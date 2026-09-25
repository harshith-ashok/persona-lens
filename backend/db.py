# db.py
import os

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_user_client(token: str) -> Client:
    """Creates a Supabase client that runs queries as the authenticated user."""
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    client.postgrest.auth(token)
    return client


def ensure_patient(patient_id: str) -> None:
    """Make sure the patients row exists, without touching the name if it already does."""
    supabase.table("patients").upsert(
        {"id": patient_id, "full_name": "Patient"}, ignore_duplicates=True
    ).execute()
