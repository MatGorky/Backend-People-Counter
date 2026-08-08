"""Minimal .env loader so scripts work without extra dependencies or a Makefile.

Loads KEY=VALUE lines from the repo-root .env into os.environ (existing environment
variables win). Not a general dotenv implementation — just enough for local dev.
"""

import os


def load_dotenv(path: str | None = None) -> None:
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value
