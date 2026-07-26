from datetime import datetime
import os
import re
import requests
from dotenv import load_dotenv
from icalendar import Calendar

# -------------------------------------------------------------------
# Setup & Config
# -------------------------------------------------------------------
load_dotenv()

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
ICS_URL = os.environ.get("ICS_URL")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# Target Databases
NOTION_LAB_DB_ID = os.environ.get("NOTION_LAB_DB_ID")
NOTION_RESEARCH_DB_ID = os.environ.get("NOTION_RESEARCH_DB_ID")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")  # Default Class/TA DB

# Keyword Aliases for Course & Category Resolution
COURSE_ALIASES = {
    "neuro": "Fund Of Cogn Neurosci Lang",
    "neuroscience": "Fund Of Cogn Neurosci Lang",
    "cognition": "Fund Of Cogn Neurosci Lang",
    "csl": "Csl Phd Lectures Series",
    "visual": "Lab Visual Language",
    "lab": "Lab Work",
    "research": "Research To-Do List",
}

# -------------------------------------------------------------------
# Helper & Route Logic
# -------------------------------------------------------------------
def page_exists_in_notion(
    db_id: str,
    title: str,
    start_dt: datetime,
    title_property: str,
    date_property: str,
) -> bool | None:
    """Checks for the same event title and start date.

    Returns None when Notion rejects the query so callers do not create a
    duplicate merely because the duplicate check failed.
    """
    if not db_id:
        return None

    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    date_str = start_dt.isoformat() if isinstance(start_dt, datetime) else str(start_dt)
    payload = {
        "filter": {
            "and": [
                {"property": title_property, "title": {"equals": title}},
                {"property": date_property, "date": {"equals": date_str}},
            ]
        }
    }
    try:
        res = requests.post(url, headers=HEADERS, json=payload)
        if res.status_code == 200:
            results = res.json().get("results", [])
            return len(results) > 0
        print(f"  [!] Could not check for duplicates for '{title}': {res.text}")
    except Exception as e:
        print(f"Error checking duplicate status for '{title}': {e}")
    return None


def determine_target_pipeline(event_title: str) -> dict:
    """
    Guarantees every event gets a route.
    1. Checks keyword aliases.
    2. Defaults to 'Class & TA Notes' (NOTION_DATABASE_ID) as catch-all.
    """
    title_lower = event_title.lower()

    # 1. Match Keyword Aliases
    for keyword, matched_category in COURSE_ALIASES.items():
        if keyword in title_lower:
            if matched_category == "Lab Work" and NOTION_LAB_DB_ID:
                return {
                    "db_id": NOTION_LAB_DB_ID,
                    "label": "Lab Work",
                    "category": matched_category,
                    "title_property": "Name",
                    "date_property": "Due Date",
                }
            elif matched_category == "Research To-Do List" and NOTION_RESEARCH_DB_ID:
                return {
                    "db_id": NOTION_RESEARCH_DB_ID,
                    "label": "Research To-Do List",
                    "category": matched_category,
                    "title_property": "Name",
                    "date_property": "Due Date",
                }
            else:
                return {
                    "db_id": NOTION_DATABASE_ID,
                    "label": "Class & TA Notes",
                    "category": matched_category,
                    "title_property": "name",
                    "date_property": "due date",
                }

    # 2. ABSOLUTE CATCH-ALL FALLBACK (Guarantees 100% routing rate)
    return {
        "db_id": NOTION_DATABASE_ID,
        "label": "Class & TA Notes",
        "category": "General Coursework",
        "title_property": "name",
        "date_property": "due date",
    }


def create_notion_page(
    db_id: str,
    title: str,
    start_dt: datetime,
    category: str,
    title_property: str,
    date_property: str,
) -> bool:
    """Creates a page entry in the target Notion database."""
    url = "https://api.notion.com/v1/pages"
    
    # ISO 8601 string format
    date_str = start_dt.isoformat() if isinstance(start_dt, datetime) else str(start_dt)

    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            title_property: {
                "title": [{"text": {"content": title}}]
            },
            date_property: {
                "date": {"start": date_str}
            }
        }
    }

    res = requests.post(url, headers=HEADERS, json=payload)
    if res.status_code in (200, 201):
        print(f"  [+] Successfully routed '{title}' -> ({category})")
        return True
    else:
        print(f"  [!] Failed to insert '{title}': {res.text}")
        return False

# -------------------------------------------------------------------
# Main Sync Pipeline
# -------------------------------------------------------------------
def run_calendar_sync():
    if not ICS_URL:
        print("Error: ICS_URL environment variable is missing.")
        return

    print("Fetching Outlook ICS feed...")
    response = requests.get(ICS_URL)
    if response.status_code != 200:
        print(f"Failed to fetch ICS feed: {response.status_code}")
        return

    cal = Calendar.from_ical(response.content)
    events_processed = 0

    print("\n=== Processing Calendar Events ===")
    for component in cal.walk():
        if component.name == "VEVENT":
            summary = str(component.get("summary", "Untitled Event"))
            dtstart = component.get("dtstart").dt

            route = determine_target_pipeline(summary)
            target_db_id = route["db_id"]

            if not target_db_id:
                print(f"  [!] Missing DB ID for route '{route['label']}'. Skipping.")
                continue

            # Deduplication check
            duplicate_status = page_exists_in_notion(
                target_db_id,
                summary,
                dtstart,
                route["title_property"],
                route["date_property"],
            )
            if duplicate_status is None:
                print(f"  [!] Skipping '{summary}' because duplicate checking failed.")
                continue
            if duplicate_status:
                print(f"  [-] Already exists in Notion (Skipping): {summary}")
                continue

            # Route and create page
            if create_notion_page(
                target_db_id,
                summary,
                dtstart,
                route["category"],
                route["title_property"],
                route["date_property"],
            ):
                events_processed += 1

    print(f"\nDone! Processed {events_processed} new calendar events.")

if __name__ == "__main__":
    run_calendar_sync()
