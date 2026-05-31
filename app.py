"""
ストレスチェック Web API
Google フォーム回答を受け取り、スコアリング → 個人PDF生成 → メール送信を行う

エンドポイント:
  POST /run-stress-check  - 1件処理（JSON body）
  GET  /health            - ヘルスチェック
"""

import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request

# プロジェクトルートを sys.path に追加
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from src.scoring.calculator import StressCheckScorer
from src.output.individual_pdf import generate_individual_pdf
from src.security.audit_log import AuditLogger

# ── 設定 ────────────────────────────────────────────────────────
MOCK_MODE   = os.environ.get("MOCK_MODE", "false").lower() == "true"
PDF_OUT_DIR = os.environ.get("PDF_OUT_DIR", "/tmp/pdfs")
LOG_DIR     = os.environ.get("LOG_DIR", "logs/audit")
SMTP_HOST   = os.environ.get("SMTP_HOST", "")
SMTP_PORT   = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER   = os.environ.get("SMTP_USER", "")
SMTP_PASS   = os.environ.get("SMTP_PASS", "")
FROM_EMAIL  = os.environ.get("FROM_EMAIL", "noreply@example.com")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

app = Flask(__name__)


# ── ヘルスチェック ───────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "mock_mode": MOCK_MODE}), 200


# ── メインエンドポイント ─────────────────────────────────────────

@app.route("/run-stress-check", methods=["POST"])
def run_stress_check():
    """
    受け付けるJSONフィールド:
      response_id    : str   - 回答ID（重複排除・ログ用）
      company_code   : str   - 企業コード
      name           : str   - 氏名（PDF表示用、ログには残さない）
      email          : str   - 送付先メールアドレス
      email_pattern  : str   - メールパターン（"A"/"B"/"C"等、未使用）
      department     : str   - 部署名
      gender         : str   - 性別
      age_group      : str   - 年齢区分
      employment_type: str   - 雇用形態
      answers        : dict  - {"Q1": 1, "Q2": 3, ...} 1-4の整数
      version        : str   - "57" / "80" / "120"（省略時 "57"）
      submitted_at   : str   - 回答日時（ISO8601）
    """
    try:
        body = request.get_json(force=True, silent=True) or {}
    except Exception:
        return jsonify({"status": "error", "message": "invalid JSON"}), 400

    # ── バリデーション ────────────────────────────────────────────
    errors = _validate_body(body)
    if errors:
        return jsonify({"status": "error", "errors": errors}), 400

    response_id  = body.get("response_id", "unknown")
    company_code = body.get("company_code", "UNKNOWN")
    version      = str(body.get("version", "57"))
    answers_raw  = body["answers"]

    audit = AuditLogger(log_dir=LOG_DIR, company_id=company_code)
    audit.log("run_stress_check", user_id=response_id,
              resource="individual_pipeline",
              detail={"version": version, "n_answers": len(answers_raw)})

    # ── モックモード ─────────────────────────────────────────────
    if MOCK_MODE:
        logger.info(f"[MOCK] response_id={response_id} version={version} answers={len(answers_raw)}")
        return jsonify({
            "status":           "success",
            "mock":             True,
            "received_answers": len(answers_raw),
        }), 200

    # ── 回答を int キーの dict に変換 ────────────────────────────
    responses = _parse_answers(answers_raw)

    # ── スコアリング ─────────────────────────────────────────────
    try:
        scorer = StressCheckScorer(version=version)
        score_result = scorer.calculate(responses)
        score_result["_raw_responses"] = responses
        comparison   = scorer.compare_to_national(
            {k: v for k, v in score_result["scale_scores"].items() if v is not None}
        )
    except Exception as e:
        logger.exception("スコアリング失敗")
        audit.log("scoring_error", user_id=response_id, success=False,
                  detail={"error": str(e)})
        return jsonify({"status": "error", "message": f"scoring failed: {e}"}), 500

    # ── PDF生成 ──────────────────────────────────────────────────
    pdf_path = None
    try:
        pdf_path = _generate_pdf(
            response_id=response_id,
            score_result=score_result,
            comparison=comparison,
            body=body,
        )
        audit.log("pdf_generated", user_id=response_id,
                  detail={"path": pdf_path})
    except Exception as e:
        logger.exception("PDF生成失敗")
        audit.log("pdf_error", user_id=response_id, success=False,
                  detail={"error": str(e)})
        # PDFが失敗してもスコア結果は返す（メール送信はスキップ）
        return jsonify({
            "status":      "partial",
            "message":     f"scoring ok, PDF failed: {e}",
            "high_stress": score_result["high_stress"],
        }), 207

    # ── メール送信 ───────────────────────────────────────────────
    email_sent = False
    email_addr = body.get("email", "")
    if email_addr and pdf_path:
        try:
            _send_email(
                to_addr=email_addr,
                pdf_path=pdf_path,
                name=body.get("name", ""),
                high_stress=score_result["high_stress"],
            )
            email_sent = True
            audit.log("email_sent", user_id=response_id,
                      detail={"to": email_addr})
        except Exception as e:
            logger.warning(f"メール送信失敗: {e}")
            audit.log("email_error", user_id=response_id, success=False,
                      detail={"error": str(e)})

    return jsonify({
        "status":      "success",
        "mock":        False,
        "high_stress": score_result["high_stress"],
        "high_stress_reason": score_result.get("high_stress_reason"),
        "pdf_path":    pdf_path,
        "email_sent":  email_sent,
    }), 200


