import os
import sys
from pathlib import Path

# Ensure project root is importable during pytest
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Use a separate MongoDB database for tests so production data is never touched.
# Set MONGODB_DB_TEST in env to override (e.g. sap_bnac_test). Requires MONGODB_URI (e.g. from .env).
os.environ["MONGODB_DB"] = os.environ.get("MONGODB_DB_TEST", "sap_bnac_test")

