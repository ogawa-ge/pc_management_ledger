from typing import Optional, List
from datetime import datetime
from src.db import get_db
from src.models.base import BaseApiModel


class Pc(BaseApiModel):
    pc_id: str
    owner_id: str
    type: str
    status: str = "Unused"  # InUse, Unused, PendingDisposal, Disposed
    cpu: Optional[str] = None
    memory: Optional[str] = None
    storage: Optional[str] = None
    os: Optional[str] = None
    manufacturer: Optional[str] = None
    model: str
    serial_number: Optional[str] = None
    created_at: str
    updated_at: str


class PcCreateRequest(BaseApiModel):
    owner_id: Optional[str] = None
    specs_text: Optional[str] = None
    pc_type: str = "N"


class PcParseRequest(BaseApiModel):
    specs_text: str


class PcReturnRequest(BaseApiModel):
    user_id: str
    return_reason: str
    pc_status_at_return: str


class PcRepository:
    def __init__(self):
        self.table = get_db()["pcs"]

    def create_pc(self, pc: Pc) -> Pc:
        """PCを新規作成"""
        self.table.put_item(Item=pc.dict())
        return pc

    def get_pc_by_id(self, pc_id: str) -> Optional[Pc]:
        """PC IDでPCを取得"""
        response = self.table.get_item(Key={"pc_id": pc_id})
        if "Item" in response:
            return Pc(**response["Item"])
        return None

    def get_pcs_by_owner_id(self, owner_id: str) -> List[Pc]:
        """所有者IDでPCを取得"""
        response = self.table.query(
            IndexName="ownerId-index",
            KeyConditionExpression=Key("owner_id").eq(owner_id)
        )
        return [Pc(**item) for item in response["Items"]]

    def update_pc(self, pc_id: str, update_data: dict) -> Optional[Pc]:
        """PCを更新"""
        update_data["updated_at"] = datetime.now().isoformat()
        response = self.table.update_item(
            Key={"pc_id": pc_id},
            UpdateExpression="SET #data = :val",
            ExpressionAttributeNames={"#data": "data"},
            ExpressionAttributeValues={":val": update_data},
            ReturnValues="ALL_NEW"
        )
        return Pc(**response["Attributes"])

    def delete_pc(self, pc_id: str) -> bool:
        """PCを削除"""
        self.table.delete_item(Key={"pc_id": pc_id})
        return True

    def get_all_pcs(self) -> List[Pc]:
        """すべてのPCを取得"""
        response = self.table.scan()
        return [Pc(**item) for item in response["Items"]]

    def get_pcs_by_status(self, status: str) -> List[Pc]:
        """ステータスでPCを取得"""
        response = self.table.query(
            IndexName="status-index",
            KeyConditionExpression=Key("status").eq(status)
        )
        return [Pc(**item) for item in response["Items"]]