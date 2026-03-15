import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# LangSmith tracing: set LANGCHAIN_API_KEY in env to enable. Optional LANGCHAIN_PROJECT (default below).
if os.getenv("LANGCHAIN_API_KEY"):
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGCHAIN_PROJECT", "kavin"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")  # Optional: Azure/custom endpoint

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_MB = 20
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}

MONGODB_URI = os.getenv("MONGODB_CONNECTION_STRING", os.getenv("MONGODB_URI", "mongodb://localhost:27017"))
MONGODB_DB = os.getenv("MONGODB_DB", "kavin_scientific")

# Premium on top of model token cost: PREMIUM_PERCENT (e.g. 10 = 10% markup). Default 0.
PREMIUM_PERCENT = max(0.0, min(100.0, float(os.getenv("PREMIUM_PERCENT", "0"))))
