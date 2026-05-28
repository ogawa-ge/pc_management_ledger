#!/usr/bin/env python3
"""
初期管理者設定スクリプト

このスクリプトは、システムの初回セットアップ時に初期管理者ユーザーを DynamoDB に作成します。
本番環境デプロイ時の初期化手順として使用されます。

使用方法:
    python scripts/seed-initial-admin.py --name "管理者名" --email "admin@example.com"
"""

import boto3
import argparse
import os
import sys
from datetime import datetime
from typing import Optional, Dict, Any

# DynamoDB リソースの初期化
def get_dynamodb_resource():
    """DynamoDB リソースを取得"""
    region = os.getenv('AWS_REGION', 'us-east-1')
    return boto3.resource('dynamodb', region_name=region)


def check_admin_exists(users_table) -> bool:
    """
    Admin ロールのユーザーが既に存在するかチェック
    """
    try:
        response = users_table.scan(
            FilterExpression="attribute_exists(#role) AND #role = :admin",
            ExpressionAttributeNames={"#role": "role"},
            ExpressionAttributeValues={":admin": "Admin"}
        )
        return len(response.get('Items', [])) > 0
    except Exception as e:
        print(f"Error checking for existing admins: {e}")
        return False


def create_initial_admin(
    name: str,
    email: str,
    user_id: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    初期管理者ユーザーを作成
    
    Args:
        name: 管理者の名前
        email: 管理者のメールアドレス
        user_id: ユーザー ID（オプション、指定されない場合は自動生成）
        force: 既存の Admin が存在する場合でも作成するかどうか
    
    Returns:
        作成されたユーザーの情報
    """
    dynamodb = get_dynamodb_resource()
    users_table = dynamodb.Table('Users')
    
    # Admin が既に存在するかチェック
    if check_admin_exists(users_table) and not force:
        print("❌ Error: An Admin user already exists.")
        print("   Use --force flag to override.")
        return {"error": "Admin user already exists"}
    
    # user_id が指定されていない場合は自動生成
    if not user_id:
        user_id = f"admin-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    # Admin ユーザーオブジェクトを作成
    admin_user = {
        'userId': user_id,
        'name': name,
        'email': email,
        'role': 'Admin',
        'createdAt': datetime.utcnow().isoformat(),
        'status': 'active',
        'permissions': [
            'pc:create',
            'pc:read',
            'pc:update',
            'pc:delete',
            'pc:change_status',
            'user:create',
            'user:read',
            'user:update',
            'user:delete',
            'report:read'
        ]
    }
    
    try:
        # DynamoDB に insert
        users_table.put_item(Item=admin_user)
        
        print("✅ Initial admin user created successfully!")
        print(f"   User ID: {user_id}")
        print(f"   Name: {name}")
        print(f"   Email: {email}")
        print(f"   Role: Admin")
        print(f"   Created At: {admin_user['createdAt']}")
        
        return admin_user
    
    except Exception as e:
        print(f"❌ Error creating initial admin: {e}")
        return {"error": str(e)}


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='Create initial admin user for PC Management Ledger'
    )
    parser.add_argument(
        '--name',
        default='System Administrator',
        help='Admin user name (default: System Administrator)'
    )
    parser.add_argument(
        '--email',
        default='admin@pcmanagement.local',
        help='Admin user email (default: admin@pcmanagement.local)'
    )
    parser.add_argument(
        '--user-id',
        help='Custom user ID (optional, auto-generated if not provided)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force creation even if Admin already exists'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("PC Management Ledger - Initial Admin Setup")
    print("=" * 60)
    
    # AWS 認証情報を確認
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"\n📍 AWS Account: {identity['Account']}")
        print(f"   User/Role: {identity['Arn']}\n")
    except Exception as e:
        print(f"⚠️  Warning: Could not verify AWS credentials: {e}\n")
    
    # 初期管理者を作成
    result = create_initial_admin(
        name=args.name,
        email=args.email,
        user_id=args.user_id,
        force=args.force
    )
    
    if 'error' in result:
        print("\n❌ Setup failed. Please check the error above.")
        return 1
    
    print("\n" + "=" * 60)
    print("✅ Admin setup completed successfully!")
    print("=" * 60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
