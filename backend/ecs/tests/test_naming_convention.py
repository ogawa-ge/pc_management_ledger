import pytest
from backend.ecs.src.models.pc import Pc

def test_pc_model_serialization():
    """Pc モデルが camelCase でシリアライズされるか確認"""
    pc_data = {
        "pc_id": "N-001",
        "owner_id": "user-123",
        "type": "N",
        "status": "Unused",
        "model": "ThinkPad",
        "created_at": "2026-06-08T00:00:00",
        "updated_at": "2026-06-08T00:00:00"
    }
    pc = Pc(**pc_data)
    dump = pc.model_dump(by_alias=True)
    
    assert "pcId" in dump
    assert "ownerId" in dump
    assert "pc_id" not in dump
    assert dump["pcId"] == "N-001"
