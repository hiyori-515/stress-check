"""
ロールベースアクセス制御（RBAC）

ストレスチェック制度の関係者ロール:
  ADMIN      : システム管理者（全データアクセス可）
  IMPLEMENTER: 実施者（産業医・保健師）- 高ストレス者リスト閲覧可
  ANALYST    : 衛生管理者 - 集団分析のみ
  VIEWER     : 事業者担当者 - 集団分析（要約）のみ
"""

import functools
from enum import IntEnum
from typing import Callable


class AccessLevel(IntEnum):
    VIEWER = 1
    ANALYST = 2
    IMPLEMENTER = 3
    ADMIN = 4


# リソース → 最低必要アクセスレベルのマッピング
RESOURCE_REQUIREMENTS: dict[str, AccessLevel] = {
    "individual_scores":   AccessLevel.ADMIN,        # 個人スコア全件
    "high_stress_list":    AccessLevel.IMPLEMENTER,  # 高ストレス者リスト
    "group_analysis":      AccessLevel.ANALYST,      # 集団分析
    "labor_report":        AccessLevel.ANALYST,      # 労基署報告
    "group_summary":       AccessLevel.VIEWER,       # 集団サマリー（公開範囲）
}


class AccessDeniedError(PermissionError):
    """アクセス権限不足"""


def check_access(resource: str, level: AccessLevel) -> bool:
    """
    リソースへのアクセス可否を返す

    Parameters
    ----------
    resource : str
        アクセス対象リソース名（RESOURCE_REQUIREMENTS のキー）
    level : AccessLevel
        要求者のアクセスレベル

    Returns
    -------
    bool
    """
    required = RESOURCE_REQUIREMENTS.get(resource)
    if required is None:
        return False
    return level >= required


def require_access(resource: str, level: AccessLevel) -> None:
    """
    アクセス権限チェック。不足時は AccessDeniedError を送出する。

    Parameters
    ----------
    resource : str
    level : AccessLevel

    Raises
    ------
    AccessDeniedError
    """
    if not check_access(resource, level):
        required = RESOURCE_REQUIREMENTS.get(resource, AccessLevel.ADMIN)
        raise AccessDeniedError(
            f"リソース '{resource}' へのアクセスには "
            f"{required.name} 以上の権限が必要です（現在: {level.name}）"
        )


def requires_level(resource: str, level: AccessLevel):
    """
    関数デコレータ版アクセス制御

    使用例:
        @requires_level("high_stress_list", AccessLevel.IMPLEMENTER)
        def get_high_stress_report(company_id):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            require_access(resource, level)
            return func(*args, **kwargs)
        return wrapper
    return decorator
