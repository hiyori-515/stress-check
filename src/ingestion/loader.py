"""
ストレスチェック CSVローダー・バリデーター

入力形式：
  - Googleフォーム等からエクスポートしたCSV
  - 必須カラム：employee_hash, department, q1〜q57（最低限）
  - 拡張カラム：q58〜q132（80項目版・120項目版）
"""

import pandas as pd
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from config.scoring_rules import ALL_ITEMS, ITEMS_80, ITEMS_120

logger = logging.getLogger(__name__)


class ResponseLoader:
    """
    ストレスチェック回答CSVの読み込みとバリデーション
    """

    # バージョンごとに必須の項目番号セット
    REQUIRED_ITEMS = {
        "120": ITEMS_120,
        "80":  ITEMS_80,
        "57":  set(range(1, 58)),
    }

    # 許容する回答値
    VALID_RESPONSES = {1, 2, 3, 4}

    def __init__(self, version: str = "120", company_id: str = "UNKNOWN"):
        if version not in self.REQUIRED_ITEMS:
            raise ValueError(f"version は '120', '80', '57' のいずれか")
        self.version = version
        self.company_id = company_id
        self.required = self.REQUIRED_ITEMS[version]

    def load(self, filepath: str) -> Tuple[pd.DataFrame, List[str]]:
        """
        CSVを読み込み、バリデーションを行う

        Returns
        -------
        (df_clean, errors)
            df_clean : バリデーション済みデータフレーム
            errors   : エラーメッセージリスト（空なら問題なし）
        """
        errors = []
        path = Path(filepath)

        if not path.exists():
            return pd.DataFrame(), [f"ファイルが見つかりません: {filepath}"]

        # 拡張子で読み込み方法を切り替え
        try:
            if path.suffix.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(filepath)
            else:
                df = pd.read_csv(filepath, encoding="utf-8-sig")
        except Exception as e:
            return pd.DataFrame(), [f"ファイル読み込みエラー: {e}"]

        logger.info(f"読み込み完了: {filepath} ({len(df)}行)")

        # カラム名を正規化
        df = self._normalize_columns(df)

        # 必須メタカラムのチェック
        meta_errors = self._check_meta_columns(df)
        errors.extend(meta_errors)

        # 回答項目カラムのチェック
        item_errors = self._check_item_columns(df)
        errors.extend(item_errors)

        if errors:
            return df, errors

        # 回答値のバリデーション（1〜4以外を欠損に変換）
        df, value_warnings = self._validate_response_values(df)
        for w in value_warnings:
            logger.warning(w)

        # employee_hashが未指定の場合、行番号からハッシュ生成
        if "employee_hash" not in df.columns:
            df["employee_hash"] = [
                self._generate_hash(f"{self.company_id}_{i}")
                for i in range(len(df))
            ]

        return df, errors

    def to_response_dicts(self, df: pd.DataFrame) -> List[Dict]:
        """
        DataFrameを1行1人の回答辞書リストに変換

        Returns
        -------
        list of dict
            [{"employee_hash": str, "department": str,
              "responses": {1: int, 2: int, ...}, "meta": {...}}, ...]
        """
        records = []
        q_cols = self._get_question_columns(df)

        for _, row in df.iterrows():
            responses = {}
            for col in q_cols:
                q_num = int(col[1:])  # "q1" → 1
                val = row[col]
                if pd.notna(val) and int(val) in self.VALID_RESPONSES:
                    responses[q_num] = int(val)

            meta = {
                "department":       row.get("department", ""),
                "gender":           row.get("gender", ""),
                "age_group":        row.get("age_group", ""),
                "employment_type":  row.get("employment_type", ""),
                "years_of_service": row.get("years_of_service", ""),
                "response_date":    row.get("response_date", ""),
            }

            records.append({
                "employee_hash": row.get("employee_hash", ""),
                "responses": responses,
                "meta": meta,
            })

        return records

    # ──────────────────────────────────────────────────────
    # 内部メソッド
    # ──────────────────────────────────────────────────────

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """カラム名を小文字・スペース除去で正規化"""
        df.columns = [str(c).lower().strip().replace(" ", "_") for c in df.columns]
        return df

    def _check_meta_columns(self, df: pd.DataFrame) -> List[str]:
        """必須メタカラムの存在確認"""
        errors = []
        required_meta = ["department"]  # departmentは最低限必須
        for col in required_meta:
            if col not in df.columns:
                errors.append(f"必須カラムがありません: {col}")
        return errors

    def _check_item_columns(self, df: pd.DataFrame) -> List[str]:
        """回答項目カラムの確認"""
        errors = []
        missing_cols = []
        for q_num in sorted(self.required):
            col = f"q{q_num}"
            if col not in df.columns:
                missing_cols.append(col)

        if missing_cols:
            errors.append(
                f"{self.version}項目版に必要なカラムが不足しています: "
                f"{missing_cols[:10]}{'...' if len(missing_cols) > 10 else ''}"
                f"（計{len(missing_cols)}件）"
            )
        return errors

    def _validate_response_values(
        self, df: pd.DataFrame
    ) -> Tuple[pd.DataFrame, List[str]]:
        """回答値が1〜4の範囲外の場合にNaNに変換"""
        warnings = []
        q_cols = self._get_question_columns(df)

        for col in q_cols:
            invalid_mask = ~df[col].isin([1, 2, 3, 4]) & df[col].notna()
            n_invalid = invalid_mask.sum()
            if n_invalid > 0:
                warnings.append(f"{col}: {n_invalid}件の無効値をNaNに変換")
                df.loc[invalid_mask, col] = None

        return df, warnings

    def _get_question_columns(self, df: pd.DataFrame) -> List[str]:
        """DataFrameからq+数字のカラムを抽出"""
        return [
            c for c in df.columns
            if c.startswith("q") and c[1:].isdigit()
            and int(c[1:]) in ALL_ITEMS
        ]

    @staticmethod
    def _generate_hash(seed: str) -> str:
        """識別子からハッシュIDを生成"""
        return hashlib.sha256(seed.encode()).hexdigest()[:16]


