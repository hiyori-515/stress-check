"""
ストレスチェック処理パイプライン
Phase 1: CSV読み込み → スコアリング → 結果出力（CSV）

使用方法:
    python main.py --input data/input/EP-2025-001/responses.csv \
                   --company_id EP-2025-001 \
                   --version 120 \
                   --year 2025
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.ingestion.loader import ResponseLoader, generate_sample_csv
from src.scoring.calculator import StressCheckScorer

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("stress_check")


def run_pipeline(
    input_path: str,
    company_id: str,
    version: str = "120",
    year: int = None,
    output_dir: str = "outputs",
    min_group_size: int = 10,
) -> dict:
    """
    ストレスチェック処理の本体

    Parameters
    ----------
    input_path : str
        入力CSVパス
    company_id : str
        企業ID（例: EP-2025-001）
    version : str
        "120" / "80" / "57"
    year : int
        実施年度（Noneの場合は現在年）
    output_dir : str
        出力先ディレクトリ
    min_group_size : int
        集団分析の最小人数（以下の部署は非表示）

    Returns
    -------
    dict
        処理結果サマリー
    """
    if year is None:
        year = datetime.now().year

    logger.info(f"処理開始: {company_id} / {version}項目版 / {year}年度")
    logger.info(f"入力ファイル: {input_path}")

    # ── Step 1: CSV読み込み ──────────────────────────────
    loader = ResponseLoader(version=version, company_id=company_id)
    df, errors = loader.load(input_path)

    if errors:
        logger.error("CSVバリデーションエラー:")
        for e in errors:
            logger.error(f"  - {e}")
        return {"success": False, "errors": errors}

    logger.info(f"読み込み成功: {len(df)}名")

    # ── Step 2: 全員分スコアリング ────────────────────────
    scorer = StressCheckScorer(version=version)
    records = loader.to_response_dicts(df)

    individual_results = []
    high_stress_count = 0

    for record in records:
        result = scorer.calculate(record["responses"])
        result["employee_hash"] = record["employee_hash"]
        result["meta"] = record["meta"]
        individual_results.append(result)
        if result["high_stress"]:
            high_stress_count += 1

    logger.info(
        f"スコアリング完了: {len(individual_results)}名 "
        f"（高ストレス者: {high_stress_count}名 / "
        f"{high_stress_count/len(individual_results)*100:.1f}%）"
    )

    # ── Step 3: 結果をDataFrameに変換 ─────────────────────
    rows = []
    for r in individual_results:
        row = {
            "employee_hash": r["employee_hash"],
            "department": r["meta"].get("department", ""),
            "gender": r["meta"].get("gender", ""),
            "age_group": r["meta"].get("age_group", ""),
            "high_stress": r["high_stress"],
            "high_stress_reason": r["high_stress_reason"] or "",
            "raw_B_total": r["raw_B_total"],
            "raw_AC_total": r["raw_AC_total"],
            "valid": r["valid"],
        }
        # 尺度得点を追加
        for scale_name, score in r["scale_scores"].items():
            row[f"scale_{scale_name}"] = round(score, 3) if score is not None else None
        rows.append(row)

    df_results = pd.DataFrame(rows)

    # ── Step 4: 出力先ディレクトリ作成 ──────────────────────
    out_base = Path(output_dir) / company_id / str(year)
    out_base.mkdir(parents=True, exist_ok=True)

    # ── Step 5: 個人スコアCSV出力（processed/に保存）────────
    processed_dir = Path("data/processed") / company_id / str(year)
    processed_dir.mkdir(parents=True, exist_ok=True)
    scores_path = processed_dir / "individual_scores.csv"
    df_results.to_csv(scores_path, index=False, encoding="utf-8-sig")
    logger.info(f"個人スコア保存: {scores_path}")

    # ── Step 6: 高ストレス者一覧（実施者用・管理外） ────────
    high_stress_df = df_results[df_results["high_stress"] == True][
        ["employee_hash", "department", "high_stress_reason",
         "raw_B_total", "raw_AC_total"]
    ]
    hs_path = processed_dir / "high_stress_list.csv"
    high_stress_df.to_csv(hs_path, index=False, encoding="utf-8-sig")
    logger.info(f"高ストレス者リスト保存: {hs_path}（{len(high_stress_df)}名）")

    # ── Step 7: 集団分析用サマリー ────────────────────────
    group_summary = _calc_group_summary(df_results, min_group_size)
    group_path = processed_dir / "group_analysis.csv"
    group_summary.to_csv(group_path, index=False, encoding="utf-8-sig")
    logger.info(f"集団分析データ保存: {group_path}")

    # ── Step 8: 労基署報告用データ ───────────────────────
    labor_report = _create_labor_report(df_results, company_id, year)
    labor_path = out_base / "admin" / "labor_bureau_report.csv"
    labor_path.parent.mkdir(parents=True, exist_ok=True)
    labor_report.to_csv(labor_path, index=False, encoding="utf-8-sig")
    logger.info(f"労基署報告データ保存: {labor_path}")

    # ── Step 9: 処理ログ ──────────────────────────────────
    log_path = Path("logs") / company_id / str(year)
    log_path.mkdir(parents=True, exist_ok=True)
    summary = {
        "company_id": company_id,
        "version": version,
        "year": year,
        "processed_at": datetime.now().isoformat(),
        "total_respondents": len(df_results),
        "high_stress_count": int(high_stress_count),
        "high_stress_rate": round(high_stress_count / len(df_results) * 100, 1),
        "valid_count": int(df_results["valid"].sum()),
        "input_file": str(input_path),
        "outputs": {
            "individual_scores": str(scores_path),
            "high_stress_list": str(hs_path),
            "group_analysis": str(group_path),
            "labor_report": str(labor_path),
        }
    }
    log_file = log_path / f"processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info(f"処理ログ保存: {log_file}")

    logger.info("=" * 50)
    logger.info(f"処理完了: {company_id}")
    logger.info(f"  受検者数: {summary['total_respondents']}名")
    logger.info(f"  高ストレス者: {summary['high_stress_count']}名"
                f"（{summary['high_stress_rate']}%）")
    logger.info("=" * 50)

    return {"success": True, "summary": summary}


def _calc_group_summary(df: pd.DataFrame, min_group_size: int = 10) -> pd.DataFrame:
    """
    部署別の集団分析サマリーを計算
    min_group_size未満の部署はデータを非表示（コンプライアンス対応）
    """
    scale_cols = [c for c in df.columns if c.startswith("scale_")]
    group_rows = []

    for dept, group in df.groupby("department"):
        n = len(group)
        row = {"department": dept, "n": n, "suppressed": n < min_group_size}

        if n >= min_group_size:
            row["high_stress_count"] = int(group["high_stress"].sum())
            row["high_stress_rate"] = round(group["high_stress"].mean() * 100, 1)
            for col in scale_cols:
                vals = group[col].dropna()
                if len(vals) > 0:
                    row[col + "_mean"] = round(vals.mean(), 3)
                    row[col + "_n"] = len(vals)
        else:
            # 個人特定防止：少人数部署はスコアを非表示
            row["high_stress_count"] = None
            row["high_stress_rate"] = None
            logger.warning(
                f"部署「{dept}」は{n}名（最小{min_group_size}名未満）のため"
                f"集団分析データを非表示にしました"
            )

        group_rows.append(row)

    return pd.DataFrame(group_rows)


def _create_labor_report(
    df: pd.DataFrame, company_id: str, year: int
) -> pd.DataFrame:
    """
    労働基準監督署報告用データを生成
    個人を特定できる情報は含まない
    """
    return pd.DataFrame([{
        "company_id": company_id,
        "fiscal_year": year,
        "total_respondents": len(df),
        "high_stress_count": int(df["high_stress"].sum()),
        "high_stress_rate_pct": round(df["high_stress"].mean() * 100, 1),
        "interview_required_count": int(df["high_stress"].sum()),  # 面接勧奨対象者数
        "report_generated_at": datetime.now().strftime("%Y-%m-%d"),
    }])


# ──────────────────────────────────────────────────────────
# CLI エントリーポイント
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ストレスチェック処理パイプライン")
    parser.add_argument("--input",      required=False, help="入力CSVパス")
    parser.add_argument("--company_id", default="EP-TEST-001", help="企業ID")
    parser.add_argument("--version",    default="120", choices=["120","80","57"])
    parser.add_argument("--year",       type=int, default=None)
    parser.add_argument("--demo",       action="store_true", help="デモ用サンプルデータで実行")
    args = parser.parse_args()

    if args.demo or not args.input:
        # デモ実行：サンプルデータを自動生成
        import tempfile
        tmp = tempfile.mktemp(suffix=".csv")
        generate_sample_csv(
            tmp,
            version=args.version,
            n_respondents=30,
            departments=["営業部", "開発部", "管理部", "製造部", "小チーム"],
        )
        input_path = tmp
        logger.info(f"デモモード: サンプルCSVを生成しました（{input_path}）")
    else:
        input_path = args.input

    result = run_pipeline(
        input_path=input_path,
        company_id=args.company_id,
        version=args.version,
        year=args.year,
    )

    if result["success"]:
        print("\n処理成功 ✅")
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    else:
        print("\n処理失敗 ❌")
        for e in result.get("errors", []):
            print(f"  - {e}")
        sys.exit(1)
