from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import settings

GVIZ_ENDPOINT_TEMPLATE = "https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
GVIZ_RESPONSE_MARKER = "google.visualization.Query.setResponse("
GVIZ_DATE_PATTERN = re.compile(r"(?:new\s+)?Date\(([^)]*)\)")
PUBLIC_SHEET_TIMEOUT_SECONDS = 20
FIELD_RECORD_HEADER_FALLBACKS = {
    0: "조사지",
    1: "조사일시",
    2: "조사자",
    3: "날씨",
    4: "기온",
    5: "풍속",
    6: "조사 범위",
    7: "조사 방식",
    8: "촬영",
    9: "보호구역 상태",
    10: "특기사항",
    11: "생물 다양성 상태",
    12: "위협 요인",
    13: "훼손 오염 상태",
    14: "사진 영상 자료 1",
    15: "사진 영상 자료 2",
    16: "사진 영상 자료 3",
    17: "사진 영상 자료 4",
    18: "사진 영상 자료 5",
}


@dataclass(frozen=True)
class ParsedSheets:
    basic_infos: list[dict]
    field_records: list[dict]


class SheetFetchError(RuntimeError):
    pass


def _build_gviz_url(sheet_name: str) -> str:
    query_string = urlencode(
        {
            "tqx": "out:json",
            "headers": "0",
            "sheet": sheet_name,
        }
    )
    return GVIZ_ENDPOINT_TEMPLATE.format(sheet_id=settings.SHEET_ID) + "?" + query_string


def _fetch_sheet_text(sheet_name: str) -> str:
    request = Request(
        _build_gviz_url(sheet_name),
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "Mozilla/5.0",
        },
    )

    try:
        with urlopen(request, timeout=PUBLIC_SHEET_TIMEOUT_SECONDS) as response:
            return response.read().decode("utf-8")
    except HTTPError as exc:
        raise SheetFetchError(
            f"Failed to fetch public Google Sheet '{sheet_name}' "
            f"(HTTP {exc.code}). Make sure the spreadsheet is publicly viewable."
        ) from exc
    except URLError as exc:
        raise SheetFetchError(
            f"Failed to connect to Google Sheets for '{sheet_name}': {exc.reason}"
        ) from exc


def _extract_response_payload(response_text: str, sheet_name: str) -> dict:
    start = response_text.find(GVIZ_RESPONSE_MARKER)
    if start == -1:
        preview = re.sub(r"\s+", " ", response_text[:160]).strip()
        raise SheetFetchError(
            f"Public Google Sheets response for '{sheet_name}' was not JSON. "
            f"Make sure the spreadsheet is publicly viewable. Preview: {preview}"
        )

    start += len(GVIZ_RESPONSE_MARKER)
    end = response_text.rfind(");")
    if end == -1:
        end = response_text.rfind(")")

    if end == -1 or end <= start:
        raise SheetFetchError(
            f"Could not parse the public Google Sheets response for '{sheet_name}'."
        )

    payload = response_text[start:end].strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        normalized_payload = GVIZ_DATE_PATTERN.sub(_replace_gviz_date_literal, payload)
        if normalized_payload == payload:
            raise SheetFetchError(
                f"Could not decode public Google Sheets JSON for '{sheet_name}'."
            ) from exc

        try:
            return json.loads(normalized_payload)
        except json.JSONDecodeError as normalized_exc:
            raise SheetFetchError(
                f"Could not decode public Google Sheets JSON for '{sheet_name}'."
            ) from normalized_exc


def _replace_gviz_date_literal(match: re.Match[str]) -> str:
    raw_parts = [part.strip() for part in match.group(1).split(",") if part.strip()]

    try:
        parts = [int(part) for part in raw_parts]
    except ValueError:
        return json.dumps(match.group(0))

    while len(parts) < 6:
        parts.append(0)

    year, zero_based_month, day, hour, minute, second = parts[:6]
    try:
        dt = datetime(year, zero_based_month + 1, day, hour, minute, second)
    except ValueError:
        return json.dumps(match.group(0))

    return json.dumps(dt.isoformat(sep=" "))


def _cell_to_string(cell) -> str:
    if cell is None:
        return ""

    formatted_value = cell.get("f")
    if formatted_value not in (None, ""):
        return str(formatted_value)

    value = cell.get("v")
    if value is None:
        return ""
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)


def _fetch_values(sheet_name: str) -> list[list[str]]:
    response_text = _fetch_sheet_text(sheet_name)
    payload = _extract_response_payload(response_text, sheet_name)
    rows = payload.get("table", {}).get("rows", [])

    return [
        [_cell_to_string(cell) for cell in (row.get("c") or [])]
        for row in rows
    ]


def _pad_row(row: list[str], width: int) -> list[str]:
    return row + [""] * max(0, width - len(row))


def _normalize_field_record_headers(headers: list[str]) -> list[str]:
    normalized = list(headers)
    for index, fallback in FIELD_RECORD_HEADER_FALLBACKS.items():
        if index >= len(normalized):
            normalized.extend([""] * (index + 1 - len(normalized)))
        if not normalized[index].strip():
            normalized[index] = fallback
    return normalized


def fetch_basic_info_rows() -> list[dict]:
    values = _fetch_values(settings.BASIC_INFO_SHEET_NAME)
    if len(values) < 3:
        return []

    headers = values[1]
    rows: list[dict] = []

    for raw_row in values[2:]:
        if not any(cell.strip() for cell in raw_row):
            continue
        row = _pad_row(raw_row, len(headers))
        rows.append(dict(zip(headers, row)))

    return rows


def fetch_field_record_rows() -> list[dict]:
    values = _fetch_values(settings.FIELD_RECORDS_SHEET_NAME)
    if len(values) < 2:
        return []

    headers = _normalize_field_record_headers(values[0])
    rows: list[dict] = []

    for raw_row in values[1:]:
        if not any(cell.strip() for cell in raw_row):
            continue
        row = _pad_row(raw_row, len(headers))
        rows.append(dict(zip(headers, row)))

    return rows


def get_parsed_sheets() -> ParsedSheets:
    return ParsedSheets(
        basic_infos=fetch_basic_info_rows(),
        field_records=fetch_field_record_rows(),
    )
