import os
from functools import wraps

import jwt
from flask import g, request
from flask_restx import abort


def require_auth(fn=None, roles=None):
    """Verify the Supabase HS256 JWT. Usable both bare and called:

    @require_auth
    @require_auth()
    @require_auth(roles=["service_role"])
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                abort(401, "Authorization header missing or malformed")

            token = auth_header.split(" ", 1)[1]
            try:
                payload = jwt.decode(
                    token,
                    os.environ.get("SUPABASE_JWT_SECRET", ""),
                    algorithms=["HS256"],
                    audience="authenticated",
                )
            except jwt.ExpiredSignatureError:
                abort(401, "Token expired")
            except jwt.InvalidTokenError:
                abort(401, "Invalid token")

            user_role = payload.get("role")
            if roles and user_role not in roles:
                abort(403, "Insufficient permissions")

            g.user = {
                "id": payload.get("sub"),
                "email": payload.get("email"),
                "role": user_role,
                # App-level role from Supabase app_metadata (set via dashboard; spec-003).
                "app_role": (payload.get("app_metadata") or {}).get("role"),
            }
            return f(*args, **kwargs)

        return decorated_function

    if callable(fn):  # used as @require_auth without parentheses
        return decorator(fn)
    return decorator
