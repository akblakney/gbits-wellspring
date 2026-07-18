"""
Central configuration for Wellspring.

Barebones for now — just what's needed to get the pool + serve endpoint
working. TTL, archive settings, beacon settings, etc. will grow here later.
"""

from pathlib import Path
import os

# How long a chunk may sit in the pool before it's considered expired
# and should be swept out (archived).
POOL_TTL_SECONDS = 60

# How often the (stubbed) generator produces a new chunk.
#GENERATOR_INTERVAL_SECONDS = 0.50

# HTTP server settings.
#API_HOST = "127.0.0.1"  # for local testing
API_HOST = "10.8.0.2"
API_PORT = 8000

# Rough empirical estimate of sustained generation throughput, used only
# to size MAX_BITS_PER_REQUEST below. Update this once real mic-based
# generation is wired in and you have a measured rate.
ESTIMATED_GENERATION_RATE_BYTES_PER_SECOND = 1024  # ~1KB/sec, per your experience

# Expected steady-state pool capacity: roughly what accumulates in one
# full TTL window (POOL_TTL_SECONDS) if nothing is being served/expired
# yet. This is a ceiling estimate, not a hard cap (pool is unbounded).
ESTIMATED_POOL_CAPACITY_BYTES = ESTIMATED_GENERATION_RATE_BYTES_PER_SECOND * POOL_TTL_SECONDS

# Upper bound on how many bits a single /bits request may ask for.
# Deliberately kept well under a full minute's worth of generation, so
# one request can't plausibly drain everything that would accumulate
# in the expiry window (leaves room for other concurrent requests and,
# later, the beacon). Currently set to 1/4 of the estimated one-minute
# pool capacity — revisit once real throughput and traffic are known.
MAX_BYTES_PER_REQUEST = 2048

# --- Archive settings ---

# Root directory for archived raw entropy (.bin) and metadata (.meta.jsonl)
# files, laid out as <ARCHIVE_ROOT_PATH>/<YYYY-MM-DD>/<HH>.bin (+.meta.jsonl).
# Defaults to <wellspring project root>/data/archive. Override to point at
# whatever disk/volume you want the (forever-retained) archive to live on.
ARCHIVE_ROOT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "archive"

# Written into each hour's metadata header record, so archived data is
# traceable to the generator/extractor version that produced it. Bump
# this manually when generation logic changes meaningfully.
ARCHIVE_FORMAT_VERSION = 1

# BEACON
BEACON_ROOT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "beacon"
BEACON_PULSE_INTERVAL_SECONDS = 60
BEACON_OUTPUT_BYTES = 64
BEACON_WAIT_TIMEOUT_SECONDS = 5.0
BEACON_WAIT_POLL_INTERVAL_SECONDS = 0.1

WELLSPRING_SHARED_SECRET = os.environ.get("WELLSPRING_SHARED_SECRET", "")