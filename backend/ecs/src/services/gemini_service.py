import os
import json
import re
import time
from typing import Dict, Any
import urllib.request
import urllib.parse
import urllib.error

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = (1, 2, 4)

# FR-008: 抽出対象6項目に含まれない識別子（BIOSシリアル番号等）を送信前に除外するためのキー名パターン
_SENSITIVE_KEY_PATTERNS = ("serialnumber", "biosserialnumber", "uuid", "assettag")


def _sanitize_specs_text(specs_text: str) -> str:
    """
    貼り付けられたテキストがJSONオブジェクトの場合、抽出対象外の識別子
    （BIOSシリアル番号等）をGemini APIへの送信前に除外する（FR-008）。
    JSONとして解析できない場合はそのまま返す。
    """
    try:
        data = json.loads(specs_text)
    except (json.JSONDecodeError, TypeError):
        return specs_text

    if not isinstance(data, dict):
        return specs_text

    sanitized = {
        key: value
        for key, value in data.items()
        if not any(pattern in key.lower().replace("_", "") for pattern in _SENSITIVE_KEY_PATTERNS)
    }
    return json.dumps(sanitized, ensure_ascii=False)


def _build_prompt(specs_text: str) -> str:
    return f"""以下のテキストからPCのスペック情報をJSON形式で抽出してください。
以下のフィールドを含めてください。項目が見当たらない場合は、文脈から推測（例: MacBookならmacOS）するか、null を設定してください。

- cpu: プロセッサ名（例: Intel Core i7-1260P）
- memory: メモリ容量（数値のみ、単位はGB、小数点第1位まで。例: 16.0）
- storage: ストレージ容量（数値のみ、単位はGB、小数点第1位まで。例: 512.0）
- os: OS名（例: Windows 11 Pro, macOS, Ubuntu）
- manufacturer: メーカー名（例: Dell, HP, Lenovo, Apple）
- model: モデル名（例: XPS 13, ThinkPad X1 Carbon）
- gpu: グラフィックスカード名（例: NVIDIA GeForce RTX 4060, Intel UHD Graphics 620）
- pcName: PCの名前（コンピューター名。例: DESKTOP-ABC1234, 20022122-0）

必ず以下の形式のJSONのみを返してください。単位記号などは含めず、数値のみを返してください。

{{
  "cpu": "...",
  "memory": 16.0,
  "storage": 512.0,
  "os": "...",
  "manufacturer": "...",
  "model": "...",
  "gpu": "...",
  "pcName": "..."
}}

テキスト:
{specs_text}"""


def _call_gemini_once(api_url: str, prompt: str) -> Dict[str, Any]:
    """Gemini APIを1回呼び出し、抽出結果の辞書を返す。失敗時は例外を送出する。"""
    request_body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    json_data = json.dumps(request_body).encode('utf-8')

    req = urllib.request.Request(
        api_url,
        data=json_data,
        headers={
            'Content-Type': 'application/json',
        },
        method='POST'
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        response_data = json.loads(response.read().decode('utf-8'))

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
                        text_content = text_content[json_start:json_end + 1]

                return json.loads(text_content)

        raise ValueError("No response from API")


def parse_specs(specs_text: str) -> Dict[str, Any]:
    """
    指定されたテキストからPCスペック情報を抽出し、辞書形式で返す。

    Gemini API呼び出しが失敗した場合は最大3回まで自動的にリトライする（FR-007）。
    3回失敗した場合は {"error": ..., "retriesExhausted": True} を返す。

    Args:
        specs_text (str): PCのスペック情報を含むテキスト

    Returns:
        Dict[str, Any]: 抽出されたPCスペック情報の辞書
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return {"error": "GEMINI_API_KEY is not set"}

    if not specs_text or not specs_text.strip():
        return {"error": "Empty input text"}

    sanitized_text = _sanitize_specs_text(specs_text)
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
    prompt = _build_prompt(sanitized_text)

    last_error_message = "Unknown error"

    for attempt in range(MAX_RETRIES):
        try:
            return _call_gemini_once(api_url, prompt)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            last_error_message = f"HTTP Error {e.code}: {error_body}"
            print(last_error_message)
        except urllib.error.URLError as e:
            last_error_message = f"URL Error: {str(e.reason)}"
            print(last_error_message)
        except json.JSONDecodeError as e:
            last_error_message = f"JSON Decode Error: {e}"
            print(last_error_message)
        except Exception as e:
            last_error_message = str(e)
            print(f"Error parsing specs: {e}")

        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_BACKOFF_SECONDS[attempt])

    return {"error": last_error_message, "retriesExhausted": True}
