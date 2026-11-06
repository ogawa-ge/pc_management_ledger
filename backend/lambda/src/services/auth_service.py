from datetime import datetime, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status
import os

# DynamoDBクライアントの初期化
from src.db import dynamodb

# JWTの秘密鍵（実際の運用では環境変数から取得する）
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
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

def is_allowed_email_domain(email: str, allowed_domain: str) -> bool:
    """
    メールアドレスのドメインが許可ドメインと完全一致するかを判定する（大文字・小文字は区別しない）
    """
    normalized_allowed_domain = (allowed_domain or "").strip().lower()
    normalized_email = (email or "").strip()
    if not normalized_allowed_domain or "@" not in normalized_email:
        return False

    email_domain = normalized_email.rsplit("@", 1)[1].lower()
    if not email_domain:
        return False

    return email_domain == normalized_allowed_domain

def sync_user(user_id: str, email: str, name: Optional[str]) -> Dict[str, Any]:
    """
    ログイン時に Users を upsert する
    未登録なら role=User で作成し、登録済みなら email・name・updatedAt のみ更新する（role・createdAt は保持）
    """
    normalized_user_id = (user_id or "").strip()
    normalized_email = (email or "").strip().lower()
    if not normalized_user_id or not normalized_email:
        raise ValueError("userId and email are required")

    now = datetime.now(timezone.utc).isoformat()
    set_clauses = [
        "email = :email",
        "updatedAt = :now",
        "#role = if_not_exists(#role, :user)",
        "createdAt = if_not_exists(createdAt, :now)",
    ]
    expression_attribute_names = {"#role": "role"}
    expression_attribute_values = {":email": normalized_email, ":now": now, ":user": "User"}

    normalized_name = (name or "").strip()
    if normalized_name:
        set_clauses.append("#name = :name")
        expression_attribute_names["#name"] = "name"
        expression_attribute_values[":name"] = normalized_name

    table = dynamodb.Table('Users')
    response = table.update_item(
        Key={'userId': normalized_user_id},
        UpdateExpression="SET " + ", ".join(set_clauses),
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="ALL_NEW",
    )
    attributes = response.get('Attributes', {})

    return {
        "userId": normalized_user_id,
        "role": attributes.get('role', 'User'),
        "created": attributes.get('createdAt') == now,
    }

def get_user_permissions(user_id: str) -> list:
    """
    DBからユーザーの権限を取得する
    """
    try:
        # Usersテーブルからユーザー情報を取得
        table = dynamodb.Table('Users')
        response = table.get_item(Key={'userId': user_id})
        user = response.get('Item')
        
        if not user:
            return []
            
        # ユーザーの権限を返す
        return user.get('permissions', [])
    except Exception as e:
        # エラーが発生した場合はログを出力し、空の権限を返す
        print(f"Error getting user permissions: {e}")
        return []

def get_user_role(user_id: str) -> Optional[str]:
    """
    DBからユーザーのロールを取得する
    """
    try:
        table = dynamodb.Table('Users')
        response = table.get_item(Key={'userId': user_id})
        user = response.get('Item')
        
        if not user:
            return None
            
        return user.get('role', 'User')
    except Exception as e:
        print(f"Error getting user role: {e}")
        return None

def check_permission(user_id: str, required_permission: str) -> bool:
    """
    ユーザーが特定の権限を持っているかを確認する
    """
    permissions = get_user_permissions(user_id)
    return required_permission in permissions