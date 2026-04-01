# db.py
from supabase import create_client, Client

SUPABASE_URL = "SECRET"

SUPABASE_SERVICE_KEY = "SECRET"

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_user_client(token: str) -> Client:
    """Creates a Supabase client that runs queries as the authenticated user."""
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    client.postgrest.auth(token)
    return client
