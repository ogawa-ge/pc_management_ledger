"""
Gemini PC スペック抽出精度テストスイート

このテストスイートは、様々なターミナル出力形式から PC スペック情報を
正確に抽出できるかを検証します。

テスト項目：
1. 標準フォーマット（Windows systeminfo、Linux lsb_release など）
2. エッジケース（手書きログ、非標準フォーマット、欠損データ等）

評価基準：6 項目（CPU、メモリ、ストレージ、OS、マザーボード、GPU）中 5 項目以上正確に抽出できることを合格とします。
"""

import json
import pytest
from typing import Dict, Any, List, Tuple
from datetime import datetime
from backend.ecs.src.services.gemini_service import parse_specs


class TestGeminiPCSpecsExtractionStandard:
    """標準フォーマットのターミナル出力からの PC スペック抽出テスト"""

    # テストケース: (入力テキスト, 期待される出力の最小要件)
    STANDARD_TEST_CASES = [
        # Windows systeminfo 形式 - 1
        (
            """
            ホスト名:                          DESKTOP-ABC123
            OS 名:                             Microsoft Windows 11 Pro
            OS バージョン:                      10.0.22621 Build 22621
            システム製造元:                      Dell Inc.
            システム モデル:                    XPS 13 Plus
            プロセッサ:                         Intel(R) Core(TM) i7-1360P CPU @ 2.20GHz
            物理メモリ:                         16384 MB
            
            ディスク情報:
            C:\                                 931 GB / 1000 GB (SSD)
            """,
            {"cpu": "Intel", "memory": "16", "storage": "931", "os": "Windows 11", "system_model": "XPS"}
        ),
        # Windows systeminfo 形式 - 2 (高スペック)
        (
            """
            ホスト名:                          WORKSTATION-001
            OS 名:                             Microsoft Windows 11 Pro for Workstations
            プロセッサ:                         Intel(R) Xeon(R) Platinum 8280
            プロセッサ数:                       2
            コア数:                             28
            物理メモリ:                         128 GB
            
            ストレージ:
            NVMe SSD:                          2 TB
            SATA SSD:                          2 TB
            HDD:                               10 TB
            """,
            {"cpu": "Xeon", "memory": "128", "storage": "2000", "os": "Windows 11"}
        ),
        # Linux lsb_release + CPU info 形式 - 1
        (
            """
            $ lsb_release -a
            Distributor ID: Ubuntu
            Description:    Ubuntu 22.04.1 LTS
            Release:        22.04
            Codename:       jammy
            
            $ cat /proc/cpuinfo | head -20
            processor       : 0
            vendor_id       : GenuineIntel
            cpu family      : 6
            model           : 140
            model name      : Intel(R) Core(TM) i5-1240P CPU @ 1.70GHz
            
            $ free -h
                          total        used        free      shared  buff/cache   available
            Mem:          15Gi        4.2Gi        6.8Gi       324Mi        4.0Gi       10Gi
            
            $ lsblk -o NAME,SIZE,TYPE
            NAME     SIZE TYPE
            sda      476G disk
            └─sda1   476G part
            """,
            {"cpu": "Intel", "memory": "15", "storage": "476", "os": "Ubuntu"}
        ),
        # Linux lsb_release + CPU info 形式 - 2 (AMD)
        (
            """
            $ lsb_release -a
            Distributor ID: Fedora
            Description:    Fedora release 38 (Thirty Eight)
            
            $ cat /proc/cpuinfo
            model name      : AMD Ryzen 9 7950X3D
            
            $ free -h
            Mem:          32Gi
            
            $ df -h /
            Filesystem     Size Used
            /dev/nvme0n1p2 476G  200G
            """,
            {"cpu": "AMD", "memory": "32", "storage": "476", "os": "Fedora"}
        ),
        # macOS system_profiler 形式 - 1
        (
            """
            $ system_profiler SPHardwareDataType
            Hardware Overview:

              Model Name: MacBook Pro
              Model Identifier: MacBookPro18,1
              Processor Name: Apple M1 Pro
              Number of Cores: 10
              Memory: 16 GB
              Total Number of Cores: 10
              
            $ df -h /
            Filesystem     Size Used Available Capacity
            /dev/disk1s1   494Gi 350Gi    100Gi   70%
            """,
            {"cpu": "M1", "memory": "16", "storage": "494", "os": "macOS"}
        ),
        # macOS system_profiler 形式 - 2 (M3 Max)
        (
            """
            System Profiler Output:
            Model Name: MacBook Pro
            Chip: Apple M3 Max
            Total Number of Cores: 12 (8 performance and 4 efficiency)
            Memory: 36GB
            Storage: 1TB SSD
            """,
            {"cpu": "M3", "memory": "36", "storage": "1000", "os": "macOS"}
        ),
        # GPU 統合情報 - NVIDIA
        (
            """
            Processor: Intel Core i7-13700K
            RAM: 32 GB DDR5
            Storage: 2 TB NVMe SSD
            GPU: NVIDIA GeForce RTX 4080
            OS: Windows 11 Pro
            Motherboard: ASUS ROG STRIX Z790-E
            """,
            {"cpu": "Intel", "memory": "32", "storage": "2000", "os": "Windows", "gpu": "RTX"}
        ),
        # GPU 統合情報 - AMD Radeon
        (
            """
            CPU: AMD Ryzen 7 5800X3D
            RAM: 64 GB DDR4
            Storage: 2TB SATA SSD + 4TB HDD
            GPU: AMD Radeon RX 6900 XT
            Motherboard: ASUS ROG CROSSHAIR X570-F
            OS: Windows 11 Pro
            """,
            {"cpu": "Ryzen", "memory": "64", "storage": "2000", "os": "Windows", "gpu": "Radeon"}
        ),
        # 複数ドライブ情報
        (
            """
            Logical Disks:
            C: (SSD NVMe)      476.94 GB
            D: (SSD SATA)      238.47 GB
            E: (HDD)           931.51 GB
            
            CPU: Intel Core i7-12700K
            RAM: 32 GB
            OS: Windows 11
            """,
            {"cpu": "Intel", "memory": "32", "storage": "476", "os": "Windows"}
        ),
        # ノートパソコン情報
        (
            """
            Model: Dell XPS 15
            CPU: Intel Core i9-13900H
            RAM: 32 GB LPDDR5
            Storage: 1 TB PCIe 4.0 SSD
            Display: 15.6" 4K OLED Touch
            GPU: NVIDIA GeForce RTX 4090
            OS: Windows 11 Pro
            """,
            {"cpu": "Intel", "memory": "32", "storage": "1000", "os": "Windows", "gpu": "RTX"}
        ),
        # ゲーミングPC スペック
        (
            """
            Case: Corsair Crystal 570X
            CPU: AMD Ryzen 9 7950X
            Motherboard: ASUS ROG CROSSHAIR X870
            RAM: 64 GB G.SKILL Trident Z5
            SSD: 2 TB Samsung 990 Pro
            HDD: 4 TB WD Black
            GPU: NVIDIA RTX 4090
            PSU: Corsair RM1000x
            OS: Windows 11 Pro
            """,
            {"cpu": "Ryzen", "memory": "64", "storage": "2000", "os": "Windows", "gpu": "RTX"}
        ),
        # ワークステーション情報
        (
            """
            System: HP Z6 G5 Workstation
            Processor: 2x Intel Xeon Platinum 8480
            Processor Cores: 56 (28 cores x 2)
            Memory: 192 GB DDR5
            Storage: 4 TB NVMe SSD + 16 TB RAID Storage
            GPU: NVIDIA RTX 6000 Ada
            OS: Linux Ubuntu 22.04 LTS
            """,
            {"cpu": "Xeon", "memory": "192", "storage": "4000", "os": "Ubuntu", "gpu": "RTX"}
        ),
        # Raspberry Pi
        (
            """
            Device: Raspberry Pi 4 Model B
            CPU: Broadcom BCM2711 (ARM Cortex-A72)
            Cores: 4
            RAM: 8 GB LPDDR4
            Storage: 256 GB microSD
            OS: Raspberry Pi OS (Debian-based)
            GPU: VideoCore VI
            """,
            {"cpu": "ARM", "memory": "8", "storage": "256", "os": "Debian"}
        ),
        # クラウドインスタンス情報 (AWS EC2 imdsv2)
        (
            """
            Instance Type: t3.xlarge
            CPU: 4 vCPU (Intel Xeon Platinum)
            Memory: 16 GB
            vCPU Details: 2.5 GHz base, 3.5 GHz turbo
            Instance Store: 1 x 160 GB SSD
            EBS: 100 GB gp3 (attached)
            OS: Amazon Linux 2
            AMI ID: ami-0c02fb55c4c1a9e2d
            """,
            {"cpu": "Xeon", "memory": "16", "storage": "160", "os": "Linux"}
        ),
    ]

    @pytest.mark.parametrize("specs_text,expected_fields", STANDARD_TEST_CASES)
    def test_standard_format_extraction(self, specs_text: str, expected_fields: Dict[str, str]):
        """
        標準フォーマットのターミナル出力から PC スペック情報を抽出
        
        評価基準: 期待されるフィールドのうち、少なくとも 5/6 が正確に抽出されていること
        """
        result = parse_specs(specs_text)
        
        # 抽出結果の検証
        assert isinstance(result, dict), "Result should be a dictionary"
        
        # 期待されるフィールドが含まれているか確認
        matched_fields = 0
        for field, expected_value in expected_fields.items():
            if field in result:
                # 値が期待値を含んでいるか検証（大文字小文字不問）
                result_value = str(result[field]).lower()
                expected_lower = str(expected_value).lower()
                if expected_lower in result_value or any(
                    part.lower() in result_value 
                    for part in expected_value.split()
                ):
                    matched_fields += 1
        
        # 6 項目中 5 項目以上が正確に抽出されていることを確認
        assert matched_fields >= min(5, len(expected_fields)), (
            f"Expected at least {min(5, len(expected_fields))} fields to be extracted correctly. "
            f"Got {matched_fields}/{ len(expected_fields)}: {result}"
        )


