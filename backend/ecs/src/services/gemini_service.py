import os
import json
import re
from typing import Dict, Any
import urllib.request
import urllib.parse

def parse_specs(specs_text: str) -> Dict[str, Any]:
    """
    指定されたテキストからPCスペック情報を抽出し、辞書形式で返す
    
    Args:
        specs_text (str): PCのスペック情報を含むテキスト
        
    Returns:
        Dict[str, Any]: 抽出されたPCスペック情報の辞書
    """
    # Gemini API キーを環境変数から取得
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY is not set"}
    
    if not specs_text or not specs_text.strip():
        return {"error": "Empty input text"}
    
    # Gemini API エンドポイント
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    prompt = f"""以下のテキストからPCのスペック情報をJSON形式で抽出してください。
以下のフィールドを含めてください。項目が見当たらない場合は、文脈から推測（例: MacBookならmacOS）するか、null を設定してください。

- cpu: プロセッサ名（例: Intel Core i7-1260P）
- memory: メモリ容量（数値のみ、単位はGB。例: 16）
- storage: ストレージ容量（数値のみ、単位はGB。例: 512）
- os: OS名（例: Windows 11 Pro, macOS, Ubuntu）
- gpu: グラフィックボード名（例: NVIDIA GeForce RTX 3060）
- motherboard: マザーボード名

必ず以下の形式のJSONのみを返してください。単位記号などは含めず、数値のみを返してください。

{{
  "cpu": "...",
  "memory": 16,
  "storage": 512,
  "os": "...",
  "gpu": "...",
  "motherboard": "..."
}}

テキスト:
{specs_text}"""
    
    try:
        # リクエストボディを作成
        request_body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ]
        }
        
        # JSONエンコード
        json_data = json.dumps(request_body).encode('utf-8')
        
        # HTTPリクエストを作成
        req = urllib.request.Request(
            api_url,
            data=json_data,
            headers={
                'Content-Type': 'application/json',
            },
            method='POST'
        )
        
        # リクエストを送信
        with urllib.request.urlopen(req, timeout=30) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            
            # 応答からテキストを抽出
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    text_content = candidate['content']['parts'][0]['text']
                    
                    # JSONを抽出（```json ... ``` の場合に対応）
                    json_match = re.search(r'```json\n(.*?)\n```', text_content, re.DOTALL)
                    if json_match:
                        text_content = json_match.group(1)
                    else:
                        # JSONブロックがない場合は、最初の { から最後の } までを抽出
                        json_start = text_content.find('{')
                        json_end = text_content.rfind('}')
                        if json_start != -1 and json_end != -1:
                            text_content = text_content[json_start:json_end+1]
                    
                    # JSONをパース
                    parsed = json.loads(text_content)
                    return parsed
            
            return {"error": "No response from API"}
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"HTTP Error {e.code}: {error_body}")
        return {"error": f"HTTP Error {e.code}: {error_body}"}
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        return {"error": f"URL Error: {str(e.reason)}"}
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        return {"error": f"JSON Decode Error: {str(e)}"}
    except Exception as e:
        # エラーが発生した場合
        print(f"Error parsing specs: {e}")
        return {"error": str(e)}