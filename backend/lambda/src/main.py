import json
from fastapi import FastAPI, Depends
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from typing import Optional

app = FastAPI()

# 認証スキームの定義
security = HTTPBearer()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/api/auth/me")
def read_current_user(token: str = Depends(security)):
    # JWTトークンからユーザー情報を取得
    try:
        payload = jwt.decode(token.credentials, "your-secret-key", algorithms=["HS256"])
        return {"user": payload.get("sub")}
    except JWTError:
        return {"error": "Invalid token"}

@app.get("/api/auth/validate")
def validate_token(token: str = Depends(security)):
    # トークンの有効性を検証
    try:
        payload = jwt.decode(token.credentials, "your-secret-key", algorithms=["HS256"])
        return {"valid": True, "user": payload.get("sub")}
    except JWTError:
        return {"valid": False, "error": "Invalid token"}

@app.post("/api/auth/user-permissions")
def get_user_permissions(token: str = Depends(security)):
    # JWTトークンからユーザーIDを取得
    try:
        payload = jwt.decode(token.credentials, "your-secret-key", algorithms=["HS256"])
        user_id = payload.get("sub")
        
        if not user_id:
            return {"error": "User ID not found in token"}
        
        # ユーザー権限を取得
        from services.auth_service import get_user_permissions as get_permissions
        permissions = get_permissions(user_id)
        
        return {"permissions": permissions}
    except JWTError:
        return {"error": "Invalid token"}

def lambda_handler(event, context):
    # FastAPIアプリケーションをLambda用にラップ
    from mangum import Mangum
    
    # FastAPIアプリケーションをMangumでラップ
    handler = Mangum(app)
    
    # Lambdaイベントを処理
    return handler(event, context)