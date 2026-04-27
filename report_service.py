from __future__ import annotations

import json
from pathlib import Path

import config


def _load_dataset() -> dict:
    path = Path(config.OUTPUT_FILE)
    if not path.exists():
        raise FileNotFoundError(
            f"{config.OUTPUT_FILE} 파일이 없습니다. 먼저 build_json.build()를 실행해주세요."
        )

    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def get_location_report_summary(location_name: str) -> dict:
    dataset = _load_dataset()
    location = dataset.get("locations", {}).get(location_name)

    if not location:
        return {
            "location": location_name,
            "exists": False,
            "report_count": 0,
            "available_months": [],
            "latest_month": None,
        }

    return {
        "location": location_name,
        "exists": True,
        "report_count": location.get("report_count", 0),
        "available_months": location.get("available_months", []),
        "latest_month": location.get("latest_month"),
    }


def get_location_report(location_name: str, month: str) -> dict:
    dataset = _load_dataset()
    location = dataset.get("locations", {}).get(location_name)

    if not location:
        return {
            "location": location_name,
            "month": month,
            "exists": False,
            "message": "해당 지역 데이터가 없습니다.",
        }

    monthly_report = location.get("reports_by_month", {}).get(month)
    if not monthly_report:
        return {
            "location": location_name,
            "month": month,
            "exists": False,
            "message": "해당 월의 모니터링 보고서가 없습니다.",
            "available_months": location.get("available_months", []),
        }

    return {
        "location": location_name,
        "month": month,
        "exists": True,
        "basic_info": location.get("basic_info", {}),
        "report_count_for_month": len(monthly_report.get("records", [])),
        "records": monthly_report.get("records", []),
    }
