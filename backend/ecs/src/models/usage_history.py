from typing import Optional, List
from datetime import datetime
from src.db import dynamodb
from src.models.base import BaseApiModel


class UsageHistory(BaseApiModel):
    """PC 利用履歴モデル"""
    id: str
    pc_id: str
    action: str  # 'registered', 'returned', 'status_updated', 'disposed'
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    user_id: Optional[str] = None
    reason: Optional[str] = None
    condition: Optional[str] = None
    created_at: str


import os

class UsageHistoryRepository:
    """PC 利用履歴リポジトリ"""
    
    def __init__(self):
        table_name = os.getenv('USAGE_HISTORY_TABLE_NAME', 'PCUsageHistories')
        self.table = dynamodb.Table(table_name)
    
    def create_record(self, record: UsageHistory) -> UsageHistory:
        """利用履歴レコードを作成"""
        try:
            self.table.put_item(Item=record.dict())
            return record
        except Exception as e:
            print(f"Error creating usage history record: {e}")
            raise
    
    def get_by_pc_id(self, pc_id: str) -> List[UsageHistory]:
        """PC ID で利用履歴を取得"""
        try:
            response = self.table.query(
                KeyConditionExpression="pc_id = :pc_id",
                ExpressionAttributeValues={":pc_id": pc_id}
            )
            return [UsageHistory(**item) for item in response.get('Items', [])]
        except Exception as e:
            print(f"Error getting usage history for PC {pc_id}: {e}")
            return []
    
    def get_by_user_id(self, user_id: str) -> List[UsageHistory]:
        """User ID で利用履歴を取得"""
        try:
            response = self.table.scan(
                FilterExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": user_id}
            )
            return [UsageHistory(**item) for item in response.get('Items', [])]
        except Exception as e:
            print(f"Error getting usage history for user {user_id}: {e}")
            return []
    
    def get_all(self) -> List[UsageHistory]:
        """すべての利用履歴を取得"""
        try:
            response = self.table.scan()
            return [UsageHistory(**item) for item in response.get('Items', [])]
        except Exception as e:
            print(f"Error getting all usage history: {e}")
            return []
