"""
個人情報の匿名化ユーティリティ

ストレスチェック法の「個人情報保護」要件に対応:
- employee_hash の再ハッシュ（企業 → 実施機関への受け渡し時）
- 少人数グループのデータ抑制
- 出力データから直接識別子を除去
"""

import hashlib
import secrets
from typing import Any, Dict, List, Optional

import pandas as pd


class Anonymizer:
    """
    匿名化処理クラス

    使用例:
        anon = Anonymizer(salt="company-specific-secret")
        df_safe = anon.pseudonymize(df, id_col="employee_hash")
        df_safe = anon.suppress_small_groups(df_safe, group_col="department", min_n=10)
    """

    # 出力 CSV に含めてはいけない直接識別子カラム名
    DIRECT_IDENTIFIERS = frozenset([
        "name", "email", "phone", "address",
        "employee_id", "my_number",
    ])

    def __init__(self, salt: Optional[str] = None):
        """
        Parameters
        ----------
        salt : str, optional
            ハッシュ生成に使うソルト。Noneの場合はセッションごとのランダム値を使用。
        """
        self._salt = salt or secrets.token_hex(32)

    # ── 公開メソッド ────────────────────────────────────────────

    def pseudonymize(
        self, df: pd.DataFrame, id_col: str = "employee_hash"
    ) -> pd.DataFrame:
        """
        識別子カラムを再ハッシュして仮名化する

        Parameters
        ----------
        df : pd.DataFrame
        id_col : str
            仮名化対象カラム名

        Returns
        -------
        pd.DataFrame
            id_col が再ハッシュされた新しいDataFrame
        """
        df = df.copy()
        if id_col in df.columns:
            df[id_col] = df[id_col].apply(
                lambda v: self._rehash(str(v)) if pd.notna(v) else v
            )
        return df

    def remove_direct_identifiers(self, df: pd.DataFrame) -> pd.DataFrame:
        """直接識別子カラムをDataFrameから除去する"""
        cols_to_drop = [c for c in df.columns if c.lower() in self.DIRECT_IDENTIFIERS]
        return df.drop(columns=cols_to_drop, errors="ignore")

    def suppress_small_groups(
        self,
        df: pd.DataFrame,
        group_col: str = "department",
        min_n: int = 10,
        fill_value: Any = None,
        score_cols: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        少人数グループのスコア列を fill_value で置換する（個人特定防止）

        Parameters
        ----------
        df : pd.DataFrame
        group_col : str
        min_n : int
            この人数未満のグループを抑制
        fill_value : Any
            置換値（デフォルト None）
        score_cols : list[str], optional
            抑制対象カラム。Noneの場合は数値カラムをすべて対象とする。

        Returns
        -------
        pd.DataFrame
        """
        df = df.copy()
        if score_cols is None:
            score_cols = df.select_dtypes(include="number").columns.tolist()
            if group_col in score_cols:
                score_cols.remove(group_col)

        counts = df[group_col].value_counts()
        small_groups = counts[counts < min_n].index

        mask = df[group_col].isin(small_groups)
        df.loc[mask, score_cols] = fill_value
        return df

    def mask_high_stress_list(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        高ストレス者リストから部署・属性以外の情報を削除する
        （実施者（産業医等）向け出力用）
        """
        allowed_cols = {"employee_hash", "department", "high_stress_reason",
                        "raw_B_total", "raw_AC_total"}
        cols = [c for c in df.columns if c in allowed_cols]
        return df[cols].copy()

    # ── 内部メソッド ────────────────────────────────────────────

    def _rehash(self, value: str) -> str:
        """ソルト付きSHA-256で再ハッシュ"""
        return hashlib.sha256(
            f"{self._salt}:{value}".encode("utf-8")
        ).hexdigest()[:16]
