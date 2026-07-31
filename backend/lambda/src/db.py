import boto3
from typing import Optional

import os

# DynamoDBクライアントの初期化
# 環境変数からリージョンを取得し、なければデフォルトのリージョンを使用
region = os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'ap-northeast-1'))
dynamodb = boto3.resource('dynamodb', region_name=region)
