from __future__ import annotations

import base64
import os
import re

import requests

import config

GITHUB_API_BASE = "https://api.github.com"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {config.GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _sanitize_segment(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "-", value.strip())
    cleaned = cleaned.strip("-._")
    return cleaned or "unknown"


def _get_existing_sha(repo_path: str) -> str | None:
    url = (
        f"{GITHUB_API_BASE}/repos/"
        f"{config.GITHUB_OWNER}/{config.GITHUB_REPO}/contents/{repo_path}"
    )
    response = requests.get(
        url,
        headers=_headers(),
        params={"ref": config.GITHUB_BRANCH},
        timeout=30,
    )
    if response.status_code == 200:
        return response.json().get("sha")
    return None


def upload(local_path: str, location: str, month_key: str) -> dict:
    file_name = os.path.basename(local_path)
    ext = os.path.splitext(file_name)[1].lower()
    safe_location = _sanitize_segment(location)
    safe_month = _sanitize_segment(month_key)
    repo_path = f"{config.MEDIA_BASE_PATH}/{safe_location}/{safe_month}/{file_name}"

    with open(local_path, "rb") as file_obj:
        content_b64 = base64.b64encode(file_obj.read()).decode("utf-8")

    payload = {
        "message": f"Upload media: {safe_location}/{safe_month}/{file_name}",
        "content": content_b64,
        "branch": config.GITHUB_BRANCH,
    }

    sha = _get_existing_sha(repo_path)
    if sha:
        payload["sha"] = sha

    url = (
        f"{GITHUB_API_BASE}/repos/"
        f"{config.GITHUB_OWNER}/{config.GITHUB_REPO}/contents/{repo_path}"
    )

    try:
        response = requests.put(url, json=payload, headers=_headers(), timeout=60)
        response.raise_for_status()

        raw_url = (
            f"https://raw.githubusercontent.com/"
            f"{config.GITHUB_OWNER}/{config.GITHUB_REPO}/"
            f"{config.GITHUB_BRANCH}/{repo_path}"
        )

        if ext in IMAGE_EXTENSIONS:
            resource_type = "image"
        elif ext in VIDEO_EXTENSIONS:
            resource_type = "video"
        else:
            resource_type = "unknown"

        return {
            "url": raw_url,
            "resource_type": resource_type,
            "repo_path": repo_path,
        }
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)
