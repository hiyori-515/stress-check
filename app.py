"""
ストレスチェック Web API
Google フォーム回答を受け取り、スコアリング → 個人PDF生成 → メール送信を行う

エンドポイント:
  POST /run-stress-check  - 1件処理（JSON body）
  GET  /health            - ヘルスチェック
"""

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from main import run_single
from src.security.audit_log import AuditLogger

# ── 設定 ────────────────────────────────────────────────────────
MOCK_MODE   = os.environ.get("MOCK_MODE", "false").lower() == "true"
PDF_OUT_DIR = os.environ.get("PDF_OUT_DIR", "/tmp/pdfs")
LOG_DIR     = os.environ.get("LOG_DIR", "logs/audit")

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
      company_code   : str   - 企業コード  ※ company_id としても可
      name           : str   - 氏名（PDF表示用、ログには残さない）
      email          : str   - 送付先メールアドレス
      department     : str   - 部署名
      gender         : str   - 性別
      age_group      : str   - 年齢区分
      employment_type: str   - 雇用形態（省略可）
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

    # company_code / company_id どちらでも受け付ける
    company_id  = body.get("company_id") or body.get("company_code", "UNKNOWN")
    response_id = body.get("response_id", "unknown")
    version     = str(body.get("version", "57"))

    audit = AuditLogger(log_dir=LOG_DIR, company_id=company_id)
    audit.log("run_stress_check", user_id=response_id,
              resource="individual_pipeline",
              detail={"version": version, "n_answers": len(body.get("answers", {}))})

    # ── モックモード ─────────────────────────────────────────────
    if MOCK_MODE:
        logger.info(f"[MOCK] response_id={response_id} version={version} "
                    f"answers={len(body.get('answers', {}))}")
        return jsonify({
            "status":           "success",
            "mock":             True,
            "received_answers": len(body.get("answers", {})),
        }), 200

    # ── run_single() に委譲 ──────────────────────────────────────
    response_data = {
        "company_id":      company_id,
        "response_id":     response_id,
        "name":            body.get("name", ""),
        "email":           body.get("email", ""),
        "department":      body.get("department", ""),
        "gender":          body.get("gender", ""),
        "age_group":       body.get("age_group", ""),
        "employment_type": body.get("employment_type", ""),
        "answers":         body["answers"],
        "version":         version,
        "submitted_at":    body.get("submitted_at", ""),
    }

    result = run_single(response_data, pdf_out_dir=PDF_OUT_DIR)

    if not result["success"] and result["pdf_path"] is None:
        audit.log("pipeline_error", user_id=response_id, success=False,
                  detail={"errors": result["errors"]})
        return jsonify({"status": "error", "errors": result["errors"]}), 500

    audit.log("pipeline_complete", user_id=response_id,
              detail={"pdf": result["pdf_path"], "email_sent": result["email_sent"]})

    status_code = 200 if result["success"] else 207
    return jsonify({
        "status":             "success" if result["success"] else "partial",
        "mock":               False,
        "high_stress":        result["high_stress"],
        "high_stress_reason": result["high_stress_reason"],
        "pdf_path":           result["pdf_path"],
        "email_sent":         result["email_sent"],
        "errors":             result["errors"],
    }), status_code


# ── バリデーション ────────────────────────────────────────────────

def _validate_body(body: Dict[str, Any]) -> list:
    errors = []
    if not body:
        return ["request body is empty"]
    if "answers" not in body:
        errors.append("'answers' フィールドが必要です")
    elif not isinstance(body["answers"], dict) or len(body["answers"]) == 0:
        errors.append("'answers' は空でない辞書である必要があります")
    version = str(body.get("version", "57"))
    if version not in ("57", "80", "120"):
        errors.append(
            f"'version' は '57' / '80' / '120' のいずれかを指定してください"
            f"（受信値: {version}）"
        )
    return errors


# ── エントリーポイント ───────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    logger.info(f"起動: port={port} mock={MOCK_MODE}")
    app.run(host="0.0.0.0", port=port, debug=False)
