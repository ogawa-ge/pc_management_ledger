#!/usr/bin/env python3
"""T020受け入れ検証用のダミーUsersを安全に作成・削除する。"""

import argparse
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


USER_ID_PREFIX = "t020-dummy-"
DEFAULT_COUNT = 25


def build_dummy_user(index: int, created_at: str) -> dict:
    user = {
        "userId": f"{USER_ID_PREFIX}{index:03d}",
        "role": "User",
        "createdAt": created_at,
        "updatedAt": created_at,
    }

    if index != 24:
        user["name"] = f"T020検証ユーザー{index:02d}"
    if index != 25:
        user["email"] = f"t020-dummy-{index:03d}@example.invalid"

    return user


def verify_account(expected_account_id: str, region: str) -> None:
    sts = boto3.client("sts", region_name=region)
    identity = sts.get_caller_identity()
    actual_account_id = identity["Account"]
    if actual_account_id != expected_account_id:
        raise RuntimeError(
            f"AWS account mismatch: expected {expected_account_id}, actual {actual_account_id}"
        )
    print(f"AWS Account: {actual_account_id}")
    print(f"Principal: {identity['Arn']}")


def list_dummy_user_ids(table) -> list[str]:
    user_ids = []
    scan_arguments = {
        "FilterExpression": "begins_with(userId, :prefix)",
        "ExpressionAttributeValues": {":prefix": USER_ID_PREFIX},
        "ProjectionExpression": "userId",
    }
    while True:
        response = table.scan(**scan_arguments)
        user_ids.extend(item["userId"] for item in response.get("Items", []))
        last_evaluated_key = response.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break
        scan_arguments["ExclusiveStartKey"] = last_evaluated_key
    return sorted(user_ids)


def seed(table, count: int) -> tuple[list[str], list[str]]:
    created_at = datetime.now(timezone.utc).isoformat()
    created = []
    skipped = []

    for index in range(1, count + 1):
        user = build_dummy_user(index, created_at)
        try:
            table.put_item(
                Item=user,
                ConditionExpression="attribute_not_exists(userId)",
            )
            created.append(user["userId"])
        except ClientError as error:
            if error.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            skipped.append(user["userId"])

    return created, skipped


def cleanup(table) -> list[str]:
    user_ids = list_dummy_user_ids(table)
    with table.batch_writer() as batch:
        for user_id in user_ids:
            batch.delete_item(Key={"userId": user_id})
    return user_ids


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-account-id", required=True)
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--table-name", default="Users")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    if not 1 <= args.count <= 100:
        parser.error("--count must be between 1 and 100")

    verify_account(args.expected_account_id, args.region)
    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table_name)
    table.load()

    if args.cleanup:
        deleted = cleanup(table)
        print(f"Deleted: {len(deleted)}")
        print("Remaining dummy users:", len(list_dummy_user_ids(table)))
        return 0

    created, skipped = seed(table, args.count)
    actual_ids = list_dummy_user_ids(table)
    print(f"Created: {len(created)}")
    print(f"Skipped existing: {len(skipped)}")
    print(f"Total dummy users: {len(actual_ids)}")
    print("Dummy user IDs:", ", ".join(actual_ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())