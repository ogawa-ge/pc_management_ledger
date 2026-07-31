"""
Excel データ移行スクリプト

既存の Excel ファイル（PC 台帳）から DynamoDB へのデータ移行を行うスクリプト
PC 管理台帳で管理されている既存データ（D-001～D-007、N-001～N-034 など）を
DynamoDB の PCs テーブルに移行します

使用方法:
    python migrate-excel-data.py --input <path-to-excel-file> [--dry-run]

前提条件:
    - AWS 認証情報が設定されていること
    - DynamoDB に PCs テーブルが存在すること
    - Excel ファイルが以下のカラムを持つこと:
      - 管理番号 (PC ID)
      - PC種別 (ノートパソコン/デスクトップパソコン)
      - ユーザーID (owner_id)
      - スペック情報（CPU、メモリなど）
      - ステータス (InUse, Unused, など)
      - 登録日
"""

import sys
import argparse
import json
import csv
import boto3
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

import openpyxl  # type: ignore


class ExcelDataMigrator:
    """Excel ファイルから DynamoDB へのデータ移行を管理するクラス"""

    def __init__(
        self,
        excel_file: str,
        dynamodb_table: str = "PCs",
        dry_run: bool = False,
    ):
        """
        ExcelDataMigrator を初期化します

        Args:
            excel_file (str): 移行対象の Excel ファイルパス
            dynamodb_table (str): 移行先の DynamoDB テーブル名
            dry_run (bool): ドライラン（実際の移行は行わない）
        """
        self.excel_file = Path(excel_file)
        self.dynamodb_table = dynamodb_table
        self.dry_run = dry_run

        if not self.excel_file.exists():
            raise FileNotFoundError(f"Excel file not found: {excel_file}")

        # DynamoDB クライアントを初期化
        self.dynamodb = boto3.resource("dynamodb")
        self.table = self.dynamodb.Table(self.dynamodb_table)

        self.migration_stats = {
            "total_records": 0,
            "migrated_records": 0,
            "failed_records": 0,
            "failed_details": [],
        }

    def _parse_pc_type(self, pc_type_str: str) -> str:
        """
        PC 種別文字列をシステム形式に変換します

        Args:
            pc_type_str (str): Excel の PC 種別文字列

        Returns:
            str: 正規化された PC 種別 ('N' または 'D')
        """
        if isinstance(pc_type_str, str):
            if "ノート" in pc_type_str or "Note" in pc_type_str or pc_type_str.upper() == "N":
                return "N"
            elif (
                "デスク" in pc_type_str
                or "Desktop" in pc_type_str
                or pc_type_str.upper() == "D"
            ):
                return "D"

        # デフォルトはノートパソコン
        return "N"

    def _parse_status(self, status_str: str) -> str:
        """
        ステータス文字列をシステム形式に変換します

        Args:
            status_str (str): Excel のステータス文字列

        Returns:
            str: 正規化されたステータス
        """
        if isinstance(status_str, str):
            status_upper = status_str.upper().strip()
            if "使用中" in status_upper or "IN USE" in status_upper:
                return "InUse"
            elif "未使用" in status_upper or "UNUSED" in status_upper:
                return "Unused"
            elif "廃棄待ち" in status_upper or "PENDING" in status_upper:
                return "PendingDisposal"
            elif "廃棄済み" in status_upper or "DISPOSED" in status_upper:
                return "Disposed"

        # デフォルトは未使用
        return "Unused"

    def _parse_registration_date(self, date_value: Any) -> str:
        """
        登録日をタイムスタンプに変換します

        Args:
            date_value: Excel の日付値

        Returns:
            str: ISO8601 形式のタイムスタンプ
        """
        if isinstance(date_value, datetime):
            return date_value.isoformat()
        elif isinstance(date_value, str):
            try:
                # 複数の日付形式を試す
                for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%m/%d/%Y"]:
                    try:
                        dt = datetime.strptime(date_value.strip(), fmt)
                        return dt.isoformat()
                    except ValueError:
                        continue
            except Exception:
                pass

        # デフォルトは現在時刻
        return datetime.utcnow().isoformat()

    def _extract_row_data(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Excel 行データを DynamoDB PC エントリに変換します

        Args:
            row (Dict[str, Any]): Excel の行データ

        Returns:
            Optional[Dict[str, Any]]: 変換後の PC データ、またはエラーの場合は None
        """
        try:
            # 必須フィールドの確認
            pc_id = row.get("管理番号") or row.get("PC ID")
            if not pc_id:
                return None

            pc_type = self._parse_pc_type(row.get("PC種別", "N"))
            owner_id = row.get("ユーザーID") or row.get("owner_id")
            specs = row.get("スペック情報", "")
            status = self._parse_status(row.get("ステータス", "Unused"))
            registration_date = self._parse_registration_date(
                row.get("登録日", datetime.utcnow())
            )

            # DynamoDB エントリを作成
            pc_entry = {
                "pcId": str(pc_id).strip(),
                "pcType": pc_type,
                "status": status,
                "createdAt": registration_date,
                "updatedAt": datetime.utcnow().isoformat(),
            }

            # オプショナルフィールド
            if owner_id:
                pc_entry["ownerId"] = str(owner_id).strip()

            if specs:
                pc_entry["specs"] = str(specs).strip()

            # メモフィールド（キャパシティプランニング）
            pc_entry["migrationNote"] = "Excel データから移行"

            return pc_entry

        except Exception as e:
            print(f"Error extracting row data: {str(e)}")
            return None

    def load_from_excel(self) -> List[Dict[str, Any]]:
        """
        Excel ファイルからデータを読み込みます

        Returns:
            List[Dict[str, Any]]: 読み込んだデータのリスト
        """
        try:
            workbook = openpyxl.load_workbook(str(self.excel_file))
            worksheet = workbook.active

            if not worksheet:
                raise ValueError("Excel ファイルにシートが見つかりません")

            # ヘッダー行を取得
            headers = []
            for cell in worksheet[1]:
                headers.append(cell.value)

            # データ行を読み込む
            records = []
            for row_idx, row in enumerate(
                worksheet.iter_rows(min_row=2, values_only=False), start=2
            ):
                row_data = {}
                for col_idx, cell in enumerate(row):
                    if col_idx < len(headers):
                        row_data[headers[col_idx]] = cell.value

                records.append(row_data)

            return records

        except Exception as e:
            print(f"Excel ファイル読み込みエラー: {str(e)}")
            raise

    def load_from_json(self) -> List[Dict[str, Any]]:
        """
        JSON ファイルからデータを読み込みます

        Returns:
            List[Dict[str, Any]]: 読み込んだデータのリスト
        """
        try:
            with open(self.excel_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "records" in data:
                    return data["records"]
                else:
                    raise ValueError("予期しない JSON 形式です")
        except Exception as e:
            print(f"JSON ファイル読み込みエラー: {str(e)}")
            raise

    def load_from_csv(self) -> List[Dict[str, Any]]:
        """
        CSV ファイルからデータを読み込みます

        Returns:
            List[Dict[str, Any]]: 読み込んだデータのリスト
        """
        try:
            records = []
            with open(self.excel_file, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row:
                        records.append(row)
            return records
        except Exception as e:
            print(f"CSV ファイル読み込みエラー: {str(e)}")
            raise

    def load_data(self) -> List[Dict[str, Any]]:
        """
        ファイル形式に応じてデータを読み込みます

        Returns:
            List[Dict[str, Any]]: 読み込んだデータのリスト
        """
        file_ext = self.excel_file.suffix.lower()

        if file_ext in [".xlsx", ".xls"]:
            return self.load_from_excel()
        elif file_ext == ".json":
            return self.load_from_json()
        elif file_ext == ".csv":
            return self.load_from_csv()
        else:
            raise ValueError(f"サポートされていないファイル形式: {file_ext}")

    def migrate(self) -> Dict[str, Any]:
        """
        データを DynamoDB に移行します

        Returns:
            Dict[str, Any]: 移行結果の統計
        """
        print(f"\n{'='*60}")
        print("PC 管理台帳データ移行スクリプト")
        print(f"{'='*60}\n")

        print(f"Excel ファイル: {self.excel_file}")
        print(f"移行先テーブル: {self.dynamodb_table}")
        print(f"ドライラン: {self.dry_run}\n")

        # データを読み込む
        print("ファイルからデータを読み込み中...")
        try:
            raw_records = self.load_data()
        except Exception as e:
            print(f"エラー: {str(e)}")
            return self.migration_stats

        self.migration_stats["total_records"] = len(raw_records)
        print(f"読み込んだレコード数: {len(raw_records)}\n")

        # データを変換
        print("レコードを変換中...")
        converted_records = []
        for idx, raw_record in enumerate(raw_records, start=1):
            pc_data = self._extract_row_data(raw_record)
            if pc_data:
                converted_records.append(pc_data)
                print(
                    f"  ✓ {pc_data.get('pcId')} ({pc_data.get('pcType')}) - 変換完了"
                )
            else:
                self.migration_stats["failed_records"] += 1
                self.migration_stats["failed_details"].append(
                    f"Row {idx}: Could not extract PC ID"
                )
                print(f"  ✗ Row {idx} - 変換失敗")

        print(f"\n変換完了: {len(converted_records)} レコード\n")

        if self.dry_run:
            print("[ドライラン] DynamoDB への書き込みをスキップします\n")
            self.migration_stats["migrated_records"] = len(converted_records)
            self._print_sample_records(converted_records[:3])
        else:
            # DynamoDB に書き込む
            print("DynamoDB に書き込み中...")
            for record in converted_records:
                try:
                    self.table.put_item(Item=record)
                    self.migration_stats["migrated_records"] += 1
                    print(f"  ✓ {record['pcId']} - 書き込み完了")
                except Exception as e:
                    self.migration_stats["failed_records"] += 1
                    self.migration_stats["failed_details"].append(
                        f"{record.get('pcId')}: {str(e)}"
                    )
                    print(f"  ✗ {record['pcId']} - 書き込み失敗: {str(e)}")

        # 統計情報を表示
        self._print_statistics()

        return self.migration_stats

    def _print_sample_records(self, records: List[Dict[str, Any]]) -> None:
        """
        サンプルレコードを表示します

        Args:
            records (List[Dict[str, Any]]): サンプルレコード
        """
        print("[サンプルレコード（最初の 3 件）]")
        for record in records:
            print(f"\n{json.dumps(record, indent=2, ensure_ascii=False)}")

    def _print_statistics(self) -> None:
        """
        移行統計を表示します
        """
        print(f"\n{'='*60}")
        print("移行統計")
        print(f"{'='*60}")
        print(f"総レコード数: {self.migration_stats['total_records']}")
        print(f"移行成功: {self.migration_stats['migrated_records']}")
        print(f"移行失敗: {self.migration_stats['failed_records']}")

        if self.migration_stats["failed_details"]:
            print(f"\n失敗詳細:")
            for detail in self.migration_stats["failed_details"][:10]:
                print(f"  - {detail}")

        success_rate = (
            (
                self.migration_stats["migrated_records"]
                / self.migration_stats["total_records"]
            )
            * 100
            if self.migration_stats["total_records"] > 0
            else 0
        )
        print(f"\n成功率: {success_rate:.1f}%\n")


def main():
    """
    スクリプトのメインエントリーポイント
    """
    parser = argparse.ArgumentParser(
        description="PC 管理台帳データの Excel から DynamoDB への移行スクリプト"
    )
    parser.add_argument(
        "--input",
        "-i",
        type=str,
        required=True,
        help="入力ファイルパス（Excel/CSV/JSON）",
    )
    parser.add_argument(
        "--table",
        "-t",
        type=str,
        default="PCs",
        help="DynamoDB テーブル名（デフォルト: PCs）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="ドライラン（実際の書き込みは行わない）",
    )

    args = parser.parse_args()

    try:
        migrator = ExcelDataMigrator(
            excel_file=args.input,
            dynamodb_table=args.table,
            dry_run=args.dry_run,
        )
        stats = migrator.migrate()

        # 統計情報に基づいて終了コードを決定
        exit_code = 0 if stats["failed_records"] == 0 else 1
        sys.exit(exit_code)

    except Exception as e:
        print(f"エラー: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