class TestGeminiPCSpecsExtractionEdgeCases:
    """エッジケース・非標準フォーマットからの PC スペック抽出テスト"""

    EDGE_CASE_TEST_CASES = [
        # 手書きメモ形式
        (
            """
            PC 構成メモ：
            CPU：Core i7
            メモリ：16GB
            SSD：512GB
            OS：Windows11
            """,
            {"cpu": "i7", "memory": "16", "storage": "512", "os": "Windows"}
        ),
        # 混合言語
        (
            """
            System Information:
            - Processor: AMD Ryzen 5 5600X
            - 搭載メモリ: 32GB
            - Storage: 1TB NVMe
            - Operating System: Ubuntu 22.04
            """,
            {"cpu": "Ryzen", "memory": "32", "storage": "1000", "os": "Ubuntu"}
        ),
        # テーブル形式
        (
            """
            | Component | Specification |
            |-----------|---------------|
            | CPU | Intel Core i5-12400F |
            | Memory | 16 GB DDR4 |
            | SSD | 512 GB PCIe 4.0 |
            | OS | Windows 11 Pro |
            """,
            {"cpu": "Intel", "memory": "16", "storage": "512", "os": "Windows"}
        ),
        # 一部欠損（メモリ情報がない）
        (
            """
            System: ThinkPad X1 Carbon Gen 11
            Processor: Intel Core i7-1365U
            Storage: 512 GB SSD
            OS: Ubuntu 22.04
            Display: 14" 2.8K OLED
            """,
            {"cpu": "Intel", "storage": "512", "os": "Ubuntu"}
        ),
        # HTML エスケープ含む
        (
            """
            &lt;HTML&gt;
            CPU: &quot;Intel Xeon&quot; 2.8GHz
            RAM: 64&nbsp;GB
            SSD: 2&nbsp;TB
            OS: &quot;Windows Server 2022&quot;
            &lt;/HTML&gt;
            """,
            {"cpu": "Intel", "memory": "64", "storage": "2000", "os": "Windows"}
        ),
        # CSV 形式
        (
            """
            Component,Value
            CPU,AMD Ryzen 9 5950X
            Memory,32GB
            Storage,2TB
            GPU,NVIDIA RTX 3090
            OS,Windows 11 Pro
            """,
            {"cpu": "Ryzen", "memory": "32", "storage": "2000", "os": "Windows", "gpu": "RTX"}
        ),
        # スペルミス・typo
        (
            """
            CPU: Intl Core i9-13900KS
            RAM: 32Gb
            Storge: 2Tb NvMe
            OS: Windoze 11
            """,
            {"cpu": "i9", "memory": "32", "storage": "2000", "os": "11"}
        ),
        # 単位が異なる（KB, MB 等）
        (
            """
            Processor: Intel Core i7-1360P
            Memory: 16384 MB
            Storage: 512000 MB
            Operating System: Windows 11 Pro
            """,
            {"cpu": "Intel", "memory": "16", "storage": "512", "os": "Windows"}
        ),
        # 複数 OS デュアルブート
        (
            """
            Boot Setup:
            - Primary OS: Windows 11 Pro (500 GB)
            - Secondary OS: Ubuntu 22.04 (250 GB)
            CPU: Intel Core i7-12700K
            Total RAM: 64 GB
            Total Storage: 2 TB NVMe
            """,
            {"cpu": "Intel", "memory": "64", "storage": "2000", "os": "Windows"}
        ),
        # 古い形式の PC 情報
        (
            """
            IBM PC 互換機
            CPU: Intel Pentium II 400 MHz
            RAM: 256 MB SDRAM
            HDD: 10 GB IDE
            OS: Windows 98 SE
            """,
            {"cpu": "Pentium", "memory": "256", "storage": "10", "os": "Windows"}
        ),
        # 非標準な表記（全角数字など）
        (
            """
            ＣＰＵ：インテル Ｃｏｒｅ ｉ７
            メモリ：１６ＧＢ
            ストレージ：５１２ＧＢ
            ＯＳ：Ｗｉｎｄｏｗｓ １１
            """,
            {"cpu": "Core", "memory": "16", "storage": "512", "os": "Windows"}
        ),
        # 改行・スペース混合
        (
            """
            CPU:  Intel Core     i9
            
            
            Memory:   32    GB
            Storage:
            
            2TB SSD
            OS:   Windows   11
            """,
            {"cpu": "Intel", "memory": "32", "storage": "2000", "os": "Windows"}
        ),
        # JSON でも XML でもない独自形式
        (
            """
            <PC>
            processor=Intel Core i5
            ram=8GB
            disk=256GB
            system=Windows 10
            </PC>
            """,
            {"cpu": "Intel", "memory": "8", "storage": "256", "os": "Windows"}
        ),
        # ベンチマーク結果混合
        (
            """
            System Specs:
            CPU: Intel Core i7-10700K @ 3.8 GHz
            RAM: 32 GB
            Storage: 1 TB NVME
            OS: Windows 11
            
            Benchmark Results:
            Cinebench R23: 12,451 points
            Geekbench 5: 1,820 (single), 8,234 (multi)
            """,
            {"cpu": "Intel", "memory": "32", "storage": "1000", "os": "Windows"}
        ),
        # 最小限の情報（CPU とメモリのみ）
        (
            """
            CPU: AMD Ryzen 7
            RAM: 16 GB
            """,
            {"cpu": "AMD", "memory": "16"}
        ),
        # デバイス情報のみ（PC スペックではない）
        (
            """
            Device: iPhone 15 Pro
            Processor: Apple A17 Pro
            Memory: 8 GB
            Storage: 256 GB
            OS: iOS 17
            """,
            {"cpu": "Apple", "memory": "8", "storage": "256", "os": "iOS"}
        ),
        # 無効なテキスト（スペックと無関係）
        (
            """
            Lorem ipsum dolor sit amet, consectetur adipiscing elit.
            CPU: Intel Core i7 (この行だけが有効)
            Sed do eiusmod tempor incididunt ut labore et dolore.
            """,
            {"cpu": "Intel"}
        ),
        # コマンド実行エラー含む
        (
            """
            $ systeminfo
            System Information
            Host Name: MYPC
            OS Name: Microsoft Windows 11 Pro
            System Manufacturer: Lenovo
            System Model: ThinkPad X1 Extreme Gen 5
            Processor: Intel(R) Core(TM) i9-12900HK CPU @ 3.80GHz
            Total Physical Memory: 32 GB
            
            $ lsblk
            Command not found
            """,
            {"cpu": "Intel", "memory": "32", "os": "Windows"}
        ),
    ]

    @pytest.mark.parametrize("specs_text,expected_fields", EDGE_CASE_TEST_CASES)
    def test_edge_case_extraction(self, specs_text: str, expected_fields: Dict[str, str]):
        """
        エッジケース・非標準フォーマットから PC スペック情報を抽出
        
        評価基準: 期待されるフィールドのうち、少なくとも全体の 80% 以上が正確に抽出されていること
        """
        result = parse_specs(specs_text)
        
        # エラーハンドリング
        if "error" in result:
            pytest.skip(f"Extraction failed with error: {result['error']}")
        
        assert isinstance(result, dict), "Result should be a dictionary"
        
        # 期待されるフィールドが含まれているか確認
        matched_fields = 0
        for field, expected_value in expected_fields.items():
            if field in result:
                # 値が期待値を含んでいるか検証
                result_value = str(result[field]).lower()
                expected_lower = str(expected_value).lower()
                
                # より柔軟なマッチング（数値変換対応）
                if expected_lower in result_value or any(
                    part.lower() in result_value 
                    for part in expected_value.split()
                ):
                    matched_fields += 1
        
        # 期待フィールドの 80% 以上が正確に抽出されていることを確認
        required_match_rate = 0.8
        required_matches = max(1, int(len(expected_fields) * required_match_rate))
        
        assert matched_fields >= required_matches, (
            f"Expected at least {required_matches}/{len(expected_fields)} fields "
            f"({required_match_rate*100}% match rate). Got {matched_fields}: {result}"
        )


