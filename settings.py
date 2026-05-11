from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# Google Sheets
SHEET_ID = os.getenv("SHEET_ID", "")
BASIC_INFO_SHEET_NAME = os.getenv("BASIC_INFO_SHEET_NAME", "")
FIELD_RECORDS_SHEET_NAME = os.getenv("FIELD_RECORDS_SHEET_NAME", "")

# 캐시
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))

# CORS
CORS_ALLOW_ORIGIN = os.getenv("CORS_ALLOW_ORIGIN", "*")
