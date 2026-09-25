from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db import supabase

bearer_scheme = HTTPBearer()


async def get_raw_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
) -> str:
    return credentials.credentials


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
):
    token = credentials.credentials

    try:
        res = supabase.auth.get_user(token)

        if not res.user:
            raise HTTPException(401, "Invalid token")

        meta = res.user.user_metadata or {}
        email = res.user.email or ""
        username = email[: -len("@persona-lens.local")] if email.endswith("@persona-lens.local") else email
        return {"sub": res.user.id, "username": username, "full_name": (meta.get("full_name") or "").strip()}

    except Exception as e:
        raise HTTPException(401, f"Auth error: {str(e)}")
