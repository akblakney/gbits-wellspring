"""
Centralized logging setup for Wellspring.

Call configure_logging() once, early, from main.py. Every other module
just does:

    import logging
    logger = logging.getLogger(__name__)

and logger.debug(...)/info(...)/warning(...)/error(...) calls will
automatically respect whatever level was configured here — no per-file
setup needed.

Level is controlled by the WELLSPRING_LOG_LEVEL env var (falls back to
INFO if unset or invalid), so you can run in debug mode without touching
code:

    WELLSPRING_LOG_LEVEL=DEBUG python main.py

configure_logging() also accepts an explicit level override, which takes
priority over the env var — useful for a --debug CLI flag (wired up in
main.py).
"""

import logging
import os
from pathlib import Path
from datetime import date

_DEFAULT_LEVEL = "INFO"
_ENV_VAR = "WELLSPRING_LOG_LEVEL"
LOG_BASE_DIR = Path(__file__).resolve().parent.parent.parent / "log"


def configure_logging(level: str | None = None) -> None:
    """
    Configure root logging once at startup.

    Priority: explicit `level` arg > WELLSPRING_LOG_LEVEL env var > INFO.
    """
    resolved = (level or os.environ.get(_ENV_VAR) or _DEFAULT_LEVEL).upper()

    numeric_level = getattr(logging, resolved, None)
    if not isinstance(numeric_level, int):
        logging.basicConfig(level=logging.INFO)
        logging.getLogger(__name__).warning(
            "Invalid log level '%s', falling back to INFO", resolved
        )
        return

    log_dir = LOG_BASE_DIR
    log_file = log_dir / f"{date.today():%Y-%m-%d}.log"

    logging.basicConfig(
        filename=log_file,
        level=numeric_level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.getLogger(__name__).debug("Logging configured at level %s", resolved)