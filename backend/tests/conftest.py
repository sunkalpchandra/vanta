"""Suite-wide database binding.

app/db.py creates its engine at first import, so DATABASE_URL must be set
before any test module imports an app module. conftest.py is imported by
pytest before every test module under any ordering, which makes this the one
deterministic place to bind the throwaway suite database.

The suite intentionally shares this one database: later modules must tolerate
earlier modules' writes (ask-created questions, discovery-minted questions,
resolved questions).
"""

import os
import tempfile

_tmpdir = tempfile.mkdtemp(prefix="vanta-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/suite.db"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

# Hypothesis: property examples run real Monte Carlo under coverage tracing in
# CI — the default 200ms deadline flakes there (reproduced DeadlineExceeded).
from hypothesis import settings  # noqa: E402

settings.register_profile("vanta", deadline=None)
settings.load_profile("vanta")