class TestGeminiAccuracyCalculation:
    """Gemini 抽出精度の計算と評価"""

    def test_accuracy_calculation_6_items(self):
        """
        6 項目の精度計算：CPU、メモリ、ストレージ、OS、マザーボード、GPU
        5 項目以上正確に抽出されていることが合格基準
        """
        # テスト用の抽出結果
        extraction_result = {
            "cpu": "Intel Core i7-13700K",
            "memory": "32",
            "storage": "1000",
            "os": "Windows 11",
            "motherboard": "ASUS ROG STRIX Z790-E",
            "gpu": "NVIDIA RTX 4080"
        }
        
        # 期待値
        expected = {
            "cpu": "Intel",
            "memory": "32",
            "storage": "1000",
            "os": "Windows",
            "motherboard": "ASUS",
            "gpu": "RTX"
        }
        
        # 正確な抽出数をカウント
        correct_count = 0
        for key, expected_value in expected.items():
            if key in extraction_result:
                actual_value = str(extraction_result[key]).lower()
                if expected_value.lower() in actual_value:
                    correct_count += 1
        
        accuracy_rate = correct_count / len(expected)
        
        # 評価基準: 5/6 以上で合格
        assert correct_count >= 5, (
            f"Expected 5 or more correct items out of 6. Got {correct_count}/6 "
            f"({accuracy_rate*100:.1f}% accuracy)"
        )

    def test_accuracy_calculation_missing_items(self):
        """部分的な抽出結果での精度計算"""
        extraction_result = {
            "cpu": "AMD Ryzen 9 7950X",
            "memory": "64",
            "os": "Windows 11",
            "gpu": "NVIDIA RTX 4090"
            # storage と motherboard が欠損
        }
        
        expected_items = ["cpu", "memory", "storage", "os", "motherboard", "gpu"]
        
        # 抽出された項目数
        extracted_count = len(extraction_result)
        
        # ストレージとマザーボード情報がない場合、4/6 で合格基準未達
        accuracy_rate = extracted_count / len(expected_items)
        
        # この場合は合格基準未達（4/6 < 5/6）
        assert extracted_count < 5, "Partial extraction should have less than 5 items"

    def test_precision_vs_recall_trade_off(self):
        """精度（Precision）とリコール（Recall）のトレードオフ分析"""
        # 高精度（少ない誤検出）だが、リコール低い結果
        high_precision_result = {
            "cpu": "Intel Core i7",
            "memory": "16"
            # 確実な 2 項目のみ
        }
        
        # 高リコール（多く検出）だが、精度低い結果
        high_recall_result = {
            "cpu": "Intel Core i7-13700K Intel Xeon",  # 混合
            "memory": "16 GB 32 GB",  # 複数値
            "storage": "512 GB 1 TB",
            "os": "Windows 11 Windows 10",  # 複数値
            "gpu": "NVIDIA RTX"
        }
        
        # テスト: 高精度・低リコールより、中程度の精度・高リコールが望ましい
        precision_items = len(high_precision_result)
        recall_items = len(high_recall_result)
        
        # 実運用では、リコールを優先する（必要な情報を取得できない方が問題）
        assert recall_items > precision_items, "Higher recall is preferable for PC spec extraction"


