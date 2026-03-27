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

        return {"sub": res.user.id}

    except Exception as e:
        raise HTTPException(401, f"Auth error: {str(e)}")
