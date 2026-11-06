import copy
from unittest.mock import Mock, patch

import pytest
from boto3.dynamodb.types import TypeDeserializer

from src.services.pc_service import (
    create_pc_transaction,
    generate_pc_id,
    return_pc_transaction,
    update_pc_status_transaction,
)


_deserializer = TypeDeserializer()


class TransactionCancelled(RuntimeError):
    pass


class AtomicMemoryClient:
    def __init__(self, tables, fail_index=None):
        self.tables = copy.deepcopy(tables)
        self.fail_index = fail_index
        self.calls = 0

    def transact_write_items(self, TransactItems):
        self.calls += 1
        staged = copy.deepcopy(self.tables)
        for index, item in enumerate(TransactItems):
            if index == self.fail_index:
                raise TransactionCancelled(f"injected failure at transaction item {index}")
            if "Put" in item:
                self._put(staged, item["Put"])
            else:
                self._update(staged, item["Update"])
        self.tables = staged

    @staticmethod
    def _decode(values):
        return {key: _deserializer.deserialize(value) for key, value in values.items()}

    def _put(self, tables, operation):
        decoded = self._decode(operation["Item"])
        table = tables[operation["TableName"]]
        key_name = next(name for name in ("pcId", "recordId", "historyId", "entityId") if name in decoded)
        key = decoded[key_name]
        if key in table:
            raise TransactionCancelled(f"duplicate key: {key}")
        table[key] = decoded

    def _update(self, tables, operation):
        table_name = operation["TableName"]
        table = tables[table_name]
        key = next(iter(self._decode(operation["Key"]).values()))
        current = table.get(key)
        values = self._decode(operation.get("ExpressionAttributeValues", {}))

        if table_name == "SystemActivity":
            if not current or not (
                current.get("status") == values[":p"]
                and current.get("ownerRequestId") == values[":owner"]
                and current.get("startedAt") == values[":started"]
            ):
                raise TransactionCancelled("idempotency owner fence rejected the transaction")
            current.update(
                {
                    "status": values[":s"],
                    "completedAt": values[":completed"],
                    "responseStatus": values[":code"],
                    "responseBody": values[":body"],
                    "expiresAt": values[":expires"],
                }
            )
            return

        if not current:
            raise TransactionCancelled(f"missing item: {key}")
        if ":oldStatus" in values and current.get("status") != values[":oldStatus"]:
            raise TransactionCancelled("old PC status no longer matches")
        current["status"] = values.get(":newStatus", values.get(":status"))
        current["updatedAt"] = values[":updated"]


def _base_tables(owner="owner", started="started"):
    return {
        "PCs": {"N-001": {"pcId": "N-001", "status": "Unused", "updatedAt": "before"}},
        "ReturnRecords": {},
        "PCUsageHistories": {},
        "SystemActivity": {
            "request#key": {
                "entityId": "request#key",
                "status": "PROCESSING",
                "ownerRequestId": owner,
                "startedAt": started,
            }
        },
    }


def _invoke_create(client):
    with patch("src.services.pc_service.parse_specs", return_value={"model": "Model"}), patch(
        "src.services.pc_service.generate_pc_id", return_value="N-002"
    ):
        return create_pc_transaction("user-1", "specs", "N", "key", "owner", "started", client)


def _invoke_return(client):
    return return_pc_transaction("N-001", "user-1", "move", "good", "key", "owner", "started", client)


def _invoke_status(client):
    return update_pc_status_transaction(
        "N-001", "admin", "Unused", "Disposed", "approved", "key", "owner", "started", client
    )


def _assert_owner_fenced_success_update(transact_items):
    success = transact_items[-1]["Update"]
    assert success["TableName"] == "SystemActivity"
    assert "ownerRequestId=:owner" in success["ConditionExpression"]
    assert "startedAt=:started" in success["ConditionExpression"]


def test_create_transaction_is_atomic_and_uses_contract_schema():
    client = Mock()
    with patch("src.services.pc_service.parse_specs", return_value={"model": "Model"}), patch(
        "src.services.pc_service.generate_pc_id", return_value="N-001"
    ):
        create_pc_transaction("user-1", "specs", "N", "key", "owner", "started", client)
    items = client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(items) == 3
    assert "pcId" in items[0]["Put"]["Item"]
    assert "historyId" in items[1]["Put"]["Item"]
    assert items[-1]["Update"]["ExpressionAttributeValues"][":body"]["S"] == '{"pcId": "N-001", "status": "success"}'
    _assert_owner_fenced_success_update(items)


def test_generate_pc_id_reads_camel_case_keys_across_scan_pages():
    table = Mock()
    table.scan.side_effect = [
        {"Items": [{"pcId": "N-001"}, {"pcId": "D-009"}], "LastEvaluatedKey": {"pcId": "D-009"}},
        {"Items": [{"pcId": "N-012"}]},
    ]
    resource = Mock()
    resource.Table.return_value = table
    with patch("src.services.pc_service.boto3.resource", return_value=resource):
        assert generate_pc_id("ignored-owner", "N") == "N-013"


def test_return_transaction_contains_record_pc_history_and_success():
    client = Mock()
    return_pc_transaction("N-001", "user-1", "move", "good", "key", "owner", "started", client)
    items = client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(items) == 4
    assert items[0]["Put"]["TableName"] == "ReturnRecords"
    assert items[1]["Update"]["Key"] == {"pcId": {"S": "N-001"}}
    assert items[2]["Put"]["TableName"] == "PCUsageHistories"
    _assert_owner_fenced_success_update(items)


def test_status_transaction_contains_pc_history_and_success():
    client = Mock()
    update_pc_status_transaction(
        "N-001", "admin", "Unused", "Disposed", "approved", "key", "owner", "started", client
    )
    items = client.transact_write_items.call_args.kwargs["TransactItems"]
    assert len(items) == 3
    assert items[0]["Update"]["ConditionExpression"] == "#status=:oldStatus"
    assert items[1]["Put"]["TableName"] == "PCUsageHistories"
    _assert_owner_fenced_success_update(items)


def test_transaction_failure_does_not_fall_back_to_partial_writes():
    client = Mock()
    client.transact_write_items.side_effect = RuntimeError("injected failure")
    try:
        return_pc_transaction("N-001", "user-1", "move", "good", "key", "owner", "started", client)
    except RuntimeError:
        pass
    else:
        raise AssertionError("transaction failure must propagate")
    client.transact_write_items.assert_called_once()


@pytest.mark.parametrize(
    ("operation", "item_count"),
    [(_invoke_create, 3), (_invoke_return, 4), (_invoke_status, 3)],
    ids=["create", "return", "status"],
)
def test_every_transaction_item_failure_leaves_no_partial_success(operation, item_count):
    for fail_index in range(item_count):
        client = AtomicMemoryClient(_base_tables(), fail_index=fail_index)
        before = copy.deepcopy(client.tables)

        with pytest.raises(TransactionCancelled, match="injected failure"):
            operation(client)

        assert client.calls == 1
        assert client.tables == before


@pytest.mark.parametrize(
    "operation",
    [_invoke_create, _invoke_return, _invoke_status],
    ids=["create", "return", "status"],
)
def test_recovered_request_rejects_old_owner_transaction_without_business_change(operation):
    client = AtomicMemoryClient(_base_tables(owner="new-owner", started="recovered-at"))
    before = copy.deepcopy(client.tables)

    with pytest.raises(TransactionCancelled, match="owner fence"):
        operation(client)

    assert client.calls == 1
    assert client.tables == before