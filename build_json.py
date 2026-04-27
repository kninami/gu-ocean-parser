from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import config
import drive_downloader
import github_uploader
import sheets_parser

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi"}


def _clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_month(recorded_at: str) -> str:
    value = _clean_text(recorded_at)
    if not value:
        return "unknown"

    normalized = value.replace(".", "-").replace("/", "-").replace("년", "-")
    normalized = normalized.replace("월", "").replace("일", "").replace(" ", "")

    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y-%m-%d%H:%M:%S"):
        try:
            dt = datetime.strptime(normalized, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue

    if len(normalized) >= 7 and normalized[4] == "-":
        return normalized[:7]

    return value


def _process_media(media_link: str, location: str, month_key: str) -> dict:
    photos: list[dict] = []
    videos: list[dict] = []

    for file_info in drive_downloader.collect_media_files(media_link):
        file_name = file_info["name"]
        ext = os.path.splitext(file_name)[1].lower()
        local_path = drive_downloader.download_file(file_info["id"], file_name)
        uploaded = github_uploader.upload(local_path, location, month_key)

        entry = {
            "name": file_name,
            "url": uploaded["url"],
            "repo_path": uploaded["repo_path"],
        }

        if ext in IMAGE_EXTENSIONS:
            photos.append(entry)
        elif ext in VIDEO_EXTENSIONS:
            videos.append(entry)

    return {"photos": photos, "videos": videos}


def _build_location_map(
    basic_infos: list[dict],
    field_records: list[dict],
) -> dict[str, dict]:
    basic_info_by_location = {
        _clean_text(item.get(config.BASIC_INFO_LOCATION_COLUMN)): item
        for item in basic_infos
        if _clean_text(item.get(config.BASIC_INFO_LOCATION_COLUMN))
    }

    locations: dict[str, dict] = {}

    for raw_record in field_records:
        location = _clean_text(raw_record.get(config.LOCATION_COLUMN))
        if not location:
            continue

        month_key = _normalize_month(raw_record.get(config.RECORDED_AT_COLUMN, ""))
        record = {
            key: value
            for key, value in raw_record.items()
            if key != config.MEDIA_LINK_COLUMN
        }
        record["month"] = month_key
        record["media"] = _process_media(
            raw_record.get(config.MEDIA_LINK_COLUMN, ""),
            location,
            month_key,
        )

        location_bucket = locations.setdefault(
            location,
            {
                "location": location,
                "basic_info": basic_info_by_location.get(location, {}),
                "available_months": [],
                "reports_by_month": {},
            },
        )

        month_bucket = location_bucket["reports_by_month"].setdefault(
            month_key,
            {
                "month": month_key,
                "basic_info": location_bucket["basic_info"],
                "records": [],
            },
        )
        month_bucket["records"].append(record)

    for location_bucket in locations.values():
        available_months = sorted(location_bucket["reports_by_month"].keys())
        location_bucket["available_months"] = available_months
        location_bucket["report_count"] = len(available_months)
        location_bucket["latest_month"] = available_months[-1] if available_months else None

    return locations


def build() -> dict:
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    parsed = sheets_parser.get_parsed_sheets()
    locations = _build_location_map(parsed.basic_infos, parsed.field_records)

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "locations": locations,
    }

    with open(config.OUTPUT_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(output, file_obj, ensure_ascii=False, indent=2)

    print(f"저장 완료: {config.OUTPUT_FILE} ({len(locations)}개 지역)")
    return output
