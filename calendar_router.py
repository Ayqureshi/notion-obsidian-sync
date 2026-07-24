import os
import requests
from datetime import datetime
from icalendar import Calendar
from dotenv import load_dotenv

load_dotenv()

# Import your custom function from classification.py
from classification import classify_title

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
ICS_URL = os.environ.get("ICS_URL")

DB_MAP = {
    "All Lab Tasks": os.environ.get("NOTION_LAB_DB_ID"),
    "course work to do": os.environ.get("NOTION_DATABASE_ID"),
    "Research To-Do List": os.environ.get("NOTION_RESEARCH_DB_ID")
}

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

def is_duplicate_event(title, start_iso, database_id):
    query_url = f"https://api.notion.com/v1/databases/{database_id}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Name", "title": {"equals": title}},
                {"property": "Due Date", "date": {"equals": start_iso}}
            ]
        }
    }
    res = requests.post(query_url, json=payload, headers=HEADERS)
    if res.status_code == 200:
        results = res.json().get("results", [])
        return len(results) > 0
    return False

def send_to_notion(title, start_iso, database_id):
    create_url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]},
            "Due Date": {"date": {"start": start_iso}}
        }
    }
    res = requests.post(create_url, json=payload, headers=HEADERS)
    return res.status_code == 200

def get_existing_notion_keys(database_id):
    """Fetches all existing event keys (title + date) from a Notion DB in a single request."""
    query_url = f"https://api.notion.com/v1/databases/{database_id}/query"
    res = requests.post(query_url, headers=HEADERS)
    existing = set()
    if res.status_code == 200:
        for page in res.json().get("results", []):
            props = page.get("properties", {})
            # Extract title
            title_objs = props.get("Name", {}).get("title", [])
            title = title_objs[0].get("text", {}).get("content") if title_objs else None
            # Extract date
            date_obj = props.get("Due Date", {}).get("date")
            start_date = date_obj.get("start") if date_obj else None
            
            if title and start_date:
                existing.add((title, start_date))
    return existing

def sync_calendar():
    if not ICS_URL or not NOTION_TOKEN:
        print("Missing required environment variables. Exiting.")
        return

    res = requests.get(ICS_URL)
    if res.status_code != 200:
        print("Failed to download ICS feed.")
        return

    # Pre-fetch existing entries for each mapped DB (3 API calls total instead of dozens)
    db_cache = {
        db_id: get_existing_notion_keys(db_id) 
        for db_id in DB_MAP.values() if db_id
    }

    cal = Calendar.from_ical(res.content)
    
    for event in cal.walk('VEVENT'):
        title = str(event.get('summary'))
        start_time = event.get('dtstart').dt
        
        start_iso = start_time.isoformat() if isinstance(start_time, datetime) else start_time.strftime("%Y-%m-%d")

        predicted_bin = classify_title(title)
        target_db_id = DB_MAP.get(predicted_bin)

        if not target_db_id:
            continue

        # In-memory instant check (Zero API calls!)
        if (title, start_iso) in db_cache[target_db_id]:
            print(f"Skipping duplicate: '{title}' [{start_iso}]")
            continue

        if send_to_notion(title, start_iso, target_db_id):
            print(f"Event: '{title}' ---> Routed to: '{predicted_bin}'")
            # Update local set so same-run duplicates are caught
            db_cache[target_db_id].add((title, start_iso))

if __name__ == "__main__":
    sync_calendar()