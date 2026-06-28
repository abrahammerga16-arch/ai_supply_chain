"""
Supabase client connection.
Loads credentials from .env file — never hardcode keys in this file.
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError(
            "Missing Supabase credentials. "
            "Copy .env.example to .env and fill in your SUPABASE_URL and SUPABASE_KEY."
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)
