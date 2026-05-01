from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status

# JWTの秘密鍵（実際の運用では環境変数から取得する）
SECRET_KEY = "your-secret-key"
ALGORITHM = "HS256"

def verify_token(token: str) -> Dict[str, Any]:
    """
    JWTトークンを検証し、ユーザー情報を返す
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="無効なトークンです",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_user_permissions(user_id: str) -> list:
    """
    ユーザーの権限を取得する（実際の実装ではDBから取得）
    """
    # 仮の権限データ
    permissions = {
        "admin": ["read", "write", "delete", "manage_users"],
        "user": ["read", "write"],
        "guest": ["read"]
    }
    
    # 実際の実装では、DBからユーザー情報を取得し、権限を取得する
    # ここでは簡略化のために、固定の権限を返す
    return permissions.get("user", [])

def check_permission(user_id: str, required_permission: str) -> bool:
    """
    ユーザーが特定の権限を持っているかを確認する
    """
    permissions = get_user_permissions(user_id)
    return required_permission in permissions