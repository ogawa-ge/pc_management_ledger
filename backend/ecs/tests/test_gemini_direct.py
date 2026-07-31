#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gemini API 直接テスト - urllib 版"""

import os
import json
import urllib.request
import urllib.error

def test_gemini_api_direct():
    """Gemini API の直接呼び出しテスト"""
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ GEMINI_API_KEY が設定されていません")
        return False
    
    print(f"✓ API キー確認: {api_key[:20]}...")
    
    # API エンドポイント
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    
    # テストプロンプト
    prompt = """以下のテキストからPCのスペック情報をJSON形式で抽出してください。
CPU: Intel i7-1360P
Memory: 16GB
Storage: 512GB SSD
OS: Windows 11"""
    
    # リクエストボディ
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
    
    print("\n📤 Gemini API へリクエスト送信...")
    print(f"   URL: {api_url[:50]}...")
    print(f"   Prompt: {prompt[:50]}...")
    
    try:
        # HTTPリクエスト作成
        req = urllib.request.Request(
            api_url,
            data=json_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        # リクエスト送信
        with urllib.request.urlopen(req, timeout=30) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            
            print("\n✓ API レスポンス受信")
            print(f"   Status: {response.status}")
            
            # 応答を表示
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    text = candidate['content']['parts'][0]['text']
                    print(f"\n📋 Gemini の応答:")
                    print(text)
                    
                    # JSON 抽出を試みる
                    if '{' in text and '}' in text:
                        start = text.find('{')
                        end = text.rfind('}')
                        if start != -1 and end != -1:
                            json_str = text[start:end+1]
                            try:
                                parsed = json.loads(json_str)
                                print(f"\n✓ JSON 抽出成功:")
                                print(json.dumps(parsed, indent=2, ensure_ascii=False))
                                return True
                            except json.JSONDecodeError:
                                print(f"⚠️  JSON パースに失敗しましたが、応答は受け取っています")
                                return True
                    
                    return True
            else:
                print("❌ 予期しない応答フォーマット")
                print(json.dumps(response_data, indent=2))
                return False
    
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f"\n❌ HTTP エラー {e.code}")
        print(f"   レスポンス: {error_body}")
        return False
    
    except urllib.error.URLError as e:
        print(f"\n❌ URL エラー: {e.reason}")
        return False
    
    except Exception as e:
        print(f"\n❌ エラー: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Gemini API 動作確認テスト (urllib 版)")
    print("=" * 60)
    
    success = test_gemini_api_direct()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ テスト成功！Gemini API は正常に動作しています")
    else:
        print("❌ テスト失敗")
    print("=" * 60)
