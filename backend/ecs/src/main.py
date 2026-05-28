from fastapi import FastAPI, HTTPException, Depends, Request
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
from backend.ecs.src.services.gemini_service import parse_specs
from backend.ecs.src.services.pc_service import create_pc, record_usage_history
from backend.ecs.src.models.user import UserRepository
from backend.ecs.src.models.return_record import ReturnRecordRepository
from backend.ecs.src.models.pc import PcRepository
from backend.ecs.src.db import dynamodb

app = FastAPI()


# ========== RBAC Helper Functions ==========
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

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/api/pcs/parse-specs")
def parse_specs_endpoint(specs_text: str) -> Dict[str, Any]:
    """
    PC のスペック情報を解析して JSON 形式で返す
    """
    try:
        result = parse_specs(specs_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse specs: {str(e)})

@app.post("/api/pcs")
def create_pc_endpoint(owner_id: str = None, specs_text: str = None, pc_type: str = "N") -> Dict[str, Any]:
    """
    新しい PC を登録する
    """
    try:
        result = create_pc(owner_id, specs_text, pc_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create PC: {str(e)}")

@app.get("/api/users")
def get_users() -> List[Dict[str, Any]]:
    """
    全てのユーザーを取得する
    """
    try:
        # Users テーブルから全ユーザーを取得
        table = dynamodb.Table('Users')
        response = table.scan()
        users = response.get('Items', [])
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get users: {str(e)}")

@app.get("/api/pcs")
def get_pcs(status: str = None) -> List[Dict[str, Any]]:
    """
    PC 一覧を取得する
    
    Query Parameters:
    - status: PC のステータスでフィルタリング (InUse, Unused, PendingDisposal, Disposed)
    """
    try:
        table = dynamodb.Table('PCs')
        
        if status:
            # status でフィルタリング
            filter_expression = "status = :status"
            expression_attribute_values = {
                ":status": status
            }
            response = table.scan(
                FilterExpression=filter_expression,
                ExpressionAttributeValues=expression_attribute_values
            )
        else:
            # 全 PC を取得
            response = table.scan()
        
        pcs = response.get('Items', [])
        return pcs
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get PCs: {str(e)}")

@app.post("/api/pcs/{pc_id}/return")
async def return_pc_endpoint(pc_id: str, user_id: str, return_reason: str, pc_status_at_return: str) -> Dict[str, Any]:
    """
    PC を返却処理し、ステータスを更新し、返却記録を作成する
    """
    try:
        # pc-service.py で定義した返却処理関数を呼び出す
        result = await process_pc_return(
            pc_id=pc_id,
            user_id=user_id,
            return_reason=return_reason,
            pc_status_at_return=pc_status_at_return
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PC 返却処理中に予期せぬエラーが発生しました：{str(e)}")


@app.patch("/api/pcs/{pc_id}/status")
async def update_pc_status(
    pc_id: str,
    request: Request,
    authorization: str = None
) -> Dict[str, Any]:
    """
    PC のステータスを更新する（Admin のみ）
    
    Request Body:
    {
        "newStatus": "InUse|Unused|PendingDisposal|Disposed",
        "reason": "optional reason for status change"
    }
    """
    try:
        # Admin 権限確認
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header required")
        
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
        
        # 現在の PC 情報を取得
        pc_repo = PcRepository()
        pc = pc_repo.get_pc_by_id(pc_id)
        
        if not pc:
            raise HTTPException(status_code=404, detail=f"PC not found: {pc_id}")
        
        old_status = pc.status
        
        # ステータスが同じ場合はスキップ
        if old_status == new_status:
            return {
                "status": "success",
                "message": "No status change needed",
                "previousStatus": old_status,
                "newStatus": new_status,
                "updatedAt": datetime.utcnow().isoformat()
            }
        
        # DynamoDB でステータスを更新
        try:
            table = dynamodb.Table('PCs')
            table.update_item(
                Key={'pc_id': pc_id},
                UpdateExpression="SET #status = :new_status, #updated = :updated_at",
                ExpressionAttributeNames={
                    '#status': 'status',
                    '#updated': 'updated_at'
                },
                ExpressionAttributeValues={
                    ':new_status': new_status,
                    ':updated_at': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to update PC status: {str(e)}"
            )
        
        # 利用履歴に記録
        try:
            # authorization ヘッダーから user_id を抽出（簡易実装）
            user_id = authorization.split(" ")[1] if " " in authorization else "unknown"
            
            await record_usage_history(
                pc_id=pc_id,
                action='status_updated',
                user_id=user_id,
                old_status=old_status,
                new_status=new_status,
                reason=reason
            )
        except Exception as e:
            # 履歴記録に失敗してもエラーとしない（ステータス更新は成功）
            print(f"Warning: Failed to record usage history: {e}")
        
        return {
            "status": "success",
            "previousStatus": old_status,
            "newStatus": new_status,
            "updatedAt": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update PC status: {str(e)}"
        )
