import os
from typing import Dict, Any
from google.generativeai import GenerativeModel
import google.generativeai as genai

# Gemini APIの設定
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = GenerativeModel("gemini-pro")

def parse_specs(specs_text: str) -> Dict[str, Any]:
    """
    指定されたテキストからPCスペック情報を抽出し、辞書形式で返す
    
    Args:
        specs_text (str): PCのスペック情報を含むテキスト
        
    Returns:
        Dict[str, Any]: 抽出されたPCスペック情報の辞書
    """
    prompt = f"""
    以下のテキストからPCのスペック情報をJSON形式で抽出してください。
    必ずJSON形式で返してください。不要な説明は不要です。
    
    {specs_text}
    """
    
    try:
        response = model.generate_content(prompt)
        # 応答からJSONを抽出
        content = response.text
        # 簡単なJSONのパース（実際にはより堅牢な方法が必要）
        import json
        parsed = json.loads(content)
        return parsed
    except Exception as e:
        # エラーが発生した場合は、元のテキストをそのまま返す
        print(f"Error parsing specs: {e}")
        return {"error": str(e)}