"""
╔══════════════════════════════════════════════════════════════════╗
║  ÆTHELGARD OS — Logging System                                   ║
║  File: core/logger.py                                            ║
║                                                                  ║
║  Central logging for Thotheauphis — rotating file output,       ║
║  crash tracking, sensitive data filtering.                       ║
║                                                                  ║
║  SECTIONS:                                                       ║
║    1. Imports and path constants                                 ║
║    2. Sensitive data filter (API keys, passwords, tokens)        ║
║    3. Logger factory (file + console handlers)                   ║
║    4. Global crash handler                                       ║
║    5. Convenience accessor                                       ║
╚══════════════════════════════════════════════════════════════════╝
"""

# ── Section 1: Imports and path constants ────────────────────────────────────

import logging
import logging.handlers
import traceback
import re
import sys
from datetime import datetime
from pathlib import Path

# All runtime data lives under data/ relative to the project root
DATA_DIR = Path(__file__).parent.parent / "data"
LOG_DIR  = DATA_DIR / "logs"

# Rotating file: 5 MB per file, 3 backups kept → max ~20 MB total on disk
MAX_LOG_BYTES   = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3


# ── Section 2: Sensitive data filter ────────────────────────────────────────
# These patterns are stripped from every log record before it is written.
# This prevents API keys, bearer tokens, and passwords from appearing in logs.

_SENSITIVE_PATTERNS = [
    # Generic long API keys starting with sk-
    (re.compile(r"(sk-[a-zA-Z0-9]{20,})", re.IGNORECASE), "***API_KEY***"),
    # Bearer tokens in Authorization headers
    (re.compile(r"(Bearer\s+[a-zA-Z0-9\-._~+/]+=*)", re.IGNORECASE), "Bearer ***"),
    # JSON "api_key" fields
    (re.compile(r'("api_key"\s*:\s*")[^"]+(")', re.IGNORECASE), r"\1***\2"),
    # JSON "password" fields
    (re.compile(r'("password"\s*:\s*")[^"]+(")', re.IGNORECASE), r"\1***\2"),
    # JSON "token" fields
    (re.compile(r'("token"\s*:\s*")[^"]+(")', re.IGNORECASE), r"\1***\2"),
]


class SensitiveDataFilter(logging.Filter):
    """
    Logging filter that redacts secrets from every log record.

    Iterates through _SENSITIVE_PATTERNS and replaces matches in the
    formatted message string before the record reaches any handler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Format the message first so substitution works on the final string
        msg = str(record.getMessage())
        for pattern, replacement in _SENSITIVE_PATTERNS:
            msg = pattern.sub(replacement, msg)
        # Overwrite msg and clear args so the formatted string is used as-is
        record.msg  = msg
        record.args = ()
        return True  # Always allow the record through (we only redact, never drop)


# ── Section 3: Logger factory ────────────────────────────────────────────────

def setup_logger() -> logging.Logger:
    """
    Build and return the root 'aethelgard' logger.

    Handler configuration:
      - RotatingFileHandler → DEBUG level, all records to disk
      - StreamHandler       → WARNING+ level to stdout only

    Both handlers share the SensitiveDataFilter instance.

    Returns:
        logging.Logger: Configured 'aethelgard' logger instance.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("aethelgard")
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers (handles module reimport gracefully)
    logger.handlers.clear()

    sensitive_filter = SensitiveDataFilter()

    # ── File handler: DEBUG+, rotating, UTF-8 ──
    log_file     = LOG_DIR / "aethelgard.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes    = MAX_LOG_BYTES,
        backupCount = LOG_BACKUP_COUNT,
        encoding    = "utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.addFilter(sensitive_filter)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(file_handler)

    # ── Console handler: WARNING+ only (keeps terminal clean) ──
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.addFilter(sensitive_filter)
    console_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console_handler)

    return logger


# ── Section 4: Global crash handler ─────────────────────────────────────────

def install_crash_handler(logger: logging.Logger):
    """
    Install a sys.excepthook that logs unhandled exceptions to both the
    rotating logger and a dedicated crash log file.

    The crash log file is capped at 1 MB by discarding the older half when
    the limit is reached (simple trimming, no external dependency).

    Args:
        logger: The configured logger to write CRITICAL records to.
    """
    crash_log = LOG_DIR / "crashes.log"

    def handle_exception(exc_type, exc_value, exc_tb):
        # Let KeyboardInterrupt pass through silently (normal user exit)
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical(f"UNHANDLED CRASH:\n{tb_text}")

        # Write to the dedicated crash log, trimming if over 1 MB
        try:
            if crash_log.exists() and crash_log.stat().st_size > 1 * 1024 * 1024:
                content   = crash_log.read_text(encoding="utf-8", errors="replace")
                crash_log.write_text(content[len(content) // 2:], encoding="utf-8")
            with open(crash_log, "a", encoding="utf-8") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(f"CRASH: {datetime.now().isoformat()}\n")
                f.write(f"{'=' * 60}\n")
                f.write(tb_text)
                f.write("\n")
        except Exception:
            pass  # Never let crash logging itself crash the process

        # Delegate to the default hook so the traceback still prints
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = handle_exception


# ── Section 5: Convenience accessor ─────────────────────────────────────────

def get_logger(name: str = "aethelgard") -> logging.Logger:
    """
    Return a named child logger under the 'aethelgard' hierarchy.

    All child loggers inherit handlers from the root 'aethelgard' logger,
    so there is no need to add handlers here.

    Args:
        name: Sub-logger name (e.g. "brain", "memory", "autonomy").

    Returns:
        logging.Logger: Child logger named 'aethelgard.<name>'.
    """
    return logging.getLogger(f"aethelgard.{name}")


# Module-level convenience instance — import and use directly
log = setup_logger()
