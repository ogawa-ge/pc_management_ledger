from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from src.services.gemini_service import parse_specs
from src.services.pc_service import (
    create_pc_transaction,
    return_pc_transaction,
    update_pc_status_transaction,
)
from src.models.user import UserRepository
from src.models.return_record import ReturnRecordRepository
from src.models.pc import PcRepository, Pc, PcCreateRequest, PcParseRequest, PcReturnRequest
from src.models.user import User
from src.db import dynamodb
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from src.services.internal_request_verifier import InternalRequestVerifier
from src.services.idempotency_service import (
    IdempotencyDecision,
    IdempotencyService,
    request_fingerprint,
)

# .env.local を読み込む
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../../../.env.local"))

app = FastAPI()


@app.middleware("http")
async def verify_internal_proxy_request(request: Request, call_next):
    if request.url.path == "/":
        return await call_next(request)
    verifier = InternalRequestVerifier()
    if not verifier.enabled:
        return await call_next(request)
    body = await request.body()
    result = verifier.verify(
        method=request.method,
        path_with_query=request.url.path
        + (f"?{request.url.query}" if request.url.query else ""),
        body=body,
        headers=dict(request.headers),
    )
    if not result.valid:
        return JSONResponse(
            status_code=403,
            content={"status": "forbidden", "reason": result.reason},
        )
    request._body = body
    return await call_next(request)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://001-pc-management.d2vdxg5wq5iczb.amplifyapp.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== RBAC Helper Functions ==========
class RequestPrincipal(BaseModel):
    user_id: str
    role: str


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_idempotency_service() -> IdempotencyService:
    return IdempotencyService()


async def claim_idempotent_request(
    request: Request,
    operation: str,
    service: IdempotencyService,
) -> IdempotencyDecision:
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    try:
        uuid.UUID(key)
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Idempotency-Key must be a UUID") from error

    body = await request.body()
    path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    owner_request_id = request.headers.get("X-Internal-Request-Id") or str(uuid.uuid4())
    return service.claim(
        key=key,
        fingerprint=request_fingerprint(request.method, path, body),
        operation=operation,
        owner_request_id=owner_request_id,
    )


def idempotency_short_circuit(decision: IdempotencyDecision) -> Optional[JSONResponse]:
    if decision.action == "PROCESSING":
        return JSONResponse(
            status_code=409,
            headers={"Retry-After": "3", "Cache-Control": "no-store"},
            content={
                "status": "processing",
                "message": "同じ操作を処理中です。",
                "retryAfterSeconds": 3,
            },
        )
    if decision.action == "CONFLICT":
        return JSONResponse(
            status_code=409,
            headers={"Cache-Control": "no-store"},
            content={
                "status": "idempotency_conflict",
                "message": "同じIdempotency-Keyを異なる要求には使用できません。",
            },
        )
    if decision.action == "REPLAY":
        return JSONResponse(
            status_code=decision.response_status or 200,
            headers={"Idempotency-Replayed": "true", "Cache-Control": "no-store"},
            content=decision.response_body or {},
        )
    return None


def get_request_principal(
    request: Request,
    user_repository: UserRepository = Depends(get_user_repository),
) -> RequestPrincipal:
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    scheme, separator, user_id = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not user_id.strip() or " " in user_id.strip():
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    try:
        user = user_repository.get_user_by_id(user_id.strip())
    except Exception as error:
        raise HTTPException(status_code=503, detail="Failed to resolve authenticated user") from error

    if user is None:
        raise HTTPException(status_code=401, detail="Authenticated user not found")

    return RequestPrincipal(user_id=user.user_id, role=user.role)


def get_admin_principal(
    principal: RequestPrincipal = Depends(get_request_principal),
) -> RequestPrincipal:
    if principal.role != "Admin":
        raise HTTPException(status_code=403, detail="Admin permission required")
    return principal


async def get_user_role(user_id: str) -> Optional[str]:
    """
    DynamoDB から user_id のロールを取得
    """
    try:
        table = dynamodb.Table('Users')
        response = table.get_item(Key={'userId': user_id})
        if 'Item' in response:
            return response['Item'].get('role')
        return None
    except Exception as e:
        print(f"Error fetching user role: {e}")
        return None


