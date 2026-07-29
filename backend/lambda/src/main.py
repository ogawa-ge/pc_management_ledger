import json
import urllib3
from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from typing import Optional
from src.services.ecs_manager import get_ecs_manager

app = FastAPI()

# CORS設定
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

# 認証スキームの定義
security = HTTPBearer()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/api/auth/me")
def read_current_user(token: str = Depends(security)):
    # JWTトークンからユーザー情報を取得
    try:
        payload = jwt.decode(token.credentials, "your-secret-key", algorithms=["HS256"])
        return {"user": payload.get("sub")}
    except JWTError:
        return {"error": "Invalid token"}

@app.get("/api/auth/validate")
def validate_token(token: str = Depends(security)):
    # トークンの有効性を検証
    try:
        payload = jwt.decode(token.credentials, "your-secret-key", algorithms=["HS256"])
        return {"valid": True, "user": payload.get("sub")}
    except JWTError:
        return {"valid": False, "error": "Invalid token"}

from pydantic import BaseModel

class UserPermissionRequest(BaseModel):
    userId: str

@app.post("/api/auth/user-permissions")
def get_user_permissions(req: UserPermissionRequest):
    user_id = req.userId
    
    if not user_id:
        return {"error": "User ID not provided"}
    
    # ユーザー権限とロールを取得
    from src.services.auth_service import get_user_permissions as get_permissions, get_user_role
    permissions = get_permissions(user_id)
    role = get_user_role(user_id) or "User"
    
    return {"permissions": permissions, "role": role}

# 資産管理 API (ECSへのリバースプロキシ)
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def proxy_to_ecs(path: str, request: Request):
    """
    資産管理 API (/api/pcs/* 等) へのリクエストを ECS (Fargate) にプロキシ転送します。
    ECS がスリープ中の場合は、自動起動をトリガーして 503 (Retry-After) を返します。
    """
    # 1. ECSManager で ECS の起動確認と IP 取得
    ecs_manager = get_ecs_manager()
    public_ip = ecs_manager.get_ecs_public_ip()
    
    if not public_ip:
        # ECS が起動していない場合は起動プロセスをバックグラウンドで開始
        ecs_manager.ensure_ecs_running()
        
        # HTTP 503 を返して、フロントエンドに再試行を促す
        return JSONResponse(
            status_code=503,
            content={
                "status": "starting",
                "message": "ECS server is starting up. Please try again in 10-15 seconds."
            },
            headers={"Retry-After": "15"}
        )
    
    # 2. リクエストの内容を ECS へフォワード
    method = request.method
    
    # クエリパラメータの再構築
    query_params = dict(request.query_params)
    query_string = f"?{urllib3.request.urlencode(query_params)}" if query_params else ""
    
    # 転送先 URL
    target_url = f"http://{public_ip}:80/{path}{query_string}"
    
    # ヘッダーの引き継ぎ (Hostヘッダーは上書き)
    headers = {key: value for key, value in request.headers.items() if key.lower() != "host"}
    
    # リクエストボディの取得
    body = await request.body()
    
    # HTTP クライアント (urllib3) でリクエストを送信
    http = urllib3.PoolManager()
    try:
        ecs_response = http.request(
            method=method,
            url=target_url,
            headers=headers,
            body=body if body else None,
            redirect=False,
            timeout=10.0
        )
        
        # レスポンスヘッダーからプロキシに不適切なものを除外
        excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
        resp_headers = {
            key: value for key, value in ecs_response.headers.items()
            if key.lower() not in excluded_headers
        }
        
        return Response(
            content=ecs_response.data,
            status_code=ecs_response.status,
            headers=resp_headers
        )
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={
                "status": "error",
                "message": f"Failed to forward request to ECS: {str(e)}"
            }
        )

def lambda_handler(event, context):
    # FastAPIアプリケーションをLambda用にラップ
    from mangum import Mangum
    
    # FastAPIアプリケーションをMangumでラップ
    handler = Mangum(app)
    
    # Lambdaイベントを処理
    return handler(event, context)
