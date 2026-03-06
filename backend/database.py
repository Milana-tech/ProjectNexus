import os
import psycopg
from dotenv import load_dotenv

# Load environment variables (important if running locally)
load_dotenv()

def get_connection():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")

    return psycopg.connect(database_url)
