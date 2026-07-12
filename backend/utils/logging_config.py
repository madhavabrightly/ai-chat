"""
Memory Twin AI — Structured Logging Configuration

Sets up JSON-structured logging for production observability.
JSON logs are parseable by Loki, Datadog, CloudWatch, etc.

Falls back to plain text if python-json-logger is not installed.
"""
import logging
import sys


def setup_logging(level: int = logging.INFO):
    """
    Configure root logger with JSON formatting if available, else plain text.
    Call once at startup (in lifespan).
    """
    root = logging.getLogger()
    # Avoid duplicate handlers on reload
    if root.handlers and any(getattr(h, "_mt_configured", False) for h in root.handlers):
        return

    root.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)

    try:
        from pythonjsonlogger import jsonlogger
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            rename_fields={"asctime": "ts"},
        )
        handler.setFormatter(formatter)
        handler._mt_configured = True  # type: ignore[attr-defined]
    except ImportError:
        # Fallback: plain text with timestamps
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler._mt_configured = True  # type: ignore[attr-defined]

    root.handlers = [handler]