# ──────────────────────────────────────────────────────────
# サンプルCSV生成（テスト用）
# ──────────────────────────────────────────────────────────
def generate_sample_csv(
    output_path: str,
    version: str = "120",
    n_respondents: int = 20,
    departments: Optional[List[str]] = None,
    seed: int = 42,
) -> str:
    """
    テスト用のサンプル回答CSVを生成する

    Parameters
    ----------
    output_path : str
        出力先パス
    version : str
        "120" / "80" / "57"
    n_respondents : int
        回答者数
    departments : list
        部署名リスト（Noneの場合はデフォルト使用）
    seed : int
        乱数シード
    """
    import random
    random.seed(seed)

    if departments is None:
        departments = ["営業部", "開発部", "管理部", "製造部"]

    required_items = {
        "120": ITEMS_120,
        "80":  ITEMS_80,
        "57":  set(range(1, 58)),
    }[version]

    rows = []
    for i in range(n_respondents):
        row = {
            "employee_hash": hashlib.sha256(f"test_{i}".encode()).hexdigest()[:16],
            "department":    random.choice(departments),
            "gender":        random.choice(["M", "F"]),
            "age_group":     random.choice(["20s", "30s", "40s", "50s"]),
            "employment_type": random.choice(["full", "part"]),
            "years_of_service": random.choice(["1y", "3y", "5y", "10y"]),
            "response_date": "2025-10-15",
        }
        for q_num in sorted(required_items):
            row[f"q{q_num}"] = random.randint(1, 4)
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"サンプルCSV生成: {output_path} ({n_respondents}名, {version}項目版)")
    return output_path


if __name__ == "__main__":
    import tempfile

    # サンプルCSV生成 → 読み込みテスト
    for version in ["120", "80", "57"]:
        with tempfile.NamedTemporaryFile(
            suffix=".csv", delete=False, mode="w"
        ) as f:
            tmp_path = f.name

        generate_sample_csv(tmp_path, version=version, n_respondents=15)

        loader = ResponseLoader(version=version, company_id="TEST-001")
        df, errors = loader.load(tmp_path)

        print(f"\n▼ {version}項目版 ローダーテスト")
        print(f"  行数: {len(df)}")
        print(f"  エラー: {errors if errors else 'なし'}")

        if not errors:
            records = loader.to_response_dicts(df)
            print(f"  変換レコード数: {len(records)}")
            sample = records[0]
            print(f"  サンプル回答項目数: {len(sample['responses'])}")

        os.unlink(tmp_path)

    print("\n✅ ローダーテスト完了")
