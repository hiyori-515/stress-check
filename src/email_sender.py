"""
メール送信ヘルパー

実際の送信は GAS の GmailApp.sendEmail() が担当する。
このモジュールは「PDFのbase64エンコード」と「APIレスポンス用ペイロードの組み立て」のみを行う。
"""

import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SENDER_EMAIL = "epiphanypsycho@gmail.com"


def build_email_payload(
    to_addr: str,
    name: str,
    pdf_path: str,
    high_stress: bool = False,
) -> dict:
    """
    GAS に渡すメール送信ペイロードを組み立てる

    Parameters
    ----------
    to_addr : str
        送付先メールアドレス
    name : str
        受検者氏名（件名・本文に使用）
    pdf_path : str
        添付するPDFのファイルパス
    high_stress : bool
        高ストレス者フラグ（本文の文言を切り替え）

    Returns
    -------
    dict
        {
          "to":           str,   # 送付先
          "subject":      str,   # 件名
          "body":         str,   # 本文（プレーンテキスト）
          "pdf_base64":   str,   # PDFのBase64エンコード文字列
          "pdf_filename": str,   # 添付ファイル名
        }
    """
    subject = f"【ストレスチェック結果】{name} 様"

    if high_stress:
        body = (
            f"{name} 様\n\n"
            "ストレスチェックの結果をお送りします。\n\n"
            "今回の結果では、高いストレス状態が確認されました。\n"
            "詳細は添付のPDFをご確認ください。\n"
            "ご不明な点があれば、産業医・保健師にご相談ください。\n\n"
            "※ このメールは自動送信されています。"
        )
    else:
        body = (
            f"{name} 様\n\n"
            "ストレスチェックの結果をお送りします。\n\n"
            "詳細は添付のPDFをご確認ください。\n\n"
            "※ このメールは自動送信されています。"
        )

    pdf_bytes = Path(pdf_path).read_bytes()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    return {
        "to":           to_addr,
        "subject":      subject,
        "body":         body,
        "pdf_base64":   pdf_base64,
        "pdf_filename": Path(pdf_path).name,
    }
