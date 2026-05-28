#!/usr/bin/env python3
"""
Gemini PC スペック抽出精度計算スクリプト

このスクリプトは、Gemini API による PC スペック抽出の精度を計算します。
6 項目（CPU、メモリ、ストレージ、OS、マザーボード、GPU）中 5 項目以上が
正確に抽出されていることを合格基準とします。

使用方法：
    python test-gemini-accuracy.py [--verbose] [--json-output result.json]
"""

import json
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum


class MatchLevel(Enum):
    """マッチレベルの定義"""
    EXACT = "exact"           # 完全一致
    PARTIAL = "partial"       # 部分一致
    FUZZY = "fuzzy"           # ファジーマッチ（主要キーワード含む）
    NOT_FOUND = "not_found"   # 未検出


@dataclass
class ExtractionItem:
    """抽出項目の詳細情報"""
    field_name: str
    expected_value: str
    extracted_value: str
    match_level: MatchLevel
    confidence: float


@dataclass
class TestCaseResult:
    """テストケースの実行結果"""
    test_id: str
    input_format: str
    extracted_items: Dict[str, Any]
    matched_items: int
    total_items: int
    accuracy_rate: float
    passed: bool
    details: List[ExtractionItem]


class GeminiAccuracyCalculator:
    """Gemini 精度計算エンジン"""

    # 必須 6 項目
    REQUIRED_ITEMS = {
        "cpu": ["Intel", "AMD", "Apple", "ARM", "Xeon", "Ryzen", "Core", "Pentium"],
        "memory": ["GB", "MB", "TB"],
        "storage": ["GB", "TB", "SSD", "HDD"],
        "os": ["Windows", "Ubuntu", "Fedora", "macOS", "iOS", "Linux", "Debian"],
        "motherboard": ["ASUS", "MSI", "Gigabyte", "ASRock", "Lenovo", "Dell", "HP"],
        "gpu": ["NVIDIA", "RTX", "GTX", "AMD", "Radeon", "Apple", "Intel", "Xe"]
    }

    PASS_THRESHOLD = 5  # 5/6 以上で合格

    def __init__(self, verbose: bool = False):
        """
        初期化

        Args:
            verbose (bool): 詳細ログ出力フラグ
        """
        self.verbose = verbose
        self.test_results: List[TestCaseResult] = []

    def calculate_match_level(
        self,
        field_name: str,
        expected_value: str,
        extracted_value: str
    ) -> Tuple[MatchLevel, float]:
        """
        2 つの値のマッチレベルと信度を計算

        Args:
            field_name (str): フィールド名
            expected_value (str): 期待値
            extracted_value (str): 抽出値

        Returns:
            Tuple[MatchLevel, float]: (マッチレベル, 信度スコア)
        """
        if not extracted_value:
            return MatchLevel.NOT_FOUND, 0.0

        # 値を正規化
        expected_lower = str(expected_value).lower().strip()
        extracted_lower = str(extracted_value).lower().strip()

        # EXACT: 完全一致
        if expected_lower == extracted_lower:
            return MatchLevel.EXACT, 1.0

        # PARTIAL: 期待値が抽出値に含まれている
        if expected_lower in extracted_lower:
            # 信度は包含度に応じて調整
            confidence = len(expected_lower) / len(extracted_lower)
            return MatchLevel.PARTIAL, min(1.0, confidence)

        # FUZZY: 主要キーワードが含まれている
        field_keywords = self.REQUIRED_ITEMS.get(field_name, [])
        for keyword in field_keywords:
            if keyword.lower() in extracted_lower:
                # キーワードが複数含まれている場合は信度高
                keyword_count = sum(
                    extracted_lower.count(kw.lower()) 
                    for kw in field_keywords 
                    if kw.lower() in extracted_lower
                )
                confidence = min(1.0, keyword_count * 0.3)
                return MatchLevel.FUZZY, confidence

        # NOT_FOUND: マッチしない
        return MatchLevel.NOT_FOUND, 0.0

    def evaluate_extraction(
        self,
        test_id: str,
        input_format: str,
        extracted_items: Dict[str, Any],
        expected_items: Dict[str, str]
    ) -> TestCaseResult:
        """
        抽出結果を評価

        Args:
            test_id (str): テスト ID
            input_format (str): 入力フォーマット
            extracted_items (Dict[str, Any]): 抽出結果
            expected_items (Dict[str, str]): 期待値

        Returns:
            TestCaseResult: 評価結果
        """
        details: List[ExtractionItem] = []
        matched_count = 0

        for field_name, expected_value in expected_items.items():
            extracted_value = extracted_items.get(field_name, "")

            match_level, confidence = self.calculate_match_level(
                field_name, expected_value, extracted_value
            )

            # 信度が 0.7 以上の場合をマッチ扱い
            is_matched = confidence >= 0.7

            item = ExtractionItem(
                field_name=field_name,
                expected_value=expected_value,
                extracted_value=str(extracted_value),
                match_level=match_level,
                confidence=confidence
            )
            details.append(item)

            if is_matched:
                matched_count += 1

            if self.verbose:
                print(
                    f"  [{field_name}] {match_level.value} "
                    f"(confidence: {confidence:.2f}) "
                    f"Expected: '{expected_value}', Got: '{extracted_value}'"
                )

        # 評価結果を集計
        total_items = len(expected_items)
        accuracy_rate = matched_count / total_items if total_items > 0 else 0.0
        passed = matched_count >= self.PASS_THRESHOLD

        result = TestCaseResult(
            test_id=test_id,
            input_format=input_format,
            extracted_items=extracted_items,
            matched_items=matched_count,
            total_items=total_items,
            accuracy_rate=accuracy_rate,
            passed=passed,
            details=details
        )

        self.test_results.append(result)
        return result

    def generate_report(self) -> Dict[str, Any]:
        """
        精度レポートを生成

        Returns:
            Dict[str, Any]: レポート辞書
        """
        if not self.test_results:
            return {"status": "No test results"}

        passed_tests = sum(1 for r in self.test_results if r.passed)
        total_tests = len(self.test_results)
        total_matched = sum(r.matched_items for r in self.test_results)
        total_items = sum(r.total_items for r in self.test_results)

        # 各フィールドの成功率
        field_success_rates: Dict[str, float] = {}
        field_counts: Dict[str, int] = {}

        for result in self.test_results:
            for detail in result.details:
                if detail.field_name not in field_counts:
                    field_counts[detail.field_name] = 0
                    field_success_rates[detail.field_name] = 0
                
                field_counts[detail.field_name] += 1
                if detail.confidence >= 0.7:
                    field_success_rates[detail.field_name] += 1

        # パーセンテージに変換
        for field in field_success_rates:
            if field_counts[field] > 0:
                field_success_rates[field] /= field_counts[field]

        # 成功率分布
        accuracy_distribution = {
            "100%": sum(1 for r in self.test_results if r.matched_items == 6),
            "83%": sum(1 for r in self.test_results if r.matched_items == 5),
            "67%": sum(1 for r in self.test_results if r.matched_items == 4),
            "50%": sum(1 for r in self.test_results if r.matched_items == 3),
            "Below 50%": sum(1 for r in self.test_results if r.matched_items < 3),
        }

        report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "pass_rate": f"{(passed_tests / total_tests * 100):.1f}%",
                "overall_accuracy": f"{(total_matched / total_items * 100):.1f}%",
                "matched_items": total_matched,
                "total_items": total_items,
            },
            "pass_threshold": f"{self.PASS_THRESHOLD}/{6} items required",
            "field_success_rates": {
                field: f"{(rate * 100):.1f}%"
                for field, rate in field_success_rates.items()
            },
            "accuracy_distribution": accuracy_distribution,
            "test_results": [
                {
                    "test_id": r.test_id,
                    "input_format": r.input_format,
                    "matched_items": r.matched_items,
                    "total_items": r.total_items,
                    "accuracy": f"{(r.accuracy_rate * 100):.1f}%",
                    "passed": r.passed,
                    "details": [
                        {
                            "field": d.field_name,
                            "expected": d.expected_value,
                            "extracted": d.extracted_value,
                            "match": d.match_level.value,
                            "confidence": f"{(d.confidence * 100):.1f}%"
                        }
                        for d in r.details
                    ]
                }
                for r in self.test_results
            ]
        }

        return report

    def print_summary(self, report: Dict[str, Any]) -> None:
        """
        サマリーをコンソールに出力

        Args:
            report (Dict[str, Any]): レポート辞書
        """
        print("\n" + "=" * 70)
        print("Gemini PC Specs Extraction Accuracy Report")
        print("=" * 70)
        print(f"Timestamp: {report['timestamp']}")
        print()

        summary = report["summary"]
        print("Summary:")
        print(f"  Total Tests: {summary['total_tests']}")
        print(f"  Passed: {summary['passed_tests']}")
        print(f"  Failed: {summary['failed_tests']}")
        print(f"  Pass Rate: {summary['pass_rate']}")
        print(f"  Overall Accuracy: {summary['overall_accuracy']}")
        print(f"  Matched Items: {summary['matched_items']}/{summary['total_items']}")
        print()

        print("Pass Threshold: " + report["pass_threshold"])
        print()

        print("Field Success Rates:")
        for field, rate in report["field_success_rates"].items():
            print(f"  {field:15} {rate}")
        print()

        print("Accuracy Distribution:")
        for accuracy, count in report["accuracy_distribution"].items():
            print(f"  {accuracy:12} {count} tests")
        print()

        print("=" * 70)


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description="Gemini PC Specs Extraction Accuracy Calculator"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--json-output", "-o",
        type=str,
        help="Output results as JSON to specified file"
    )

    args = parser.parse_args()

    # 計算エンジンを初期化
    calculator = GeminiAccuracyCalculator(verbose=args.verbose)

    # テストケース例（実際はテストスイートから生成）
    test_cases = [
        {
            "test_id": "standard_windows_001",
            "input_format": "Windows systeminfo",
            "extracted": {
                "cpu": "Intel Core i7-13700K",
                "memory": "32",
                "storage": "1000",
                "os": "Windows 11",
                "motherboard": "ASUS ROG",
                "gpu": "NVIDIA RTX 4080"
            },
            "expected": {
                "cpu": "Intel",
                "memory": "32",
                "storage": "1000",
                "os": "Windows",
                "motherboard": "ASUS",
                "gpu": "RTX"
            }
        },
        {
            "test_id": "edge_case_typo_001",
            "input_format": "Manual notes with typos",
            "extracted": {
                "cpu": "Intl Core i9",
                "memory": "32Gb",
                "storage": "2Tb",
                "os": "Windoze 11"
            },
            "expected": {
                "cpu": "Intel",
                "memory": "32",
                "storage": "2000",
                "os": "Windows"
            }
        },
    ]

    # テストを実行
    print("Running accuracy tests...")
    for test_case in test_cases:
        result = calculator.evaluate_extraction(
            test_id=test_case["test_id"],
            input_format=test_case["input_format"],
            extracted_items=test_case["extracted"],
            expected_items=test_case["expected"]
        )
        if args.verbose:
            print(
                f"Test {result.test_id}: "
                f"{result.matched_items}/{result.total_items} "
                f"({'PASS' if result.passed else 'FAIL'})"
            )

    # レポートを生成
    report = calculator.generate_report()

    # コンソールに出力
    calculator.print_summary(report)

    # JSON 出力
    if args.json_output:
        with open(args.json_output, 'w', encoding='utf-8') as f:
            # ExtractionItem と TestCaseResult を JSON シリアライズ可能にする
            json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\nResults saved to {args.json_output}")

    # 終了コード
    passed_tests = report["summary"]["passed_tests"]
    total_tests = report["summary"]["total_tests"]
    return 0 if passed_tests == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
