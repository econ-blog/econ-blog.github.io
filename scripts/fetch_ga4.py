#!/usr/bin/env python3
"""
GA4 Analytics Reporter Script for AI Agent
Fetches traffic summary, top pages, traffic sources, and realtime users from Google Analytics 4 Data API.
"""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from credentials import service_account_path  # noqa: E402

DEFAULT_PROPERTY_ID = "546174128"
DEFAULT_DAYS = 7
DEFAULT_LIMIT = 200


def parse_args(argv):
    """[property_id] [--days N] [--limit N]. 기존 위치 인자를 보존한다.

    주간 감사 ②는 28일 조회와 절삭 없는 페이지 목록이 필요하다(SEED AC #14·#16·#23).
    """
    positional, days, limit, unknown = None, DEFAULT_DAYS, DEFAULT_LIMIT, []
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--days" and i + 1 < len(argv):
            days = int(argv[i + 1])
            i += 2
        elif token == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1])
            i += 2
        elif token.isdigit() and positional is None:
            positional = token
            i += 1
        else:
            # 무인 실행에서 오타 하나가 조용히 기본값을 쓰게 두지 않는다
            unknown.append(token)
            i += 1
    if unknown:
        print(f"경고: 알 수 없는 인자 {unknown} — 무시한다", file=sys.stderr)
    return positional, max(1, days), max(1, limit)


def get_credentials_path():
    return service_account_path()


def main():
    credentials_path = get_credentials_path()

    if not credentials_path or not os.path.exists(credentials_path):
        print(json.dumps({
            "error": "Credentials file not found.",
            "hint": "저장소 루트에 credentials.json을 두거나 GA4_CREDENTIALS로 서비스 계정 키 경로를 넘긴다."
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    positional_id, days, limit = parse_args(sys.argv[1:])
    property_id = os.environ.get("GA4_PROPERTY_ID") or positional_id or DEFAULT_PROPERTY_ID
    window = f"{days}daysAgo"

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange, Dimension, Metric, RunReportRequest, RunRealtimeReportRequest
        )
    except ImportError:
        print(json.dumps({
            "error": "google-analytics-data package not installed.",
            "hint": "Run: .venv/bin/pip install google-analytics-data"
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    client = BetaAnalyticsDataClient()

    # Realtime Check
    realtime_request = RunRealtimeReportRequest(
        property=f"properties/{property_id}",
        metrics=[Metric(name="activeUsers")],
        dimensions=[Dimension(name="deviceCategory"), Dimension(name="country")]
    )
    realtime_response = client.run_realtime_report(realtime_request)
    
    total_realtime_users = 0
    realtime_details = []
    for row in realtime_response.rows:
        count = int(row.metric_values[0].value)
        total_realtime_users += count
        realtime_details.append({
            "device": row.dimension_values[0].value,
            "country": row.dimension_values[1].value,
            "activeUsers": count
        })

    # 1. Overall Traffic Summary
    summary_request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=window, end_date="today")],
        metrics=[
            Metric(name="activeUsers"),
            Metric(name="screenPageViews"),
            Metric(name="sessions"),
            Metric(name="averageSessionDuration")
        ]
    )
    summary_response = client.run_report(summary_request)

    # 2. Top Pages
    pages_request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=window, end_date="today")],
        dimensions=[Dimension(name="pagePath"), Dimension(name="pageTitle")],
        # sessions는 주간 감사 ②의 후행 지표다 — 사이트 전체 summary에만 있으면
        # 주제군별 합계를 만들 수 없다(SEED AC #15의 세션 대체 경로).
        metrics=[Metric(name="screenPageViews"), Metric(name="activeUsers"),
                 Metric(name="sessions")],
        limit=limit
    )
    pages_response = client.run_report(pages_request)

    # 3. Traffic Sources
    sources_request = RunReportRequest(
        property=f"properties/{property_id}",
        date_ranges=[DateRange(start_date=window, end_date="today")],
        dimensions=[Dimension(name="sessionSource")],
        metrics=[Metric(name="activeUsers"), Metric(name="sessions")],
        limit=limit
    )
    sources_response = client.run_report(sources_request)

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
            "activeUsers": int(row.metric_values[1].value),
            "sessions": int(row.metric_values[2].value)
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
        "realtimeActiveUsers": total_realtime_users,
        "realtimeBreakdown": realtime_details,
        "dateRange": f"Last {days} Days",
        "days": days,
        "limit": limit,
        "summary": summary_data,
        "topPages": top_pages,
        "trafficSources": traffic_sources
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
