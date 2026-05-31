"""
Gmail API メール送信モジュール

認証方式: OAuth2 Service Account または credentials.json（Desktop app flow）
送信元: epiphanypsycho@gmail.com

環境変数:
  GMAIL_CREDENTIALS_PATH  credentials.json のパス（省略時: credentials.json）
  GMAIL_TOKEN_PATH        token.json の保存先（省略時: token.json）
"""

import base64
import logging
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SENDER_EMAIL  = "epiphanypsycho@gmail.com"
GMAIL_SCOPES  = ["https://www.googleapis.com/auth/gmail.send"]

_gmail_service = None


# ── 認証 ────────────────────────────────────────────────────────

def _get_gmail_service():
    """Gmail API サービスオブジェクトをシングルトンで返す"""
    global _gmail_service
    if _gmail_service is not None:
        return _gmail_service

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds_path = os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
    token_path  = os.environ.get("GMAIL_TOKEN_PATH", "token.json")

    if not Path(creds_path).exists():
        raise FileNotFoundError(
            f"credentials.json が見つかりません: {creds_path}\n"
            "Google Cloud Console でOAuth2クライアントIDを作成し、"
            "GMAIL_CREDENTIALS_PATH 環境変数で指定してください。"
        )

    creds = None
    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
        logger.info(f"Gmail トークン保存: {token_path}")

    _gmail_service = build("gmail", "v1", credentials=creds)
    return _gmail_service


def reset_gmail_service():
    """テスト・再認証用にキャッシュをリセットする"""
    global _gmail_service
    _gmail_service = None


# ── メール送信 ────────────────────────────────────────────────────

def send_result_email(
    to_addr: str,
    name: str,
    pdf_path: str,
    high_stress: bool = False,
) -> None:
    """
    個人結果PDFをGmail APIで送信する

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

    Raises
    ------
    FileNotFoundError
        credentials.json が見つからない場合
    googleapiclient.errors.HttpError
        Gmail API 呼び出し失敗時
    """
    service = _get_gmail_service()
    raw = _build_message(to_addr, name, pdf_path, high_stress)

    service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    logger.info(f"Gmail送信完了: {to_addr} ({Path(pdf_path).name})")


def _build_message(
    to_addr: str,
    name: str,
    pdf_path: str,
    high_stress: bool,
) -> str:
    """MIME メッセージを組み立て、Base64URL エンコードして返す"""
    subject = f"【ストレスチェック結果】{name} 様"

    if high_stress:
        body_text = (
            f"{name} 様\n\n"
            "ストレスチェックの結果をお送りします。\n\n"
            "今回の結果では、高いストレス状態が確認されました。\n"
            "詳細は添付のPDFをご確認ください。\n"
            "ご不明な点があれば、産業医・保健師にご相談ください。\n\n"
            "※ このメールは自動送信されています。"
        )
    else:
        body_text = (
            f"{name} 様\n\n"
            "ストレスチェックの結果をお送りします。\n\n"
            "詳細は添付のPDFをご確認ください。\n\n"
            "※ このメールは自動送信されています。"
        )

    msg = MIMEMultipart()
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    pdf_name = Path(pdf_path).name
    with open(pdf_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=pdf_name)
        part["Content-Disposition"] = f'attachment; filename="{pdf_name}"'
        msg.attach(part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return raw


# ── テスト送信 ────────────────────────────────────────────────────

def send_test_email(to_addr: str, pdf_path: Optional[str] = None) -> None:
    """
    動作確認用のテスト送信

    Parameters
    ----------
    to_addr : str
        送付先アドレス
    pdf_path : str, optional
        添付するPDF。省略時はダミーテキストファイルを生成して送信する

    使用例:
        python -m src.email_sender test@example.com
    """
    import tempfile

    cleanup = False
    if pdf_path is None or not Path(pdf_path).exists():
        tmp = tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, mode="wb"
        )
        # 最小限のPDFバイト列（テキストのみ）
        tmp.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj "
                  b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj "
                  b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]>>endobj "
                  b"xref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n9\n%%EOF")
        tmp.close()
        pdf_path = tmp.name
        cleanup = True
        logger.info(f"ダミーPDF生成: {pdf_path}")

    try:
        service = _get_gmail_service()
        raw = _build_message(
            to_addr=to_addr,
            name="テスト 太郎",
            pdf_path=pdf_path,
            high_stress=False,
        )
        result = service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        print(f"テスト送信成功: {to_addr}  messageId={result.get('id')}")
    finally:
        if cleanup:
            Path(pdf_path).unlink(missing_ok=True)


# ── CLI ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")

    if len(sys.argv) < 2:
        print("使用方法: python -m src.email_sender <送付先メール> [PDFパス]")
        sys.exit(1)

    to   = sys.argv[1]
    pdf  = sys.argv[2] if len(sys.argv) > 2 else None
    send_test_email(to_addr=to, pdf_path=pdf)
