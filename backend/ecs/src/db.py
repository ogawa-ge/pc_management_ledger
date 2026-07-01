import boto3
from typing import Optional
from boto3.dynamodb.conditions import Key

import os

# DynamoDBクライアントの初期化
# 環境変数からリージョンを取得し、なければデフォルトのリージョンを使用
region = os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'ap-northeast-1'))
dynamodb = boto3.resource('dynamodb', region_name=region)

def get_db():
    """DynamoDBのpcsテーブルを返す"""
    return dynamodb.Table('pcs')