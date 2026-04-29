from __future__ import annotations

from flask import Flask, jsonify, request

import data_service
import google_credentials

app = Flask(__name__)


def _wants_refresh() -> bool:
    value = (request.args.get("refresh") or "").strip().lower()
    return value in {"1", "true", "yes", "y"}


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
    return jsonify(
        {
            "service": "greenpeace-sea-api",
            "endpoints": [
                "/health",
                "/locations",
                "/locations/<location_name>",
                "/locations/<location_name>?month=YYYY-MM",
            ],
        }
    )


@app.get("/health")
def health():
    return jsonify(
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

    return jsonify(
        {
            "last_updated": dataset.get("last_updated"),
            "locations": items,
        }
    )


@app.get("/locations/<path:location_name>")
def get_location(location_name: str):
    dataset = data_service.get_dataset(force_refresh=_wants_refresh())
    location = dataset.get("locations", {}).get(location_name)

    if location is None:
        return (
            jsonify(
                {
                    "message": "Location not found.",
                    "location": location_name,
                }
            ),
            404,
        )

    month = request.args.get("month")
    if not month:
        return jsonify(location)

    monthly_report = location.get("reports_by_month", {}).get(month)
    if monthly_report is None:
        return (
            jsonify(
                {
                    "message": "Month not found for location.",
                    "location": location_name,
                    "month": month,
                    "available_months": location.get("available_months", []),
                }
            ),
            404,
        )

    return jsonify(
        {
            "location": location_name,
            "basic_info": location.get("basic_info", {}),
            "month": month,
            "records": monthly_report.get("records", []),
            "available_months": location.get("available_months", []),
        }
    )
