import jwt
from functools import wraps
from flask import request, jsonify, g
import os

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")



def require_auth(roles=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "Authorization header missing or malformed"}), 401

            token = auth_header.split(" ")[1]

            try:
                payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
                user_role = payload.get("role")
                
                if roles and user_role not in roles:
                    return jsonify({"error": "Insufficient permissions"}), 403

                g.user = {
                    "id": payload.get("sub"),
                    "email": payload.get("email"),
                    "role": user_role
                }

            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except jwt.InvalidTokenError:
                return jsonify({"error": "Invalid token"}), 401

            return f(*args, **kwargs)
        return decorated_function
    return decorator
