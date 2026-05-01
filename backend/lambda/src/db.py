import boto3
from typing import Optional

# DynamoDBクライアントの初期化
# 環境変数からリージョンを取得し、なければデフォルトのリージョンを使用
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')