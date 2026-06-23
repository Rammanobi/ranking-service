import os
import tempfile

import pytest

# Must be set before `app` is imported anywhere, since config.DB_PATH is
# read at import time.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["RANKING_DB_PATH"] = _tmp_db.name

from app import db  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    db.reset_db()
    yield


@pytest.fixture
def client():
    return TestClient(app)
