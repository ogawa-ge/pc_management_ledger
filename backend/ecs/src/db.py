import boto3
from typing import Optional
from boto3.dynamodb.conditions import Key

# DynamoDBクライアントの初期化
# 環境変数からリージョンを取得し、なければデフォルトのリージョンを使用
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')

def get_db():
    """DynamoDBのpcsテーブルを返す"""
    return dynamodb.Table('pcs')