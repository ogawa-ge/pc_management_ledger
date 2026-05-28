from typing import Dict, Any
from backend.ecs.src.models.pc import Pc, PcRepository
from backend.ecs.src.services.gemini_service import parse_specs
from backend.ecs.src.models.return_record import ReturnRecord, ReturnRecordRepository
from backend.ecs.src.models.usage_history import UsageHistory, UsageHistoryRepository
from datetime import datetime
import re
import uuid
from fastapi import HTTPException

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

def create_pc(owner_id: str = None, specs_text: str = None, pc_type: str = "N") -> Dict[str, Any]:
    """
    PCを新規作成
    """
    # スペックを解析
    parsed_specs = parse_specs(specs_text)
    
    # owner_idが指定されていない場合は、認証情報から取得するなどの処理が必要（仮実装）
    # ここでは、owner_idが指定されていない場合はエラーとする
    if owner_id is None:
        raise HTTPException(status_code=400, detail="owner_id is required")
    
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

async def process_pc_return(pc_id: str, user_id: str, return_reason: str, pc_status_at_return: str) -> Dict[str, Any]:
    """
    PCの返却処理を実行し、返却記録を作成し、PCのステータスを更新する。
    """
    # 1. 返却記録の作成
    return_repo = ReturnRecordRepository()
    
    # UUIDを生成するロジックが必要だが、ここでは仮のIDを使用
    record_id = f"RET-{pc_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    return_record = ReturnRecord(
        record_id=record_id,
        pc_id=pc_id,
        user_id=user_id,
        return_date=datetime.now(),
        return_reason=return_reason,
        pc_status_at_return=pc_status_at_return,
        # created_atはデフォルトで設定される
    )
    
    # 記録を保存
    await return_repo.create_record(return_record)
    
    # 2. PCのステータス更新 (仮実装: PcRepositoryにupdate_pc_statusメソッドが必要)
    pc_repo = PcRepository()
    # 実際のDB操作をシミュレート
    # await pc_repo.update_pc_status(pc_id, "Returned")
    
    return {"message": f"PC ID {pc_id} の返却処理が正常に完了しました。記録ID: {record_id}"}


async def record_usage_history(
    pc_id: str,
    action: str,
    user_id: Optional[str] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    reason: Optional[str] = None,
    condition: Optional[str] = None
) -> UsageHistory:
    """
    PC 利用履歴を記録する
    
    Args:
        pc_id: PC ID
        action: 'registered', 'returned', 'status_updated', 'disposed'
        user_id: ユーザー ID（オプション）
        old_status: 前のステータス（オプション）
        new_status: 新しいステータス（オプション）
        reason: 理由（オプション）
        condition: PC の状態（オプション）
    
    Returns:
        UsageHistory: 作成された利用履歴レコード
    """
    history_id = str(uuid.uuid4())
    
    history_record = UsageHistory(
        id=history_id,
        pc_id=pc_id,
        action=action,
        old_status=old_status,
        new_status=new_status,
        user_id=user_id,
        reason=reason,
        condition=condition,
        created_at=datetime.utcnow().isoformat()
    )
    
    try:
        repo = UsageHistoryRepository()
        return await repo.create_record(history_record)
    except Exception as e:
        print(f"Error recording usage history: {e}")
        raise