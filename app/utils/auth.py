import jwt
from functools import wraps
from flask import request, jsonify, g
from flask_restx import abort
import os

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")


def require_auth(roles=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                abort(401, "Authorization header missing or malformed")

            token = auth_header.split(" ")[1]

            try:
                payload = jwt.decode(
                    token,
                    SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    audience="authenticated",
                )
                user_role = payload.get("role")

                if roles and user_role not in roles:
                    abort(403, "Insufficient permissions")

                g.user = {
                    "id": payload.get("sub"),
                    "email": payload.get("email"),
                    "role": user_role,
                }

            except jwt.ExpiredSignatureError:
                abort(401, "Token expired")
            except jwt.InvalidTokenError:
                abort(401, "Invalid token")

            return f(*args, **kwargs)

        return decorated_function

    return decorator
