"""Mint a Supabase-shaped JWT for local API testing.

Signs with SUPABASE_JWT_SECRET from the environment (or .env via scripts.env_loader),
matching what app/utils/auth.py verifies. Usage:

    python scripts/dev_token.py
    curl -H "Authorization: Bearer $(python scripts/dev_token.py)" \
         http://localhost:8080/data-tracker/daily/2026-08-01
"""
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.env_loader import load_dotenv  # noqa: E402

import jwt  # noqa: E402


def main() -> None:
    load_dotenv()
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        sys.exit("SUPABASE_JWT_SECRET is not set (create .env from .env.example)")

    now = int(time.time())
    payload = {
        "sub": str(uuid.uuid4()),
        "email": "dev@local.test",
        "role": "authenticated",
        "aud": "authenticated",
        "iat": now,
        "exp": now + 12 * 3600,
    }
    print(jwt.encode(payload, secret, algorithm="HS256"))


if __name__ == "__main__":
    main()
