from fastapi import FastAPI, HTTPException
from typing import Dict, Any
from backend.ecs.src.services.gemini_service import parse_specs
from backend.ecs.src.services.pc_service import create_pc
from backend.ecs.src.services.pc_service import create_pc

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/api/pcs/parse-specs")
def parse_specs_endpoint(specs_text: str) -> Dict[str, Any]:
    """
    PCのスペック情報を解析してJSON形式で返す
    """
    try:
        result = parse_specs(specs_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse specs: {str(e)}")


@app.post("/api/pcs")
def create_pc_endpoint(owner_id: str, specs_text: str, pc_type: str = "N") -> Dict[str, Any]:
    """
    新しいPCを登録する
    """
    try:
        result = create_pc(owner_id, specs_text, pc_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create PC: {str(e)}")