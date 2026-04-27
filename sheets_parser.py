from __future__ import annotations

from dataclasses import dataclass

from googleapiclient.discovery import build

import config
import google_credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


@dataclass(frozen=True)
class ParsedSheets:
    basic_infos: list[dict]
    field_records: list[dict]


def _get_service():
    creds = google_credentials.get_credentials(SCOPES)
    return build("sheets", "v4", credentials=creds)


def _fetch_values(sheet_name: str) -> list[list[str]]:
    service = _get_service()
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=config.SHEET_ID,
        range=sheet_name,
    ).execute()
    return result.get("values", [])


def _pad_row(row: list[str], width: int) -> list[str]:
    return row + [""] * max(0, width - len(row))


def fetch_basic_info_rows() -> list[dict]:
    values = _fetch_values(config.BASIC_INFO_SHEET_NAME)
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
    values = _fetch_values(config.FIELD_RECORDS_SHEET_NAME)
    if len(values) < 2:
        return []

    headers = values[0]
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
