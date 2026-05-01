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

def lambda_handler(event, context):
    # FastAPIアプリケーションをLambda用にラップ
    from mangum import Mangum
    
    # FastAPIアプリケーションをMangumでラップ
    handler = Mangum(app)
    
    # Lambdaイベントを処理
    return handler(event, context)