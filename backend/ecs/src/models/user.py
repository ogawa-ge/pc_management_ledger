from typing import Optional
from src.models.base import BaseApiModel

class User(BaseApiModel):
    user_id: str
    name: str
    email: str
    role: str  # 'User' or 'Admin'
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserRepository:
    def __init__(self, db_client=None):
        from src.db import dynamodb
        self.table = dynamodb.Table('Users')

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        response = self.table.get_item(Key={'userId': user_id})
        if 'Item' in response:
            return User(**response['Item'])
        return None
