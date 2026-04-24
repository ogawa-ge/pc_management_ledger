import json
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

def lambda_handler(event, context):
    # FastAPIアプリケーションをLambda用にラップ
    from mangum import Mangum
    
    # FastAPIアプリケーションをMangumでラップ
    handler = Mangum(app)
    
    # Lambdaイベントを処理
    return handler(event, context)