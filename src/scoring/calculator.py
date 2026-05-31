"""
ストレスチェック スコアリングエンジン
Phase 1: 個人スコア計算 + 高ストレス者判定

対応バージョン：
  - 120項目版（新職業性ストレス簡易調査票 推奨尺度セット標準版）
  - 80項目版（新職業性ストレス簡易調査票 推奨尺度セット短縮版）
  - 57項目版（職業性ストレス簡易調査票）
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from config.scoring_rules import (
    ALL_ITEMS, SCALES, ITEMS_80, ITEMS_120,
    HIGH_STRESS_RAW, NATIONAL_AVERAGES, VERSIONS
)
from typing import Dict, Optional, Tuple
import math


class StressCheckScorer:
    """
    ストレスチェック スコアリングエンジン

    使用方法:
        scorer = StressCheckScorer(version="120")
        result = scorer.calculate(responses)
        print(result["high_stress"])
    """

    def __init__(self, version: str = "120"):
        """
        Parameters
        ----------
        version : str
            "120" / "80" / "57"
        """
        if version not in VERSIONS:
            raise ValueError(f"versionは '120', '80', '57' のいずれかを指定してください")
        self.version = version
        self.mode = VERSIONS[version]["mode"]

    # ──────────────────────────────────────────────────────
    # 公開メソッド
    # ──────────────────────────────────────────────────────

    def calculate(self, responses: Dict[int, int]) -> Dict:
        """
        個人の回答データからスコアを計算する

        Parameters
        ----------
        responses : dict
            {項目番号: 回答値(1-4)} の辞書
            例: {1: 2, 2: 3, 3: 1, ...}

        Returns
        -------
        dict
            {
              "version": "120",
              "valid": True/False,
              "missing_items": [欠損項目番号リスト],
              "item_scores": {項目番号: 換算後スコア},
              "scale_scores": {尺度名: 尺度得点(1-4)},
              "domain_scores": {"A": float, "B": float, "C": float},
              "high_stress": True/False,
              "high_stress_reason": "㋐" / "㋑" / None,
              "raw_B_total": int,    # 高ストレス判定用（元スコア）
              "raw_AC_total": int,
            }
        """
        # 1. バリデーション
        required = self._get_required_items()
        missing = [q for q in required if q not in responses]
        valid = len(missing) == 0

        # 2. 項目スコアの換算
        item_scores = self._convert_item_scores(responses)

        # 3. 尺度得点の計算
        scale_scores = self._calc_scale_scores(item_scores)

        # 4. 高ストレス判定（57項目部分のみ）
        raw_B, raw_AC = self._calc_raw_totals_for_highstress(responses)
        high_stress, reason = self._judge_high_stress(raw_B, raw_AC)

        # 5. 領域別合計（参考値）
        domain_scores = self._calc_domain_scores(scale_scores)

        return {
            "version": self.version,
            "valid": valid,
            "missing_items": missing,
            "item_scores": item_scores,
            "scale_scores": scale_scores,
            "domain_scores": domain_scores,
            "high_stress": high_stress,
            "high_stress_reason": reason,
            "raw_B_total": raw_B,
            "raw_AC_total": raw_AC,
        }

    def compare_to_national(self, scale_scores: Dict[str, float]) -> Dict[str, Dict]:
        """
        全国平均との比較（集団分析用）

        Returns
        -------
        dict
            {尺度名: {"score": float, "national_mean": float,
                      "diff": float, "z_score": float, "level": str}}
        """
        result = {}
        for scale_name, score in scale_scores.items():
            if scale_name not in NATIONAL_AVERAGES:
                continue
            nat = NATIONAL_AVERAGES[scale_name]
            diff = score - nat["mean"]
            z = diff / nat["sd"] if nat["sd"] > 0 else 0.0
            # レベル判定（全国平均との差）
            if z >= 0.5:
                level = "良好"
            elif z >= -0.5:
                level = "平均的"
            elif z >= -1.0:
                level = "やや低い"
            else:
                level = "低い"
            result[scale_name] = {
                "score": round(score, 3),
                "national_mean": nat["mean"],
                "diff": round(diff, 3),
                "z_score": round(z, 3),
                "level": level,
            }
        return result

    # ──────────────────────────────────────────────────────
    # 内部メソッド
    # ──────────────────────────────────────────────────────

    def _get_required_items(self) -> list:
        """バージョンに応じた必須項目番号リストを返す"""
        if self.version == "120":
            return sorted(ITEMS_120)
        elif self.version == "80":
            return sorted(ITEMS_80)
        else:  # 57
            return list(range(1, 58))

    def _convert_item_scores(self, responses: Dict[int, int]) -> Dict[int, Optional[int]]:
        """回答値をスコアマップに従って換算する"""
        item_scores = {}
        for q_num, raw_val in responses.items():
            if q_num not in ALL_ITEMS:
                continue
            score_map = ALL_ITEMS[q_num]["score_map"]
            if raw_val in score_map:
                item_scores[q_num] = score_map[raw_val]
            else:
                item_scores[q_num] = None  # 無効値
        return item_scores

    def _calc_scale_scores(self, item_scores: Dict[int, Optional[int]]) -> Dict[str, Optional[float]]:
        """尺度得点を計算する（高得点=望ましい、1〜4点）"""
        scale_scores = {}
        items_key = "items_standard" if self.version == "120" else "items_short"

        for scale_name, scale_def in SCALES.items():
            items = scale_def[items_key]
            if not items:
                scale_scores[scale_name] = None
                continue

            scores = [item_scores.get(q) for q in items]
            valid_scores = [s for s in scores if s is not None]

            if not valid_scores:
                scale_scores[scale_name] = None
            elif len(valid_scores) < len(items):
                # 欠損あり：有効分で計算（50%以上あれば計算）
                if len(valid_scores) / len(items) >= 0.5:
                    scale_scores[scale_name] = sum(valid_scores) / len(valid_scores)
                else:
                    scale_scores[scale_name] = None
            else:
                scale_scores[scale_name] = sum(valid_scores) / len(items)

        return scale_scores

    def _calc_raw_totals_for_highstress(
        self, responses: Dict[int, int]
    ) -> Tuple[int, int]:
        """
        高ストレス判定用の元スコア合計を計算する
        厚労省基準：逆転なし（1=最小, 4=最大）の元の回答値で集計

        B領域：q18-46（29項目）
        A領域：q1-17（17項目）
        C領域：q47-55（9項目）
        """
        # B領域（q18-q46）：そのままの回答値
        B_total = 0
        for q in range(18, 47):
            val = responses.get(q, 0)
            B_total += val

        # A領域（q1-q17）：逆転項目あり
        # q1-7,11-13,15 は逆転（1→4,2→3...）
        A_REVERSE = {1,2,3,4,5,6,7,11,12,13,15}
        A_total = 0
        for q in range(1, 18):
            val = responses.get(q, 0)
            if q in A_REVERSE:
                val = 5 - val  # 逆転
            A_total += val

        # C領域（q47-q55）：B領域1-3は逆転
        # C領域q47-55は全て「高=良い」なので逆転（元スコアでは低=良い）
        C_total = 0
        for q in range(47, 56):
            val = responses.get(q, 0)
            val = 5 - val  # C領域は全て逆転
            C_total += val

        return B_total, A_total + C_total

    def _judge_high_stress(self, raw_B: int, raw_AC: int) -> Tuple[bool, Optional[str]]:
        """高ストレス者判定"""
        # ㋐ B領域合計 >= 77
        if raw_B >= HIGH_STRESS_RAW["method_A"]["B_threshold"]:
            return True, "㋐"
        # ㋑ A+C合計 >= 76 かつ B >= 63
        if (raw_AC >= HIGH_STRESS_RAW["method_B"]["AC_threshold"] and
                raw_B >= HIGH_STRESS_RAW["method_B"]["B_secondary"]):
            return True, "㋑"
        return False, None

    def _calc_domain_scores(self, scale_scores: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
        """A/B/C領域の尺度得点平均（参考値）"""
        domains = {"A": [], "B": [], "C": []}
        for scale_name, score in scale_scores.items():
            domain = SCALES[scale_name].get("domain")
            if domain in domains and score is not None:
                domains[domain].append(score)
        return {
            d: (sum(v)/len(v) if v else None)
            for d, v in domains.items()
        }


# ──────────────────────────────────────────────────────────
# 簡易テスト
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import random

    print("=" * 60)
    print("StressCheckScorer 動作確認")
    print("=" * 60)

    # ダミー回答（全項目に1〜4のランダム値）
    all_qnums = sorted(ALL_ITEMS.keys())
    dummy_responses = {q: random.randint(1, 4) for q in all_qnums}

    for version in ["120", "80", "57"]:
        scorer = StressCheckScorer(version=version)
        result = scorer.calculate(dummy_responses)

        print(f"\n▼ バージョン: {version}項目版")
        print(f"  有効: {result['valid']}")
        print(f"  欠損項目数: {len(result['missing_items'])}")
        print(f"  高ストレス: {result['high_stress']} ({result['high_stress_reason']})")
        print(f"  B領域合計(元): {result['raw_B_total']}")
        print(f"  A+C合計(元): {result['raw_AC_total']}")
        print(f"  尺度数: {len([v for v in result['scale_scores'].values() if v is not None])}")

        # 全国平均比較（上位3尺度）
        comparison = scorer.compare_to_national(
            {k: v for k, v in result["scale_scores"].items() if v is not None}
        )
        top3 = sorted(comparison.items(), key=lambda x: x[1]["z_score"], reverse=True)[:3]
        print(f"  強み上位3尺度: {[(n, d['level']) for n, d in top3]}")

    print("\n✅ 動作確認完了")
