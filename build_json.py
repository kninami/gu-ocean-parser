from __future__ import annotations

from datetime import datetime, timezone

import sheets_parser

LOCATION_HEADER = "조사지"
BASIC_INFO_LOCATION_HEADER = "보호구역명"
RECORDED_AT_HEADER = "조사일시"
MEDIA_LINK_PREFIX = "사진 영상 자료"

DEFAULT_HEADER_KEY_MAP = {
    "조사지": "target_location",
    "보호구역명": "protected_area_name",
    "소재지": "address",
    "지정일자": "designation_date",
    "지정근거": "designation_basis",
    "면적": "area",
    "보호구역 유형": "protected_area_type",
    "주요 표지판 위치": "main_signage_locations",
    "관리주체": "managing_authority",
    "관리조직": "managing_organization",
    "연락처": "contact",
    "깃대종 및 주요 생물군": "flagship_species_and_key_taxa",
    "생태계 유형 및 특기사항": "ecosystem_type_and_notes",
    "주요 어업 및 양식업": "main_fisheries_and_aquaculture",
    "관광 및 레저활동": "tourism_and_leisure_activities",
    "시설 및 인프라": "facilities_and_infrastructure",
    "특기사항": "notes",
    "오각형 이미지": "pentagon_image_url",
    "조사일시": "survey_datetime",
    "조사자": "surveyor",
    "날씨": "weather",
    "기온": "temperature",
    "풍속": "wind_speed",
    "조사 범위": "survey_scope",
    "조사 방식": "survey_method",
    "촬영": "capture_tools",
    "보호구역 상태": "protected_area_status",
    "생물 다양성 상태": "biodiversity_status",
    "위협 요인": "threat_factors",
    "훼손 오염 상태": "damage_and_pollution_status",
}


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


def _get_media_prefix() -> str:
    return MEDIA_LINK_PREFIX


def _get_header_key_map() -> dict[str, str]:
    return DEFAULT_HEADER_KEY_MAP


def _collect_media_column_names(raw_record: dict) -> list[str]:
    prefix = _get_media_prefix()
    columns: list[str] = []

    if prefix:
        discovered_columns = sorted(
            key
            for key in raw_record
            if _clean_text(key) == prefix or _clean_text(key).startswith(prefix + " ")
        )
        for column in discovered_columns:
            if column not in columns:
                columns.append(column)

    return columns


def _make_fallback_key(label: str, existing_keys: set[str]) -> str:
    base_key = "field"
    candidate = base_key
    index = 1
    while candidate in existing_keys:
        candidate = f"{base_key}_{index}"
        index += 1
    return candidate


def _structure_fields(raw_record: dict) -> dict[str, str]:
    header_key_map = _get_header_key_map()
    structured: dict[str, str] = {}

    for label, value in raw_record.items():
        cleaned_label = _clean_text(label)
        if not cleaned_label:
            continue

        key = header_key_map.get(cleaned_label)
        if not key:
            key = _make_fallback_key(cleaned_label, set(structured))

        structured[key] = value

    return structured


def _collect_basic_info_match_keys(item: dict) -> list[str]:
    keys: list[str] = []

    configured_key = _clean_text(item.get(BASIC_INFO_LOCATION_HEADER))
    if configured_key:
        keys.append(configured_key)

    location_key = _clean_text(item.get(LOCATION_HEADER))
    if location_key and location_key not in keys:
        keys.append(location_key)

    return keys


def _build_media_links(raw_record: dict, media_columns: list[str]) -> list[str]:
    image_urls: list[str] = []

    for column in media_columns:
        value = _clean_text(raw_record.get(column, ""))
        if not value:
            continue

        image_urls.append(value)

    return image_urls


def _build_location_map(
    basic_infos: list[dict],
    field_records: list[dict],
) -> dict[str, dict]:
    basic_info_by_location: dict[str, dict] = {}
    for item in basic_infos:
        for match_key in _collect_basic_info_match_keys(item):
            basic_info_by_location.setdefault(match_key, item)

    locations: dict[str, dict] = {}

    for raw_record in field_records:
        location = _clean_text(raw_record.get(LOCATION_HEADER))
        if not location:
            continue

        month_key = _normalize_month(raw_record.get(RECORDED_AT_HEADER, ""))
        media_columns = _collect_media_column_names(raw_record)
        record_fields = {
            key: value
            for key, value in raw_record.items()
            if key not in media_columns
        }
        record = _structure_fields(record_fields)
        record["month"] = month_key
        record["image_urls"] = _build_media_links(raw_record, media_columns)

        location_bucket = locations.setdefault(
            location,
            {
                "location": location,
                "basic_info": _structure_fields(
                    basic_info_by_location.get(location, {})
                ),
                "available_months": [],
                "reports_by_month": {},
            },
        )

        month_bucket = location_bucket["reports_by_month"].setdefault(
            month_key,
            {
                "month": month_key,
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


def generate_dataset() -> dict:
    parsed = sheets_parser.get_parsed_sheets()
    locations = _build_location_map(parsed.basic_infos, parsed.field_records)

    return {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "locations": locations,
    }
