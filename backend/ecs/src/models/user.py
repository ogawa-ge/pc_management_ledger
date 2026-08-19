from typing import List, Optional
from src.models.base import BaseApiModel

class User(BaseApiModel):
    user_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    role: str  # 'User' or 'Admin'
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserRepository:
    def __init__(self, db_client=None):
        if db_client is None:
            from src.db import dynamodb
            self.table = dynamodb.Table('Users')
        else:
            self.table = db_client

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        response = self.table.get_item(Key={'userId': user_id})
        if 'Item' in response:
            return User(**response['Item'])
        return None

    def user_exists(self, user_id: str) -> bool:
        return self.get_user_by_id(user_id) is not None

    def get_all_users(self) -> List[User]:
        users_by_id = {}
        scan_arguments = {}

        while True:
            response = self.table.scan(**scan_arguments)
            for item in response.get('Items', []):
                user_id = item.get('userId') or item.get('user_id')
                if user_id and user_id not in users_by_id:
                    users_by_id[user_id] = User(**item)

            last_evaluated_key = response.get('LastEvaluatedKey')
            if not last_evaluated_key:
                break
            scan_arguments = {'ExclusiveStartKey': last_evaluated_key}

        return list(users_by_id.values())