# ── 内部ヘルパー ─────────────────────────────────────────────────

def _validate_body(body: Dict[str, Any]) -> list:
    errors = []
    if not body:
        return ["request body is empty"]
    if "answers" not in body:
        errors.append("'answers' フィールドが必要です")
    else:
        if not isinstance(body["answers"], dict) or len(body["answers"]) == 0:
            errors.append("'answers' は空でない辞書である必要があります")
    version = str(body.get("version", "57"))
    if version not in ("57", "80", "120"):
        errors.append(f"'version' は '57' / '80' / '120' のいずれかを指定してください（受信値: {version}）")
    return errors


def _parse_answers(answers_raw: dict) -> Dict[int, int]:
    """{"Q1": 3, "q2": 2, "1": 4, 1: 1} → {1: 3, 2: 2, ...}"""
    responses = {}
    for key, val in answers_raw.items():
        # キー正規化: "Q1" / "q1" / "1" / 1 → 1
        k = str(key).upper().lstrip("Q")
        try:
            q_num = int(k)
            responses[q_num] = int(val)
        except (ValueError, TypeError):
            continue
    return responses


def _generate_pdf(
    response_id: str,
    score_result: dict,
    comparison: dict,
    body: dict,
) -> str:
    """個人PDFを生成して保存パスを返す"""
    out_dir = Path(PDF_OUT_DIR) / body.get("company_code", "UNKNOWN")
    out_dir.mkdir(parents=True, exist_ok=True)

    submitted_at = body.get("submitted_at", datetime.now().isoformat())[:10]  # YYYY-MM-DD
    filename = f"{response_id}_{submitted_at}.pdf"
    pdf_path = str(out_dir / filename)

    meta = {
        "department":       body.get("department", ""),
        "gender":           body.get("gender", ""),
        "age_group":        body.get("age_group", ""),
        "employment_type":  body.get("employment_type", ""),
        "name":             body.get("name", ""),
    }

    generate_individual_pdf(
        employee_hash=response_id,
        score_result=score_result,
        comparison=comparison,
        meta=meta,
        output_path=pdf_path,
        lang="ja",
        company_name=body.get("company_code", ""),
        impl_date=submitted_at,
    )
    return pdf_path


def _send_email(to_addr: str, pdf_path: str, name: str, high_stress: bool) -> None:
    """
    PDFをメール添付して送信する（smtplib 実装）

    SMTP_HOST が未設定の場合は NotImplementedError を送出する。
    本番ではenv変数 SMTP_HOST / SMTP_USER / SMTP_PASS を設定してください。
    """
    if not SMTP_HOST:
        raise NotImplementedError(
            "SMTP_HOST が未設定です。環境変数を設定するか MOCK_MODE=true で起動してください。"
        )

    import smtplib
    from email.mime.application import MIMEApplication
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    subject = "【ストレスチェック】あなたの結果をお知らせします"
    if high_stress:
        body_text = (
            f"{name} さん\n\n"
            "ストレスチェックの結果をお送りします。\n"
            "今回の結果では、高いストレス状態が確認されました。\n"
            "産業医・保健師への相談をご検討ください。\n\n"
            "添付のPDFをご確認ください。"
        )
    else:
        body_text = (
            f"{name} さん\n\n"
            "ストレスチェックの結果をお送りします。\n"
            "添付のPDFをご確認ください。"
        )

    msg = MIMEMultipart()
    msg["From"]    = FROM_EMAIL
    msg["To"]      = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    with open(pdf_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=Path(pdf_path).name)
        part["Content-Disposition"] = f'attachment; filename="{Path(pdf_path).name}"'
        msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        if SMTP_USER and SMTP_PASS:
            server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(FROM_EMAIL, to_addr, msg.as_string())

    logger.info(f"メール送信完了: {to_addr}")


# ── エントリーポイント ───────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"起動: port={port} mock={MOCK_MODE}")
    app.run(host="0.0.0.0", port=port, debug=False)
