from typing import Dict, Any, Optional
from src.models.pc import Pc, PcRepository
from src.services.gemini_service import parse_specs
from src.models.return_record import ReturnRecord, ReturnRecordRepository
from src.models.usage_history import UsageHistory, UsageHistoryRepository
from datetime import datetime
import re
import uuid
from fastapi import HTTPException
import boto3
import os
from boto3.dynamodb.types import TypeSerializer

from src.services.idempotency_service import IdempotencyService


_serializer = TypeSerializer()


def _serialize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {key: _serializer.serialize(value) for key, value in item.items() if value is not None}


def _dynamodb_client(client=None):
    return client or boto3.client("dynamodb")


def create_pc_transaction(
    owner_id: str,
    specs_text: str,
    pc_type: str,
    idempotency_key: str,
    owner_request_id: str,
    started_at: str,
    client=None,
) -> Dict[str, Any]:
    parsed_specs = parse_specs(specs_text)
    pc_id = generate_pc_id(owner_id, pc_type)
    now = datetime.utcnow().isoformat()
    type_name = "Notebook" if pc_type == "N" else "Desktop" if pc_type == "D" else pc_type
    pc_item = {
        "pcId": pc_id,
        "ownerId": owner_id,
        "type": type_name,
        "status": "InUse",
        "cpu": parsed_specs.get("cpu"),
        "memory": parsed_specs.get("memory"),
        "storage": parsed_specs.get("storage"),
        "os": parsed_specs.get("os"),
        "manufacturer": parsed_specs.get("manufacturer"),
        "model": parsed_specs.get("model") or "Unknown",
        "serialNumber": parsed_specs.get("serial_number"),
        "createdAt": now,
        "updatedAt": now,
    }
    history_item = {
        "historyId": str(uuid.uuid4()),
        "pcId": pc_id,
        "userId": owner_id,
        "status": "InUse",
        "reason": "registered",
        "date": now,
    }
    response = {"pcId": pc_id, "status": "success"}
    success_update = IdempotencyService().success_update(
        idempotency_key, owner_request_id, started_at, 200, response
    )
    _dynamodb_client(client).transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName": os.getenv("PCS_TABLE_NAME", "PCs"),
                    "Item": _serialize_item(pc_item),
                    "ConditionExpression": "attribute_not_exists(pcId)",
                }
            },
            {
                "Put": {
                    "TableName": os.getenv("USAGE_HISTORY_TABLE_NAME", "PCUsageHistories"),
                    "Item": _serialize_item(history_item),
                    "ConditionExpression": "attribute_not_exists(historyId)",
                }
            },
            success_update,
        ]
    )
    return response


def return_pc_transaction(
    pc_id: str,
    user_id: str,
    return_reason: str,
    condition: str,
    idempotency_key: str,
    owner_request_id: str,
    started_at: str,
    client=None,
) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    record_id = str(uuid.uuid4())
    return_item = {
        "recordId": record_id,
        "pcId": pc_id,
        "userId": user_id,
        "returnDate": now[:10],
        "reason": return_reason,
        "condition": condition,
        "createdAt": now,
    }
    history_item = {
        "historyId": str(uuid.uuid4()),
        "pcId": pc_id,
        "userId": user_id,
        "status": "Unused",
        "reason": return_reason,
        "date": now,
    }
    response = {"status": "success", "message": "返却処理が正常に完了しました。", "recordId": record_id}
    success_update = IdempotencyService().success_update(
        idempotency_key, owner_request_id, started_at, 200, response
    )
    _dynamodb_client(client).transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName": os.getenv("RETURN_RECORDS_TABLE_NAME", "ReturnRecords"),
                    "Item": _serialize_item(return_item),
                    "ConditionExpression": "attribute_not_exists(recordId)",
                }
            },
            {
                "Update": {
                    "TableName": os.getenv("PCS_TABLE_NAME", "PCs"),
                    "Key": {"pcId": {"S": pc_id}},
                    "UpdateExpression": "SET #status=:status, updatedAt=:updated",
                    "ConditionExpression": "attribute_exists(pcId)",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {
                        ":status": {"S": "Unused"},
                        ":updated": {"S": now},
                    },
                }
            },
            {
                "Put": {
                    "TableName": os.getenv("USAGE_HISTORY_TABLE_NAME", "PCUsageHistories"),
                    "Item": _serialize_item(history_item),
                    "ConditionExpression": "attribute_not_exists(historyId)",
                }
            },
            success_update,
        ]
    )
    return response


