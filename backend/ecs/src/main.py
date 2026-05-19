from fastapi import FastAPI, HTTPException, Depends
from typing import Dict, Any, List
from datetime import datetime
import uuid
from backend.ecs.src.services.gemini_service import parse_specs
from backend.ecs.src.services.pc_service import create_pc
from backend.ecs.src.models.user import UserRepository
from backend.ecs.src.models.return-record import ReturnRecordRepository
from backend.ecs.src.db import dynamodb

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
        result = await pc_service.process_pc_return(
            pc_id=pc_id,
            user_id=user_id,
            return_reason=return_reason,
            pc_status_at_return=pc_status_at_return
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PC 返却処理中に予期せぬエラーが発生しました：{str(e)}")
