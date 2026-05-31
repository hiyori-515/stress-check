"""
src/security/ のテスト
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
from src.security.anonymizer import Anonymizer
from src.security.access_control import (
    AccessLevel, AccessDeniedError, check_access, require_access, requires_level
)
from src.security.audit_log import AuditLogger


# ── Anonymizer ────────────────────────────────────────────────

class TestAnonymizer:
    def test_pseudonymize_changes_values(self):
        anon = Anonymizer(salt="test-salt")
        df = pd.DataFrame({"employee_hash": ["abc", "def", "ghi"]})
        result = anon.pseudonymize(df)
        assert not (result["employee_hash"] == df["employee_hash"]).any()

    def test_pseudonymize_deterministic(self):
        anon = Anonymizer(salt="fixed-salt")
        df = pd.DataFrame({"employee_hash": ["abc", "def"]})
        r1 = anon.pseudonymize(df)
        r2 = anon.pseudonymize(df)
        assert (r1["employee_hash"] == r2["employee_hash"]).all()

    def test_pseudonymize_different_salts(self):
        df = pd.DataFrame({"employee_hash": ["abc"]})
        r1 = Anonymizer(salt="salt1").pseudonymize(df)
        r2 = Anonymizer(salt="salt2").pseudonymize(df)
        assert r1["employee_hash"].iloc[0] != r2["employee_hash"].iloc[0]

    def test_remove_direct_identifiers(self):
        df = pd.DataFrame({
            "employee_hash": ["x"],
            "name": ["田中"],
            "email": ["a@b.com"],
            "department": ["営業部"],
        })
        result = Anonymizer().remove_direct_identifiers(df)
        assert "name" not in result.columns
        assert "email" not in result.columns
        assert "employee_hash" in result.columns
        assert "department" in result.columns

    def test_suppress_small_groups(self):
        df = pd.DataFrame({
            "department": ["A"] * 3 + ["B"] * 12,
            "score": [2.0] * 15,
        })
        result = Anonymizer().suppress_small_groups(df, group_col="department", min_n=5)
        assert result[result["department"] == "A"]["score"].isna().all()
        assert not result[result["department"] == "B"]["score"].isna().any()

    def test_suppress_preserves_large_groups(self):
        df = pd.DataFrame({
            "department": ["Large"] * 20,
            "score": [3.0] * 20,
        })
        result = Anonymizer().suppress_small_groups(df, min_n=5)
        assert not result["score"].isna().any()

    def test_mask_high_stress_list(self):
        df = pd.DataFrame({
            "employee_hash": ["h1"],
            "department": ["部署A"],
            "high_stress_reason": ["㋐"],
            "raw_B_total": [80],
            "raw_AC_total": [90],
            "scale_仕事の量": [3.5],
        })
        result = Anonymizer().mask_high_stress_list(df)
        assert "scale_仕事の量" not in result.columns
        assert "employee_hash" in result.columns


# ── AccessControl ─────────────────────────────────────────────

class TestAccessControl:
    def test_admin_can_access_all(self):
        for resource in ["individual_scores", "high_stress_list", "group_analysis"]:
            assert check_access(resource, AccessLevel.ADMIN) is True

    def test_viewer_limited(self):
        assert check_access("individual_scores", AccessLevel.VIEWER) is False
        assert check_access("high_stress_list", AccessLevel.VIEWER) is False
        assert check_access("group_summary", AccessLevel.VIEWER) is True

    def test_implementer_can_view_high_stress(self):
        assert check_access("high_stress_list", AccessLevel.IMPLEMENTER) is True

    def test_analyst_cannot_view_individual(self):
        assert check_access("individual_scores", AccessLevel.ANALYST) is False

    def test_require_access_raises_on_deny(self):
        with pytest.raises(AccessDeniedError):
            require_access("individual_scores", AccessLevel.VIEWER)

    def test_require_access_passes_for_admin(self):
        require_access("individual_scores", AccessLevel.ADMIN)  # no exception

    def test_unknown_resource_denied(self):
        assert check_access("nonexistent_resource", AccessLevel.ADMIN) is False

    def test_decorator_blocks_low_level(self):
        """デコレータが低権限での呼び出しをブロックする"""
        @requires_level("high_stress_list", AccessLevel.VIEWER)
        def sensitive_func():
            return "secret"

        with pytest.raises(AccessDeniedError):
            sensitive_func()

    def test_decorator_allows_sufficient_level(self):
        """デコレータが十分な権限での呼び出しを通過させる"""
        @requires_level("group_summary", AccessLevel.VIEWER)
        def public_func():
            return "ok"

        assert public_func() == "ok"

    def test_access_level_order(self):
        assert AccessLevel.VIEWER < AccessLevel.ANALYST
        assert AccessLevel.ANALYST < AccessLevel.IMPLEMENTER
        assert AccessLevel.IMPLEMENTER < AccessLevel.ADMIN


# ── AuditLogger ───────────────────────────────────────────────

class TestAuditLogger:
    def test_writes_log_file(self, tmp_path):
        audit = AuditLogger(log_dir=str(tmp_path), company_id="TEST")
        audit.log("test_action", user_id="user1", resource="group_analysis")
        log_file = tmp_path / "TEST_audit.jsonl"
        assert log_file.exists()

    def test_log_content(self, tmp_path):
        audit = AuditLogger(log_dir=str(tmp_path), company_id="TEST")
        audit.log("export_csv", user_id="admin", resource="high_stress_list")
        entries = audit.read_logs()
        assert len(entries) == 1
        e = entries[0]
        assert e["action"] == "export_csv"
        assert e["user_id"] == "admin"
        assert e["resource"] == "high_stress_list"
        assert e["company_id"] == "TEST"
        assert e["success"] is True

    def test_multiple_entries(self, tmp_path):
        audit = AuditLogger(log_dir=str(tmp_path), company_id="TEST")
        for i in range(5):
            audit.log(f"action_{i}", user_id="user")
        entries = audit.read_logs()
        assert len(entries) == 5

    def test_access_denied_log(self, tmp_path):
        audit = AuditLogger(log_dir=str(tmp_path), company_id="TEST")
        audit.log_access_denied("viewer_user", "individual_scores", "ADMIN")
        entries = audit.read_logs()
        assert entries[0]["action"] == "access_denied"
        assert entries[0]["success"] is False

    def test_read_logs_empty(self, tmp_path):
        audit = AuditLogger(log_dir=str(tmp_path / "new"), company_id="EMPTY")
        assert audit.read_logs() == []

    def test_read_logs_limit(self, tmp_path):
        audit = AuditLogger(log_dir=str(tmp_path), company_id="TEST")
        for i in range(20):
            audit.log(f"action_{i}")
        entries = audit.read_logs(limit=5)
        assert len(entries) == 5
