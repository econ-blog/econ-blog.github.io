import os
import sys
import json
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'ga4-credentials.json')
SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly']

def get_search_console_service():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Error: Credentials file not found at {CREDENTIALS_FILE}")
        sys.exit(1)
    
    credentials = service_account.Credentials.from_service_account_file(
        CREDENTIALS_FILE, scopes=SCOPES
    )
    return build('searchconsole', 'v1', credentials=credentials)

def list_sites():
    service = get_search_console_service()
    sites = service.sites().list().execute()
    return sites.get('siteEntry', [])

def fetch_search_analytics(site_url, days=90, dimensions=['query']):
    service = get_search_console_service()
    
    end_date = datetime.now() - timedelta(days=2)
    start_date = end_date - timedelta(days=days)
    
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    request = {
        'startDate': start_date_str,
        'endDate': end_date_str,
        'dimensions': dimensions,
        'rowLimit': 50,
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
            'data': results
        }
    except Exception as e:
        print(f"API Error ({site_url}): {e}")
        return None

def main():
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
