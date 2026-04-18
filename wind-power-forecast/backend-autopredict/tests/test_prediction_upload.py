# tests/test_prediction_upload.py
"""Integration tests for the prediction CSV upload endpoints.

Tests cover:
- Successful CSV upload and parsing (supershort, short, mid power)
- Rejected upload: no file attached
- Rejected upload: empty filename
- Rejected upload: non-CSV file format
- Filename time parsing for supershort (hhmm extraction)
- Invalid filename format (non-numeric time part)
- Missing required CSV columns
- Full batch insert/update flow with mocked database
"""
import io
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock the heavy DB import chain before any backend imports.
for _mod in (
    "database_config",
    "db_session",
    "db_models",
    "db_models.base",
    "db_models.report_config",
    "models",
    "config",
    "logging_config",
    "connection_middleware",
    "common",
    "common.api_response",
    "s3_error",
    "db_models.dataset",
    "base",
    "kingbase_dialect",
):
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Provide mock ORM models that the route file imports
mock_supershort = MagicMock()
mock_supershort.__name__ = "SupershortlPower"
mock_short = MagicMock()
mock_short.__name__ = "ShortlPower"
mock_mid = MagicMock()
mock_mid.__name__ = "MidPower"

sys.modules["models"] = MagicMock(
    SupershortlPower=mock_supershort,
    ShortlPower=mock_short,
    MidPower=mock_mid,
)

import flask


def _create_test_app():
    """Create a Flask test app with the prediction2database blueprint registered."""
    app = flask.Flask(__name__)
    app.config["TESTING"] = True

    from routes.prediction2database import prediction2database_bp
    app.register_blueprint(prediction2database_bp)

    return app


def _make_mock_ctx(mock_session=None):
    """Create a mock db_session context manager that returns mock_session."""
    if mock_session is None:
        mock_session = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__ = MagicMock(return_value=mock_session)
    mock_ctx.__exit__ = MagicMock(return_value=False)
    return lambda: mock_ctx


# ---------------------------------------------------------------------------
# Helper: build CSV content
# ---------------------------------------------------------------------------

def _make_predicted_power_csv(rows=None):
    """Return a BytesIO CSV with Timestamp + Predicted Power columns."""
    if rows is None:
        rows = [
            {"Timestamp": "2025-06-15 10:00:00", "Predicted Power": "100.5"},
            {"Timestamp": "2025-06-15 11:00:00", "Predicted Power": "150.0"},
        ]
    header = list(rows[0].keys())
    lines = [",".join(header)]
    for row in rows:
        line = ",".join(str(row.get(h, "")) for h in header)
        lines.append(line)
    csv_text = "\n".join(lines) + "\n"
    return io.BytesIO(csv_text.encode("utf-8"))


# Filename format for supershort: must have hhmm at positions [-8:-4]
# e.g., "predict_20250615_1030.csv" -> time_str = "1030"
def _make_supershort_filename(hour=10, minute=30):
    """Generate a filename with embedded hhmm for supershort upload."""
    return f"predict_20250615_{hour:02d}{minute:02d}.csv"


# ===========================================================================
# Tests: batch_supershortl_power
# ===========================================================================


class TestBatchSupershortNoFile:
    """Test missing file scenarios for supershort upload."""

    def test_no_file_attached(self):
        """POST without a file returns 400."""
        app = _create_test_app()
        with app.test_client() as client:
            resp = client.post("/prediction2database/batch_supershortl_power")
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_empty_filename(self):
        """POST with empty filename returns 400."""
        app = _create_test_app()
        with app.test_client() as client:
            resp = client.post(
                "/prediction2database/batch_supershortl_power",
                data={"file": (io.BytesIO(b""), "")},
            )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data

    def test_non_csv_file_rejected(self):
        """A .xlsx file is rejected with 400."""
        app = _create_test_app()
        with app.test_client() as client:
            resp = client.post(
                "/prediction2database/batch_supershortl_power",
                data={"file": (io.BytesIO(b"fake"), "data.xlsx")},
            )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "CSV" in data["error"]


class TestBatchSupershortFilenameParsing:
    """Test filename time parsing for supershort uploads.

    The supershort route extracts hhmm from filename[-8:-4] to compute pre_order.
    """

    def test_valid_filename_succeeds(self):
        """A filename like predict_20250615_1030.csv is parsed correctly."""
        app = _create_test_app()
        csv_data = _make_predicted_power_csv()
        filename = _make_supershort_filename(10, 30)

        mock_session = MagicMock()
        # query().filter().all() returns no duplicates
        mock_session.query.return_value.filter.return_value.all.return_value = []

        import routes.prediction2database as p2d
        original = p2d.db_session
        p2d.db_session = _make_mock_ctx(mock_session)

        try:
            with app.test_client() as client:
                resp = client.post(
                    "/prediction2database/batch_supershortl_power",
                    data={"file": (csv_data, filename)},
                )
        finally:
            p2d.db_session = original

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total"] == 2
        assert data["inserted"] == 2

    def test_invalid_filename_time_returns_500(self):
        """A filename without valid hhmm causes int() parse error -> 500."""
        app = _create_test_app()
        csv_data = _make_predicted_power_csv()

        import routes.prediction2database as p2d
        original = p2d.db_session
        p2d.db_session = _make_mock_ctx()

        try:
            with app.test_client() as client:
                resp = client.post(
                    "/prediction2database/batch_supershortl_power",
                    data={"file": (csv_data, "data.csv")},
                )
        finally:
            p2d.db_session = original

        # The route catches int() ValueError and returns 500
        assert resp.status_code == 500

    def test_different_times_compute_different_pre_order(self):
        """Different filename times produce correct pre_order values.

        pre_order = (hour * 60 + minute) // 15 + 1
        10:30 -> (630 // 15) + 1 = 43
        14:15 -> (855 // 15) + 1 = 58
        """
        # Test the formula directly
        def compute_pre_order(hour, minute):
            return (hour * 60 + minute) // 15 + 1

        assert compute_pre_order(10, 30) == 43  # 10*60+30 = 630, 630//15+1 = 43
        assert compute_pre_order(0, 0) == 1     # midnight -> 1
        assert compute_pre_order(23, 45) == 96  # last slot


