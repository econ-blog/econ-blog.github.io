import os
import sys
import json
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

DEFAULT_SITE_URL = 'https://econ-blog.github.io/'

def get_credentials_path():
    credentials_path = (
        os.environ.get("GSC_CREDENTIALS")
        or os.environ.get("GA4_CREDENTIALS")
        or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )
    if not credentials_path:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_path = os.path.join(base_dir, 'ga4-credentials.json')
        if os.path.exists(default_path):
            credentials_path = default_path
    return credentials_path

def get_site_url():
    return os.environ.get("GSC_SITE_URL") or DEFAULT_SITE_URL

CREDENTIALS_FILE = get_credentials_path()
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']
DEFAULT_DAYS = 90
# ②는 page 차원 합계로 n_g·m_g를 만든다 — 절삭되면 조용히 틀린 수치가 나온다.
DEFAULT_LIMIT = 200
INSPECT_CAP = 5


def parse_args(argv):
    """[--json] [--days N] [--limit N] [--dimensions a,b] [--sitemaps] [--inspect url…]"""
    opts = {"json": False, "days": DEFAULT_DAYS, "limit": DEFAULT_LIMIT,
            "dimensions": ["query", "page"], "sitemaps": False, "inspect": [],
            "unknown": []}
    i = 0
    while i < len(argv):
        token = argv[i]
        if token == "--json":
            opts["json"] = True
            i += 1
        elif token == "--days" and i + 1 < len(argv):
            opts["days"] = max(1, int(argv[i + 1]))
            i += 2
        elif token == "--limit" and i + 1 < len(argv):
            opts["limit"] = max(1, int(argv[i + 1]))
            i += 2
        elif token == "--dimensions" and i + 1 < len(argv):
            opts["dimensions"] = [d.strip() for d in argv[i + 1].split(",") if d.strip()]
            i += 2
        elif token == "--sitemaps":
            opts["sitemaps"] = True
            i += 1
        elif token == "--inspect":
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                opts["inspect"].append(argv[i])
                i += 1
        else:
            # 무인 실행에서 오타 하나가 조용히 기본값을 쓰게 두지 않는다
            opts["unknown"].append(token)
            i += 1
    if opts["unknown"]:
        print(f"경고: 알 수 없는 인자 {opts['unknown']} — 무시한다", file=sys.stderr)
    return opts


def property_type(site_url):
    """AC #28 I7 — 도메인 속성인지 URL 접두어 속성인지."""
    return "domain" if site_url.startswith("sc-domain:") else "url-prefix"


def fetch_sitemaps(site_url):
    """AC #28 I4. lastDownloaded는 아직 읽히지 않은 sitemap에는 없다 — 옵셔널로 다룬다."""
    service = get_search_console_service()
    response = service.sitemaps().list(siteUrl=site_url).execute()
    return [{
        "path": s.get("path"),
        "lastSubmitted": s.get("lastSubmitted"),
        "lastDownloaded": s.get("lastDownloaded"),
        "isPending": s.get("isPending"),
        "warnings": s.get("warnings"),
        "errors": s.get("errors"),
    } for s in response.get("sitemap", [])]


def inspect_urls(site_url, urls):
    """AC #28 I6 — 일일 할당량 때문에 최대 INSPECT_CAP건만. coverageState는 가공하지 않는다."""
    service = get_search_console_service()
    out = []
    for url in urls[:INSPECT_CAP]:
        body = {"inspectionUrl": url, "siteUrl": site_url}
        result = service.urlInspection().index().inspect(body=body).execute()
        status = result.get("inspectionResult", {}).get("indexStatusResult", {})
        out.append({
            "url": url,
            "verdict": status.get("verdict"),
            "coverage_state": status.get("coverageState"),
            "last_crawl_time": status.get("lastCrawlTime"),
            "robots_txt_state": status.get("robotsTxtState"),
        })
    return out


def get_search_console_service():
    cred_file = get_credentials_path()
    if not cred_file or not os.path.exists(cred_file):
        print(f"Error: Credentials file not found at {cred_file}")
        sys.exit(1)
    
    credentials = service_account.Credentials.from_service_account_file(
        cred_file, scopes=SCOPES
    )
    return build('searchconsole', 'v1', credentials=credentials)

