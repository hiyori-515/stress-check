"""
監査ログ

ストレスチェック制度では「誰が・いつ・何にアクセスしたか」の記録が必要。
このモジュールは操作ログをJSONL形式でファイルに追記する。
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class AuditLogger:
    """
    監査ログの記録クラス

    使用例:
        audit = AuditLogger(log_dir="logs/audit", company_id="EP-2025-001")
        audit.log("export_csv", user_id="admin", resource="high_stress_list")
    """

    def __init__(
        self,
        log_dir: str = "logs/audit",
        company_id: str = "UNKNOWN",
    ):
        self.company_id = company_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self.log_dir / f"{company_id}_audit.jsonl"

    def log(
        self,
        action: str,
        user_id: str = "system",
        resource: Optional[str] = None,
        detail: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> None:
        """
        監査イベントを記録する

        Parameters
        ----------
        action : str
            実行アクション（例: "export_csv", "view_high_stress", "run_pipeline"）
        user_id : str
            操作者ID
        resource : str, optional
            アクセス対象リソース名
        detail : dict, optional
            追加情報（件数、ファイルパス等）
        success : bool
            操作成否
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "company_id": self.company_id,
            "user_id": user_id,
            "action": action,
            "resource": resource,
            "success": success,
            "detail": detail or {},
        }

        try:
            with open(self._log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.error(f"監査ログ書き込み失敗: {e}")

    def log_access_denied(
        self, user_id: str, resource: str, required_level: str
    ) -> None:
        """アクセス拒否イベントを記録する"""
        self.log(
            action="access_denied",
            user_id=user_id,
            resource=resource,
            success=False,
            detail={"required_level": required_level},
        )

    def read_logs(self, limit: int = 100) -> list:
        """
        監査ログを新しい順に読み込む

        Parameters
        ----------
        limit : int
            取得件数上限

        Returns
        -------
        list of dict
        """
        if not self._log_file.exists():
            return []

        entries = []
        with open(self._log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return list(reversed(entries))[:limit]
