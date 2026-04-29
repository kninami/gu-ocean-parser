from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# Google Sheets
SHEET_ID = os.getenv("SHEET_ID", "")
BASIC_INFO_SHEET_NAME = os.getenv("BASIC_INFO_SHEET_NAME", "기본정보")
FIELD_RECORDS_SHEET_NAME = os.getenv("FIELD_RECORDS_SHEET_NAME", "현장 조사 기록")

# 캐시
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))

# 로컬 fallback용 서비스 계정 파일 경로
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "credentials.json")