def update_pc_status_transaction(
    pc_id: str,
    user_id: str,
    old_status: str,
    new_status: str,
    reason: Optional[str],
    idempotency_key: str,
    owner_request_id: str,
    started_at: str,
    client=None,
) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()
    history_item = {
        "historyId": str(uuid.uuid4()),
        "pcId": pc_id,
        "userId": user_id,
        "status": new_status,
        "reason": reason or "status_updated",
        "date": now,
    }
    response = {
        "status": "success",
        "pcId": pc_id,
        "previousStatus": old_status,
        "newStatus": new_status,
        "updatedAt": now,
    }
    success_update = IdempotencyService().success_update(
        idempotency_key, owner_request_id, started_at, 200, response
    )
    _dynamodb_client(client).transact_write_items(
        TransactItems=[
            {
                "Update": {
                    "TableName": os.getenv("PCS_TABLE_NAME", "PCs"),
                    "Key": {"pcId": {"S": pc_id}},
                    "UpdateExpression": "SET #status=:newStatus, updatedAt=:updated",
                    "ConditionExpression": "#status=:oldStatus",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {
                        ":newStatus": {"S": new_status},
                        ":oldStatus": {"S": old_status},
                        ":updated": {"S": now},
                    },
                }
            },
            {
                "Put": {
                    "TableName": os.getenv("USAGE_HISTORY_TABLE_NAME", "PCUsageHistories"),
                    "Item": _serialize_item(history_item),
                    "ConditionExpression": "attribute_not_exists(historyId)",
                }
            },
            success_update,
        ]
    )
    return response

def generate_pc_id(owner_id: str, pc_type: str) -> str:
    """
    PC IDを自動生成する
    パターン: N-XXX または D-XXX (N: ノートパソコン, D: デスクトップ)
    """
    table = boto3.resource("dynamodb").Table(os.getenv("PCS_TABLE_NAME", "PCs"))
    response = table.scan(ProjectionExpression="pcId")
    items = list(response.get("Items", []))
    while response.get("LastEvaluatedKey"):
        response = table.scan(
            ProjectionExpression="pcId",
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    max_number = 0
    pattern = rf'^{re.escape(pc_type)}-(\d+)$'
    for item in items:
        match = re.match(pattern, item.get("pcId", ""))
        if match:
            number = int(match.group(1))
            max_number = max(max_number, number)
    return f"{pc_type}-{max_number + 1:03d}"

def create_pc(owner_id: str = None, specs_text: str = None, pc_type: str = "N") -> Dict[str, Any]:
    """
    PCを新規作成
    """
    if not owner_id:
        raise HTTPException(status_code=400, detail="owner_id is required")

    # スペックを解析
    parsed_specs = parse_specs(specs_text)
    
    # PC IDを生成
    pc_id = generate_pc_id(owner_id, pc_type)
    
    # PCオブジェクトを作成
    pc = Pc(
        pc_id=pc_id,
        owner_id=owner_id,
        type=pc_type,
        cpu=parsed_specs.get("cpu"),
        memory=parsed_specs.get("memory"),
        storage=parsed_specs.get("storage"),
        os=parsed_specs.get("os"),
        manufacturer=parsed_specs.get("manufacturer"),
        model=parsed_specs.get("model"),
        serial_number=parsed_specs.get("serial_number"),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    
    # リポジトリを使用してPCを保存
    repository = PcRepository()
    created_pc = repository.create_pc(pc)
    
    return created_pc.dict()

async def process_pc_return(pc_id: str, user_id: str, return_reason: str, pc_status_at_return: str) -> Dict[str, Any]:
    """
    PCの返却処理を実行し、返却記録を作成し、PCのステータスを更新する。
    """
    # 1. 返却記録の作成
    return_repo = ReturnRecordRepository()
    
    # UUIDを生成するロジックが必要だが、ここでは仮のIDを使用
    record_id = f"RET-{pc_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    return_record = ReturnRecord(
        record_id=record_id,
        pc_id=pc_id,
        user_id=user_id,
        return_date=datetime.now(),
        return_reason=return_reason,
        pc_status_at_return=pc_status_at_return,
        # created_atはデフォルトで設定される
    )
    
    # 記録を保存
    await return_repo.create_record(return_record)
    
    # 2. PCのステータス更新 (仮実装: PcRepositoryにupdate_pc_statusメソッドが必要)
    pc_repo = PcRepository()
    # 実際のDB操作をシミュレート
    # await pc_repo.update_pc_status(pc_id, "Returned")
    
    return {"message": f"PC ID {pc_id} の返却処理が正常に完了しました。記録ID: {record_id}"}


async def record_usage_history(
    pc_id: str,
    action: str,
    user_id: Optional[str] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    reason: Optional[str] = None,
    condition: Optional[str] = None
) -> UsageHistory:
    """
    PC 利用履歴を記録する
    
    Args:
        pc_id: PC ID
        action: 'registered', 'returned', 'status_updated', 'disposed'
        user_id: ユーザー ID（オプション）
        old_status: 前のステータス（オプション）
        new_status: 新しいステータス（オプション）
        reason: 理由（オプション）
        condition: PC の状態（オプション）
    
    Returns:
        UsageHistory: 作成された利用履歴レコード
    """
    history_id = str(uuid.uuid4())
    
    history_record = UsageHistory(
        id=history_id,
        pc_id=pc_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        user_id=user_id,
        reason=reason,
        condition=condition,
        created_at=datetime.utcnow().isoformat()
    )
    
    try:
        repo = UsageHistoryRepository()
        return await repo.create_record(history_record)
    except Exception as e:
        print(f"Error recording usage history: {e}")
        raise