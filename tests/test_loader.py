"""
ResponseLoader の基本テスト
"""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.ingestion.loader import ResponseLoader, generate_sample_csv


@pytest.fixture
def sample_csv_57(tmp_path):
    path = str(tmp_path / "sample_57.csv")
    generate_sample_csv(path, version="57", n_respondents=15, seed=0)
    return path


@pytest.fixture
def sample_csv_120(tmp_path):
    path = str(tmp_path / "sample_120.csv")
    generate_sample_csv(path, version="120", n_respondents=15, seed=0)
    return path


class TestResponseLoader:
    def test_load_57_success(self, sample_csv_57):
        loader = ResponseLoader(version="57", company_id="TEST")
        df, errors = loader.load(sample_csv_57)
        assert errors == []
        assert len(df) == 15

    def test_load_120_success(self, sample_csv_120):
        loader = ResponseLoader(version="120", company_id="TEST")
        df, errors = loader.load(sample_csv_120)
        assert errors == []
        assert len(df) == 15

    def test_load_missing_file(self):
        loader = ResponseLoader(version="57")
        df, errors = loader.load("/nonexistent/path.csv")
        assert len(errors) == 1
        assert "見つかりません" in errors[0]

    def test_load_wrong_version_columns(self, sample_csv_57):
        """57項目版CSVを120項目版でロードするとエラー"""
        loader = ResponseLoader(version="120", company_id="TEST")
        df, errors = loader.load(sample_csv_57)
        assert len(errors) > 0

    def test_to_response_dicts(self, sample_csv_57):
        loader = ResponseLoader(version="57", company_id="TEST")
        df, _ = loader.load(sample_csv_57)
        records = loader.to_response_dicts(df)
        assert len(records) == 15
        for r in records:
            assert "employee_hash" in r
            assert "responses" in r
            assert "meta" in r
            assert len(r["responses"]) > 0

    def test_response_values_in_range(self, sample_csv_57):
        loader = ResponseLoader(version="57", company_id="TEST")
        df, _ = loader.load(sample_csv_57)
        records = loader.to_response_dicts(df)
        for r in records:
            for q_num, val in r["responses"].items():
                assert val in (1, 2, 3, 4), f"q{q_num}: {val} is invalid"

    def test_invalid_version_raises(self):
        with pytest.raises(ValueError):
            ResponseLoader(version="999")

    def test_meta_fields_present(self, sample_csv_57):
        loader = ResponseLoader(version="57", company_id="TEST")
        df, _ = loader.load(sample_csv_57)
        records = loader.to_response_dicts(df)
        meta = records[0]["meta"]
        assert "department" in meta
        assert "gender" in meta
        assert "age_group" in meta


class TestGenerateSampleCsv:
    @pytest.mark.parametrize("version", ["57", "80", "120"])
    def test_generates_file(self, version, tmp_path):
        path = str(tmp_path / f"sample_{version}.csv")
        result = generate_sample_csv(path, version=version, n_respondents=10)
        assert os.path.exists(result)

    def test_correct_row_count(self, tmp_path):
        path = str(tmp_path / "test.csv")
        generate_sample_csv(path, version="57", n_respondents=25)
        loader = ResponseLoader(version="57")
        df, errors = loader.load(path)
        assert errors == []
        assert len(df) == 25
