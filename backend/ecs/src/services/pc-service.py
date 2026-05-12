from typing import Dict, Any
from backend.ecs.src.models.pc import Pc, PcRepository
from backend.ecs.src.services.gemini_service import parse_specs
from datetime import datetime
import re

def generate_pc_id(owner_id: str, pc_type: str) -> str:
    """
    PC IDを自動生成する
    パターン: N-XXX または D-XXX (N: ノートパソコン, D: デスクトップ)
    """
    # 既存のPC IDを取得
    repository = PcRepository()
    pcs = repository.get_pcs_by_owner_id(owner_id)
    
    # 同じタイプのPCの最大番号を取得
    max_number = 0
    # NとDをNotebookとDesktopに変換
    if pc_type == "N":
        type_name = "Notebook"
    elif pc_type == "D":
        type_name = "Desktop"
    else:
        type_name = pc_type
    pattern = rf'^{type_name}-\d+$'
    for pc in pcs:
        match = re.match(pattern, pc.pc_id)
        if match:
            number = int(match.group(0).split('-')[1])
            max_number = max(max_number, number)
    
    # 新しい番号を生成
    new_number = max_number + 1
    return f"{pc_type}-{new_number:03d}"

def create_pc(owner_id: str, specs_text: str, pc_type: str = "N") -> Dict[str, Any]:
    """
    PCを新規作成
    """
    # スペックを解析
    parsed_specs = parse_specs(specs_text)
    
    # PC IDを生成
    pc_id = generate_pc_id(owner_id, pc_type)
    
    # PCオブジェクトを作成
    pc = Pc(
        pc_id=pc_id,
        owner_id=owner_id,
        type=pc_type,
        cpu=parsed_specs.get("cpu"),
        memory=parsed_specs.get("memory"),
        storage=parsed_specs.get("storage"),
        os=parsed_specs.get("os"),
        manufacturer=parsed_specs.get("manufacturer"),
        model=parsed_specs.get("model"),
        serial_number=parsed_specs.get("serial_number"),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat()
    )
    
    # リポジトリを使用してPCを保存
    repository = PcRepository()
    created_pc = repository.create_pc(pc)
    
    return created_pc.dict()