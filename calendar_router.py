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

def sync_calendar():
    if not ICS_URL or not NOTION_TOKEN:
        print("Missing required environment variables. Exiting.")
        return

    res = requests.get(ICS_URL)
    if res.status_code != 200:
        print("Failed to download ICS feed.")
        return

    cal = Calendar.from_ical(res.content)
    
    for event in cal.walk('VEVENT'):
        title = str(event.get('summary'))
        start_time = event.get('dtstart').dt
        
        if isinstance(start_time, datetime):
            start_iso = start_time.isoformat()
        else:
            start_iso = start_time.strftime("%Y-%m-%d")

        # Classify title using imported function
        predicted_bin = classify_title(title)
        target_db_id = DB_MAP.get(predicted_bin)

        if not target_db_id:
            print(f"No DB mapped for '{predicted_bin}'. Skipping.")
            continue

        if is_duplicate_event(title, start_iso, target_db_id):
            print(f"Skipping duplicate: '{title}' [{start_iso}]")
            continue

        if send_to_notion(title, start_iso, target_db_id):
            print(f"Event: '{title}' ---> Routed to: '{predicted_bin}'")

if __name__ == "__main__":
    sync_calendar()