# db.py
from supabase import create_client, Client

SUPABASE_URL = "https://pffshbkpvbxakvblflzw.supabase.co"
# from Supabase → Settings → API
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBmZnNoYmtwdmJ4YWt2YmxmbHp3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NDYwNTIxMiwiZXhwIjoyMDkwMTgxMjEyfQ.Q1fCdxOy-e5jg6g2etOuta6vwgQ3dreKRK7ib_qfuYM"

# Service client (bypasses RLS — use only when needed)
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_user_client(token: str) -> Client:
    """Creates a Supabase client that runs queries as the authenticated user."""
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    client.postgrest.auth(token)
    return client
