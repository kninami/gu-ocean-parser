from __future__ import annotations

import io
import os
import re
from urllib.parse import parse_qs, urlparse

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

import config
import google_credentials

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".mov", ".avi"}

FOLDER_PATTERNS = (
    re.compile(r"/folders/([a-zA-Z0-9_-]+)"),
    re.compile(r"id=([a-zA-Z0-9_-]+)"),
)
FILE_PATTERNS = (
    re.compile(r"/file/d/([a-zA-Z0-9_-]+)"),
    re.compile(r"[?&]id=([a-zA-Z0-9_-]+)"),
)


def _get_service():
    creds = google_credentials.get_credentials(SCOPES)
    return build("drive", "v3", credentials=creds)


def _extract_ids(link_text: str, patterns: tuple[re.Pattern[str], ...]) -> list[str]:
    ids: list[str] = []

    for token in re.split(r"[\s,\n]+", link_text.strip()):
        if not token:
            continue

        for pattern in patterns:
            match = pattern.search(token)
            if match:
                ids.append(match.group(1))
                break
        else:
            parsed = urlparse(token)
            query_id = parse_qs(parsed.query).get("id", [])
            if query_id:
                ids.append(query_id[0])

    return list(dict.fromkeys(ids))


def extract_folder_ids(link_text: str) -> list[str]:
    if not link_text:
        return []
    return _extract_ids(link_text, FOLDER_PATTERNS)


def extract_file_ids(link_text: str) -> list[str]:
    if not link_text:
        return []
    return _extract_ids(link_text, FILE_PATTERNS)


def list_folder_files(folder_id: str) -> list[dict]:
    if not folder_id:
        return []

    service = _get_service()
    query = f"'{folder_id}' in parents and trashed = false"
    result = service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
        pageSize=1000,
    ).execute()
    files = result.get("files", [])

    return [
        file_info
        for file_info in files
        if os.path.splitext(file_info["name"])[1].lower() in ALLOWED_EXTENSIONS
    ]


def get_file_metadata(file_id: str) -> dict:
    service = _get_service()
    return service.files().get(fileId=file_id, fields="id, name, mimeType").execute()


def collect_media_files(link_text: str) -> list[dict]:
    if not link_text:
        return []

    collected: list[dict] = []

    for folder_id in extract_folder_ids(link_text):
        collected.extend(list_folder_files(folder_id))

    for file_id in extract_file_ids(link_text):
        metadata = get_file_metadata(file_id)
        ext = os.path.splitext(metadata["name"])[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            collected.append(metadata)

    unique_by_id: dict[str, dict] = {}
    for item in collected:
        unique_by_id[item["id"]] = item

    return list(unique_by_id.values())


def download_file(file_id: str, file_name: str) -> str:
    """
    file_id 파일을 tmp_media/ 디렉터리에 다운로드하고 로컬 경로를 반환.
    """
    os.makedirs(config.TMP_DIR, exist_ok=True)
    local_path = os.path.join(config.TMP_DIR, file_name)

    service = _get_service()
    request = service.files().get_media(fileId=file_id)

    with io.FileIO(local_path, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    return local_path