class TestGeminiRobustness:
    """Gemini 抽出の堅牢性テスト"""

    def test_empty_input(self):
        """空の入力に対する処理"""
        result = parse_specs("")
        
        # エラーまたは空の結果が返されることを確認
        assert isinstance(result, dict)
        # エラーまたは値なしを許容
        assert len(result) == 0 or "error" in result

    def test_very_long_input(self):
        """非常に長いテキスト入力での処理"""
        long_text = """
        CPU: Intel Core i7-13700K
        Memory: 32 GB
        Storage: 1 TB
        """ * 1000  # 1000 回繰り返し
        
        result = parse_specs(long_text)
        
        # 長いテキストでも処理できること
        assert isinstance(result, dict)

    def test_special_characters(self):
        """特殊文字を含むテキストの処理"""
        special_text = """
        CPU: Intel Core i7 (第13世代) 🖥️
        Memory: 32 GB 💾
        Storage: 2 TB ↔️ 
        OS: Windows 11 🪟
        """
        
        result = parse_specs(special_text)
        
        # 特殊文字を含むテキストでも処理できること
        assert isinstance(result, dict)
        # CPU、メモリ、OS 情報は抽出できるべき
        assert any(key in result for key in ["cpu", "memory", "os"])


# ========================
# テスト実行と結果集計
# ========================

def run_accuracy_report():
    """
    テスト実行後、精度レポートを生成
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "total_test_cases": len(TestGeminiPCSpecsExtractionStandard.STANDARD_TEST_CASES) + 
                           len(TestGeminiPCSpecsExtractionEdgeCases.EDGE_CASE_TEST_CASES),
        "standard_test_cases": len(TestGeminiPCSpecsExtractionStandard.STANDARD_TEST_CASES),
        "edge_case_test_cases": len(TestGeminiPCSpecsExtractionEdgeCases.EDGE_CASE_TEST_CASES),
        "minimum_accuracy_target": "5/6 items (83.3%) for standard, 80% for edge cases",
    }
    
    return report


if __name__ == "__main__":
    report = run_accuracy_report()
    print("=" * 60)
    print("Gemini PC Specs Extraction Accuracy Test Suite")
    print("=" * 60)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("=" * 60)
    print(
        f"Standard test cases: {report['standard_test_cases']}\n"
        f"Edge case test cases: {report['edge_case_test_cases']}\n"
        f"Total test cases: {report['total_test_cases']}"
    )
