from __future__ import annotations

import json
import os

from flask import Flask, request

import data_service
import google_credentials

app = Flask(__name__)


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


def _get_location_response(location_name: str):
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

    month = request.args.get("month")
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


@app.before_request
def _bind_vercel_oidc_token() -> None:
    google_credentials.set_request_oidc_token(
        request.headers.get("x-vercel-oidc-token")
    )


@app.teardown_request
def _clear_vercel_oidc_token(exc) -> None:
    google_credentials.set_request_oidc_token(None)


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
    location_name = (request.args.get("name") or "").strip()
    if not location_name:
        return _json_response(
            {
                "message": "Missing required query parameter: name",
            },
            status=400,
        )

    return _get_location_response(location_name)


@app.get("/locations/<path:location_name>")
def get_location(location_name: str):
    return _get_location_response(location_name)


if __name__ == "__main__":
    run_dev_server()
