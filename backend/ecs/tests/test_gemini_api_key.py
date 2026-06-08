#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gemini API キーの確認テスト"""

import os
from pathlib import Path
import sys

# 親ディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_gemini_api_key_exists():
    """Gemini API キーが環境変数に設定されていることを確認"""
    api_key = os.getenv("GEMINI_API_KEY")
    assert api_key is not None, "GEMINI_API_KEY が設定されていません"
    assert len(api_key) > 0, "GEMINI_API_KEY が空です"
    print(f"✓ Gemini API キー設定確認: {api_key[:20]}...")


def test_gemini_service_import():
    """gemini-service.py のインポートを確認"""
    import importlib.util
    
    service_path = Path(__file__).parent.parent / "src" / "services" / "gemini-service.py"
    spec = importlib.util.spec_from_file_location("gemini_service", service_path)
    gemini_service = importlib.util.module_from_spec(spec)
    
    try:
        spec.loader.exec_module(gemini_service)
        print("✓ gemini-service.py のインポートに成功しました")
        assert hasattr(gemini_service, 'parse_specs'), "parse_specs 関数が見つかりません"
        print("✓ parse_specs 関数が確認できました")
    except Exception as e:
        print(f"✗ gemini-service.py のインポートに失敗: {e}")
        raise


def test_parse_specs_basic():
    """parse_specs 関数の基本動作を確認"""
    import importlib.util
    
    service_path = Path(__file__).parent.parent / "src" / "services" / "gemini-service.py"
    spec = importlib.util.spec_from_file_location("gemini_service", service_path)
    gemini_service = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gemini_service)
    
    # 簡単なテキストで parse_specs をテスト
    test_specs_text = "CPU: Intel i7, Memory: 16GB, OS: Windows 11"
    
    try:
        result = gemini_service.parse_specs(test_specs_text)
        print(f"✓ parse_specs() の実行に成功: {type(result)}")
        assert isinstance(result, dict), "結果が辞書ではありません"
        print(f"✓ 結果は辞書形式です: {result}")
    except Exception as e:
        print(f"✗ parse_specs() の実行に失敗: {e}")
        # API キーが不正である可能性がある
        if "429" in str(e) or "401" in str(e):
            print("  → API キーが不正であるか、レート制限に達した可能性があります")
        raise


if __name__ == "__main__":
    print("=== Gemini API テスト開始 ===\n")
    
    try:
        test_gemini_api_key_exists()
        print()
        
        test_gemini_service_import()
        print()
        
        test_parse_specs_basic()
        print()
        
        print("✓ すべてのテストが成功しました！")
    except Exception as e:
        print(f"\n✗ テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