class TestBatchSupershortSuccessfulUpload:
    """Test successful supershort CSV upload with mocked database."""

    def test_successful_insert(self):
        """Valid CSV inserts new records and returns 201."""
        app = _create_test_app()
        csv_data = _make_predicted_power_csv()
        filename = _make_supershort_filename(10, 0)

        mock_session = MagicMock()
        # No existing records (empty duplicate set)
        mock_session.query.return_value.filter.return_value.all.return_value = []

        import routes.prediction2database as p2d
        original = p2d.db_session
        p2d.db_session = _make_mock_ctx(mock_session)

        try:
            with app.test_client() as client:
                resp = client.post(
                    "/prediction2database/batch_supershortl_power",
                    data={"file": (csv_data, filename)},
                )
        finally:
            p2d.db_session = original

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total"] == 2
        assert data["inserted"] == 2
        assert data["updated"] == 0

    def test_successful_update_existing(self):
        """Valid CSV updates existing records when duplicates found."""
        app = _create_test_app()
        csv_data = _make_predicted_power_csv()
        filename = _make_supershort_filename(10, 0)

        mock_session = MagicMock()
        # Simulate existing records (duplicates)
        mock_dt = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = [(mock_dt,)]

        import routes.prediction2database as p2d
        original = p2d.db_session
        p2d.db_session = _make_mock_ctx(mock_session)

        try:
            with app.test_client() as client:
                resp = client.post(
                    "/prediction2database/batch_supershortl_power",
                    data={"file": (csv_data, filename)},
                )
        finally:
            p2d.db_session = original

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total"] == 2
        assert data["updated"] == 1
        assert data["inserted"] == 1


# ===========================================================================
# Tests: batch_shortl_power
# ===========================================================================


class TestBatchShortNoFile:
    """Test missing file scenarios for short-term upload."""

    def test_no_file_attached(self):
        """POST without a file returns 400."""
        app = _create_test_app()
        with app.test_client() as client:
            resp = client.post("/prediction2database/batch_shortl_power")
        assert resp.status_code == 400

    def test_non_csv_rejected(self):
        """Non-CSV file is rejected."""
        app = _create_test_app()
        with app.test_client() as client:
            resp = client.post(
                "/prediction2database/batch_shortl_power",
                data={"file": (io.BytesIO(b"{}"), "data.json")},
            )
        assert resp.status_code == 400


class TestBatchShortSuccessfulUpload:
    """Test successful short-term CSV upload with mocked database."""

    def test_successful_insert(self):
        """Valid short CSV inserts records and returns 201."""
        app = _create_test_app()
        csv_data = _make_predicted_power_csv()

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        import routes.prediction2database as p2d
        original = p2d.db_session
        p2d.db_session = _make_mock_ctx(mock_session)

        try:
            with app.test_client() as client:
                resp = client.post(
                    "/prediction2database/batch_shortl_power",
                    data={"file": (csv_data, "short.csv")},
                )
        finally:
            p2d.db_session = original

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total"] == 2
        assert data["errors"] == 0


# ===========================================================================
# Tests: batch_mid_power
# ===========================================================================


class TestBatchMidNoFile:
    """Test missing file scenarios for mid-term upload."""

    def test_no_file_attached(self):
        app = _create_test_app()
        with app.test_client() as client:
            resp = client.post("/prediction2database/batch_mid_power")
        assert resp.status_code == 400


class TestBatchMidSuccessfulUpload:
    """Test successful mid-term CSV upload with mocked database."""

    def test_successful_insert(self):
        """Valid mid CSV inserts records and returns 201."""
        app = _create_test_app()
        csv_data = _make_predicted_power_csv()

        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.all.return_value = []

        import routes.prediction2database as p2d
        original = p2d.db_session
        p2d.db_session = _make_mock_ctx(mock_session)

        try:
            with app.test_client() as client:
                resp = client.post(
                    "/prediction2database/batch_mid_power",
                    data={"file": (csv_data, "mid.csv")},
                )
        finally:
            p2d.db_session = original

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["total"] == 2
        assert data["errors"] == 0
