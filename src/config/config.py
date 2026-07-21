from pathlib import Path
import os

# How long a chunk may sit in the pool before it's considered expired
# and should be swept out (archived).
POOL_TTL_SECONDS = 60

#API_HOST = "127.0.0.1"  # for local testing
API_HOST = "10.8.0.2"
API_PORT = 8000

MAX_BYTES_PER_REQUEST = 2048

# --- Archive settings ---
ARCHIVE_ROOT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "archive"
ARCHIVE_FORMAT_VERSION = 1

# BEACON
BEACON_ROOT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "beacon"
BEACON_PULSE_INTERVAL_SECONDS = 60
BEACON_OUTPUT_BYTES = 64
BEACON_WAIT_TIMEOUT_SECONDS = 5.0
BEACON_WAIT_POLL_INTERVAL_SECONDS = 0.1

WELLSPRING_SHARED_SECRET = os.environ.get("WELLSPRING_SHARED_SECRET", "")