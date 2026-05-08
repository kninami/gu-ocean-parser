from __future__ import annotations

import json
import os
import re
import unicodedata

from flask import Flask, request

import data_service
import sheets_parser

app = Flask(__name__)

MAX_LOCATION_NAME_LENGTH = 100
LOCATION_ALLOWED_PUNCTUATION = {" ", "-", "_", ".", "(", ")", "·", ","}
MONTH_PATTERN = re.compile(r"^\d{4}-\d{2}$")


def run_dev_server() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }
    app.run(host=host, port=port, debug=debug)


def _json_response(payload: dict, status: int = 200):
    return app.response_class(
        response=json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        status=status,
        mimetype="application/json",
    )


def _wants_refresh() -> bool:
    value = (request.args.get("refresh") or "").strip().lower()
    return value in {"1", "true", "yes", "y"}


def _normalize_location_name(raw_value: str) -> str:
    return unicodedata.normalize("NFC", raw_value).strip()


def _is_allowed_location_character(char: str) -> bool:
    return char.isalnum() or char in LOCATION_ALLOWED_PUNCTUATION


def _validate_location_name(raw_value: str):
    location_name = _normalize_location_name(raw_value)

    if not location_name:
        return None, _json_response(
            {
                "message": "Missing required location name.",
            },
            status=400,
        )

    if len(location_name) > MAX_LOCATION_NAME_LENGTH:
        return None, _json_response(
            {
                "message": "Location name is too long.",
                "max_length": MAX_LOCATION_NAME_LENGTH,
            },
            status=400,
        )

    if any(not _is_allowed_location_character(char) for char in location_name):
        return None, _json_response(
            {
                "message": "Location name contains unsupported characters.",
            },
            status=400,
        )

    return location_name, None


def _validate_month(month: str | None):
    if not month:
        return None, None

    if not MONTH_PATTERN.fullmatch(month):
        return None, _json_response(
            {
                "message": "Invalid month format. Use YYYY-MM.",
                "month": month,
            },
            status=400,
        )

    return month, None


def _get_location_response(location_name: str):
    month, month_error = _validate_month((request.args.get("month") or "").strip())
    if month_error is not None:
        return month_error

    dataset = data_service.get_dataset(force_refresh=_wants_refresh())
    location = dataset.get("locations", {}).get(location_name)

    if location is None:
        return _json_response(
            {
                "message": "Location not found.",
                "location": location_name,
            },
            status=404,
        )

    if not month:
        return _json_response(location)

    monthly_report = location.get("reports_by_month", {}).get(month)
    if monthly_report is None:
        return _json_response(
            {
                "message": "Month not found for location.",
                "location": location_name,
                "month": month,
                "available_months": location.get("available_months", []),
            },
            status=404,
        )

    return _json_response(
        {
            "location": location_name,
            "basic_info": location.get("basic_info", {}),
            "month": month,
            "records": monthly_report.get("records", []),
            "available_months": location.get("available_months", []),
        }
    )

@app.errorhandler(sheets_parser.SheetFetchError)
def handle_sheet_fetch_error(exc: sheets_parser.SheetFetchError):
    return _json_response(
        {
            "message": str(exc),
        },
        status=502,
    )


@app.get("/")
def index():
    return _json_response(
        {
            "service": "greenpeace-sea-api",
            "endpoints": [
                "/health",
                "/locations",
                "/location?name=신안",
                "/location?name=신안&month=YYYY-MM",
                "/locations/<location_name>",
                "/locations/<location_name>?month=YYYY-MM",
            ],
        }
    )


@app.get("/health")
def health():
    return _json_response(
        {
            "status": "ok",
            **data_service.get_cache_status(),
        }
    )


@app.get("/locations")
def list_locations():
    requested_location_name = request.args.get("name")
    if requested_location_name is not None:
        location_name, error_response = _validate_location_name(requested_location_name)
        if error_response is not None:
            return error_response
        return _get_location_response(location_name)

    dataset = data_service.get_dataset(force_refresh=_wants_refresh())
    locations = dataset.get("locations", {})
    items = []

    for location_name in sorted(locations):
        location = locations[location_name]
        items.append(
            {
                "location": location_name,
                "latest_month": location.get("latest_month"),
                "available_months": location.get("available_months", []),
                "report_count": location.get("report_count", 0),
            }
        )

    return _json_response(
        {
            "last_updated": dataset.get("last_updated"),
            "locations": items,
        }
    )


@app.get("/location")
def get_location_by_query():
    location_name, error_response = _validate_location_name(
        request.args.get("name") or ""
    )
    if error_response is not None:
        return error_response

    return _get_location_response(location_name)


@app.get("/locations/<path:location_name>")
def get_location(location_name: str):
    location_name, error_response = _validate_location_name(location_name)
    if error_response is not None:
        return error_response

    return _get_location_response(location_name)


if __name__ == "__main__":
    run_dev_server()
