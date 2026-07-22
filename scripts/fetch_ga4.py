#!/usr/bin/env python3
"""
GA4 Analytics Reporter Script for AI Agent
Fetches traffic summary, top pages, and traffic sources from Google Analytics 4 Data API.
"""

import os
import sys
import json
from datetime import datetime

DEFAULT_PROPERTY_ID = "546174128"

def main():
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not credentials_path:
        for possible_name in ["ga4-credentials.json", "ga4-credentials.json.json"]:
            if os.path.exists(possible_name):
                credentials_path = possible_name
                break

    if not credentials_path or not os.path.exists(credentials_path):
        print(json.dumps({
            "error": "Credentials file not found.",
            "hint": "Please place your Service Account JSON key file as 'ga4-credentials.json' in the project root."
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    property_id = os.environ.get("GA4_PROPERTY_ID")
    if not property_id:
        if len(sys.argv) > 1 and sys.argv[1].isdigit():
            property_id = sys.argv[1]
        else:
            property_id = DEFAULT_PROPERTY_ID

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest
        )
    except ImportError:
        print(json.dumps({
            "error": "google-analytics-data package not installed.",
            "hint": "Run: .venv/bin/pip install google-analytics-data"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    client = BetaAnalyticsDataClient()

    # 1. Overall Traffic Summary (Last 7 Days)
    summary_request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="screenPageViews"),
            Metric(name="sessions"),
            Metric(name="averageSessionDuration")
        ]
    )
    summary_response = client.run_report(summary_request)

    # 2. Top Pages (Last 7 Days)
    pages_request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
        dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
        metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers")],
        limit=10
    )
    pages_response = client.run_report(pages_request)

    # 3. Traffic Sources (Last 7 Days)
    sources_request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date="7daysAgo", end_date="today")],
        dimensions=[Dimension(name="sessionSource")],
        metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
        limit=10
    )
    sources_response = client.run_report(sources_request)

    # Format results
    summary_data = {}
    if summary_response.rows:
        row = summary_response.rows[0]
        summary_data = {
            "activeUsers": int(row.metric_values[0].value),
            "pageViews": int(row.metric_values[1].value),
            "sessions": int(row.metric_values[2].value),
            "avgSessionDurationSeconds": round(float(row.metric_values[3].value), 1)
        }
    else:
        summary_data = {
            "activeUsers": 0,
            "pageViews": 0,
            "sessions": 0,
            "avgSessionDurationSeconds": 0
        }

    top_pages = []
    for row in pages_response.rows:
        top_pages.append({
            "path": row.dimension_values[0].value,
            "title": row.dimension_values[1].value,
            "pageViews": int(row.metric_values[0].value),
            "activeUsers": int(row.metric_values[1].value)
        })

    traffic_sources = []
    for row in sources_response.rows:
        traffic_sources.append({
            "source": row.dimension_values[0].value,
            "activeUsers": int(row.metric_values[0].value),
            "sessions": int(row.metric_values[1].value)
        })

    report = {
        "fetchedAt": datetime.now().isoformat(),
        "propertyId": property_id,
        "dateRange": "Last 7 Days",
        "summary": summary_data,
        "topPages": top_pages,
        "trafficSources": traffic_sources
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
