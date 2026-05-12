from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    user_id: str
    name: str
    email: str
    role: str  # 'user' or 'admin'
    created_at: str
    updated_at: str

class UserRepository:
    def __init__(self, db_client):
        self.db_client = db_client

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        # Implement logic to fetch user from database
        pass

    def create_user(self, user: User) -> User:
        # Implement logic to create user in database
        pass

    def update_user(self, user: User) -> User:
        # Implement logic to update user in database
        pass

    def delete_user(self, user_id: str) -> bool:
        # Implement logic to delete user from database
        pass