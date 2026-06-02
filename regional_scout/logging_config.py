"""Logging setup — never emit api_key in log lines."""

from __future__ import annotations

import logging
import re


def redact_secrets(message: str, api_key: str | None = None) -> str:
    if api_key:
        message = message.replace(api_key, "***")
    return re.sub(r"api_key=[^&\s\"']+", "api_key=***", message)


class SecretRedactionFilter(logging.Filter):
    def __init__(self, api_key: str | None = None) -> None:
        super().__init__()
        self.api_key = api_key

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg, self.api_key)
        if record.args:
            record.args = tuple(
                redact_secrets(str(a), self.api_key) if isinstance(a, str) else a
                for a in record.args
            )
        return True


def configure_logging(*, api_key: str | None = None, level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")
    for name in ("httpx", "httpcore", "hpack"):
        logging.getLogger(name).setLevel(logging.WARNING)
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(SecretRedactionFilter(api_key))
