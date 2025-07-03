from dotenv import load_dotenv
from supabase import Client, create_client
import os
import logging
# Load environment variables from .env file
load_dotenv()   

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-1.5-flash")  # Default to Gemini if not set

logging.info(f"GOOGLE_API_KEY loaded: {bool(GOOGLE_API_KEY)}")

supabase: Client = create_client(
    supabase_url=SUPABASE_URL,
    supabase_key=SUPABASE_KEY
)