def require_admin(func):
    """
    Admin ロールをチェックするデコレーター
    リクエストから user_id を取得して、Admin ロール確認
    """
    async def wrapper(*args, **kwargs):
        # FastAPI の Request オブジェクトを取得
        request = kwargs.get('request')
        if not request:
            raise HTTPException(status_code=400, detail="Request object not found")
        
        # Bearer トークンから user_id を抽出
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="No authorization header")
        
        # 簡易的な実装：トークンから user_id を取得
        # 本来は JWT をデコードしてペイロードから取得
        try:
            token = auth_header.split(" ")[1]
            # ここでは簡易的に token を user_id として使用
            # 実装では JWT デコードが必要
            user_id = token  # TODO: JWT デコード実装
        except (IndexError, ValueError):
            raise HTTPException(status_code=401, detail="Invalid token format")
        
        # user_id のロールを確認
        role = await get_user_role(user_id)
        if role != "Admin":
            raise HTTPException(status_code=403, detail="Admin permission required")
        
        # 元の関数を実行
        return await func(*args, **kwargs)
    
    return wrapper

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/api/pcs/parse-specs")
def parse_specs_endpoint(request: PcParseRequest) -> Dict[str, Any]:
    """
    PC のスペック情報を解析して JSON 形式で返す
    """
    try:
        result = parse_specs(request.specs_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse specs: {str(e)}")

@app.post("/api/pcs")
async def create_pc_endpoint(
    payload: PcCreateRequest,
    request: Request,
    principal: RequestPrincipal = Depends(get_request_principal),
    user_repository: UserRepository = Depends(get_user_repository),
    idempotency: IdempotencyService = Depends(get_idempotency_service),
) -> Any:
    """
    新しい PC を登録する
    """
    try:
        if principal.role != "Admin" and payload.owner_id != principal.user_id:
            raise HTTPException(status_code=403, detail="Cannot register a PC for another user")

        try:
            owner = user_repository.get_user_by_id(payload.owner_id)
        except Exception as error:
            raise HTTPException(status_code=503, detail="Failed to verify owner") from error

        if owner is None:
            raise HTTPException(status_code=404, detail="Owner not found")

        decision = await claim_idempotent_request(request, "create_pc", idempotency)
        short_circuit = idempotency_short_circuit(decision)
        if short_circuit:
            return short_circuit
        if not decision.owner_request_id or not decision.started_at:
            raise HTTPException(status_code=500, detail="Idempotency ownership was not established")

        return create_pc_transaction(
            payload.owner_id,
            payload.specs_text,
            payload.pc_type,
            request.headers["Idempotency-Key"],
            decision.owner_request_id,
            decision.started_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create PC: {str(e)}")

@app.get("/api/users", response_model=List[User])
def get_users(
    _principal: RequestPrincipal = Depends(get_admin_principal),
    user_repository: UserRepository = Depends(get_user_repository),
) -> List[User]:
    """
    全てのユーザーを取得する
    """
    try:
        return user_repository.get_all_users()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail="Failed to get users") from e

@app.get("/api/pcs", response_model=List[Pc])
def get_pcs(status: str = None) -> List[Pc]:
    """
    PC 一覧を取得する
    
    Query Parameters:
    - status: PC のステータスでフィルタリング (InUse, Unused, PendingDisposal, Disposed)
    """
    try:
        table = dynamodb.Table('PCs')
        
        if status:
            # status でフィルタリング (status は予約語のため ExpressionAttributeNames を使用)
            filter_expression = "#st = :status"
            expression_attribute_names = {
                "#st": "status"
            }
            expression_attribute_values = {
                ":status": status
            }
            response = table.scan(
                FilterExpression=filter_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_attribute_values
            )
        else:
            # 全 PC を取得
            response = table.scan()
        
        pcs_data = response.get('Items', [])
        return [Pc(**item) for item in pcs_data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get PCs: {str(e)}")

@app.post("/api/pcs/{pc_id}/return")
async def return_pc_endpoint(
    pc_id: str,
    payload: PcReturnRequest,
    request: Request,
    principal: RequestPrincipal = Depends(get_request_principal),
    idempotency: IdempotencyService = Depends(get_idempotency_service),
) -> Any:
    """
    PC を返却処理し、ステータスを更新し、返却記録を作成する
    """
    try:
        if principal.role != "Admin" and payload.user_id != principal.user_id:
            raise HTTPException(status_code=403, detail="Cannot return a PC for another user")
        decision = await claim_idempotent_request(request, "return_pc", idempotency)
        short_circuit = idempotency_short_circuit(decision)
        if short_circuit:
            return short_circuit
        if not decision.owner_request_id or not decision.started_at:
            raise HTTPException(status_code=500, detail="Idempotency ownership was not established")
        return return_pc_transaction(
            pc_id=pc_id,
            user_id=payload.user_id,
            return_reason=payload.return_reason,
            condition=payload.pc_status_at_return,
            idempotency_key=request.headers["Idempotency-Key"],
            owner_request_id=decision.owner_request_id,
            started_at=decision.started_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PC 返却処理中に予期せぬエラーが発生しました：{str(e)}")


@app.patch("/api/pcs/{pc_id}/status")
async def update_pc_status(
    pc_id: str,
    request: Request,
    principal: RequestPrincipal = Depends(get_admin_principal),
    idempotency: IdempotencyService = Depends(get_idempotency_service),
) -> Any:
    """
    PC のステータスを更新する（Admin のみ）
    
    Request Body:
    {
        "newStatus": "InUse|Unused|PendingDisposal|Disposed",
        "reason": "optional reason for status change"
    }
    """
    try:
        # リクエストボディを取得
        body = await request.json()
        new_status = body.get('newStatus')
        reason = body.get('reason')
        
        # バリデーション
        valid_statuses = ["InUse", "Unused", "PendingDisposal", "Disposed"]
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of {valid_statuses}"
            )
        
        decision = await claim_idempotent_request(request, "update_pc_status", idempotency)
        short_circuit = idempotency_short_circuit(decision)
        if short_circuit:
            return short_circuit
        if not decision.owner_request_id or not decision.started_at:
            raise HTTPException(status_code=500, detail="Idempotency ownership was not established")

        pc_response = dynamodb.Table(os.getenv("PCS_TABLE_NAME", "PCs")).get_item(
            Key={"pcId": pc_id}
        )
        pc_item = pc_response.get("Item")
        if not pc_item:
            raise HTTPException(status_code=404, detail=f"PC not found: {pc_id}")
        old_status = pc_item.get("status")

        return update_pc_status_transaction(
            pc_id=pc_id,
            user_id=principal.user_id,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            idempotency_key=request.headers["Idempotency-Key"],
            owner_request_id=decision.owner_request_id,
            started_at=decision.started_at,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update PC status: {str(e)}"
        )