def list_sites():
    service = get_search_console_service()
    sites = service.sites().list().execute()
    return sites.get('siteEntry', [])

def fetch_search_analytics(site_url, days=90, dimensions=['query'], limit=DEFAULT_LIMIT):
    service = get_search_console_service()
    
    end_date = datetime.now() - timedelta(days=2)
    start_date = end_date - timedelta(days=days)
    
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    request = {
        'startDate': start_date_str,
        'endDate': end_date_str,
        'dimensions': dimensions,
        'rowLimit': limit,
    }
    
    try:
        response = service.searchanalytics().query(siteUrl=site_url, body=request).execute()
        rows = response.get('rows', [])
        
        results = []
        for row in rows:
            key_name = ", ".join(row['keys'])
            clicks = row.get('clicks', 0)
            impressions = row.get('impressions', 0)
            ctr = round(row.get('ctr', 0) * 100, 2)
            position = round(row.get('position', 0), 1)
            
            results.append({
                'key': key_name,
                'clicks': clicks,
                'impressions': impressions,
                'ctr_percent': ctr,
                'position': position
            })
            
        return {
            'site_url': site_url,
            'dimensions': dimensions,
            'start_date': start_date_str,
            'end_date': end_date_str,
            'total_rows': len(results),
            'truncated': len(results) >= limit,
            'data': results
        }
    except Exception as e:
        print(f"API Error ({site_url}): {e}", file=sys.stderr)
        return None

def main():
    opts = parse_args(sys.argv[1:])

    if opts["json"]:
        try:
            sites = list_sites()
            if not sites:
                print(json.dumps({"error": "GSC에 접근 가능한 사이트가 없다",
                                  "stage": "list_sites"}, ensure_ascii=False))
                sys.exit(1)
            site_url = os.environ.get("GSC_SITE_URL") or (sites[0].get("siteUrl") if sites else DEFAULT_SITE_URL)
            payload = {
                "site_url": site_url,
                "property_type": property_type(site_url),
                "permission_level": sites[0].get("permissionLevel"),
                "days": opts["days"],
                "limit": opts["limit"],
                "analytics": {},
                "sitemaps": None,
                "inspections": None,
            }
            for dim in opts["dimensions"]:
                res = fetch_search_analytics(site_url, days=opts["days"],
                                             dimensions=[dim], limit=opts["limit"])
                if res is None:
                    # 0행과 조회 실패는 다른 판정이다 (AC #26·#29) — 스테이지가
                    # 구분할 수 있게 페이로드 안에 남긴다. stderr는 읽히지 않는다.
                    payload["analytics"][dim] = {"ok": False, "error": "조회 실패"}
                    continue
                payload["analytics"][dim] = {
                    "ok": True,
                    "total_rows": res.get("total_rows", 0),
                    "truncated": res.get("truncated", False),
                    "start_date": res.get("start_date"),
                    "end_date": res.get("end_date"),
                    "data": res.get("data", []),
                }
            if opts["sitemaps"]:
                payload["sitemaps"] = fetch_sitemaps(site_url)
            if opts["inspect"]:
                payload["inspections"] = inspect_urls(site_url, opts["inspect"])
                if len(opts["inspect"]) > INSPECT_CAP:
                    payload["truncated"] = True
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return
        except Exception as exc:  # 스테이지가 "조회 실패"와 "0행"을 구분해야 한다
            print(json.dumps({"error": str(exc), "stage": "json_mode"},
                             ensure_ascii=False))
            sys.exit(1)

    sites = list_sites()
    if not sites:
        print("No sites accessible.")
        return

    site_url = sites[0].get('siteUrl')
    print(f"Checking 90 days query analytics for: {site_url}")
    
    res_query = fetch_search_analytics(site_url, days=90, dimensions=['query'])
    print("\n--- Top Search Queries (90 Days) ---")
    print(json.dumps(res_query, ensure_ascii=False, indent=2))

    res_page = fetch_search_analytics(site_url, days=90, dimensions=['page'])
    print("\n--- Top Landing Pages (90 Days) ---")
    print(json.dumps(res_page, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
