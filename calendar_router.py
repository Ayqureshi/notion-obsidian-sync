from datetime import datetime
import os
import re
import requests
from dotenv import load_dotenv
from icalendar import Calendar
from classification import classify_course, classify_title

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

COURSE_PAGE_CACHE = {}

# -------------------------------------------------------------------
# Helper & Route Logic
# -------------------------------------------------------------------
def get_title_from_page(page: dict) -> str:
    """Extracts the title without depending on a particular property name."""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            return "".join(part.get("plain_text", "") for part in title_parts)
    return ""


def get_course_page_id(course_name: str) -> str | None:
    """Finds a course page through the coursework database's relation schema."""
    course_key = course_name.casefold()
    if course_key in COURSE_PAGE_CACHE:
        return COURSE_PAGE_CACHE[course_key]

    try:
        database_url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}"
        database_res = requests.get(database_url, headers=HEADERS)
        if database_res.status_code != 200:
            print(f"  [!] Could not inspect coursework database: {database_res.text}")
            return None

        properties = database_res.json().get("properties", {})
        course_property = properties.get("courses") or properties.get("Course")
        related_db_id = (course_property or {}).get("relation", {}).get("database_id")
        if not related_db_id:
            print("  [!] The coursework database has no usable courses relation.")
            return None

        query_url = f"https://api.notion.com/v1/databases/{related_db_id}/query"
        query_res = requests.post(query_url, headers=HEADERS)
        if query_res.status_code != 200:
            print(f"  [!] Could not query the courses database: {query_res.text}")
            return None

        for page in query_res.json().get("results", []):
            page_title = get_title_from_page(page)
            COURSE_PAGE_CACHE[page_title.casefold()] = page.get("id")

        return COURSE_PAGE_CACHE.get(course_key)
    except requests.RequestException as error:
        print(f"  [!] Could not resolve course '{course_name}': {error}")
        return None


def set_course_on_page(page_id: str, course_name: str) -> bool:
    """Assigns a classified course to an existing coursework page."""
    course_page_id = get_course_page_id(course_name)
    if not course_page_id:
        return False

    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "courses": {"relation": [{"id": course_page_id}]}
        }
    }
    response = requests.patch(url, headers=HEADERS, json=payload)
    if response.status_code == 200:
        return True
    print(f"  [!] Could not assign course '{course_name}': {response.text}")
    return False


def page_exists_in_notion(
    db_id: str,
    title: str,
    start_dt: datetime,
    title_property: str,
    date_property: str,
) -> dict | bool | None:
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
            return results[0] if results else False
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
    category = classify_title(event_title)
    course_name = classify_course(event_title)

    # Course aliases take priority so "Lab Visual Language" is not mistaken
    # for a general lab-work item.
    if course_name:
        return {
            "db_id": NOTION_DATABASE_ID,
            "label": "Class & TA Notes",
            "category": course_name,
            "course_name": course_name,
            "title_property": "name",
            "date_property": "due date",
        }

    if category == "All Lab Tasks":
        return {
            "db_id": NOTION_LAB_DB_ID,
            "label": "Lab Work",
            "category": "Lab Work",
            "course_name": None,
            "title_property": "Name",
            "date_property": "Due Date",
        }

    if category == "Research To-Do List":
        return {
            "db_id": NOTION_RESEARCH_DB_ID,
            "label": "Research To-Do List",
            "category": "Research To-Do List",
            "course_name": None,
            "title_property": "Name",
            "date_property": "Due Date",
        }

    # 2. ABSOLUTE CATCH-ALL FALLBACK (Guarantees 100% routing rate)
    return {
        "db_id": NOTION_DATABASE_ID,
        "label": "Class & TA Notes",
        "category": "General Coursework",
        "course_name": None,
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
    course_name: str | None = None,
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

    if course_name:
        course_page_id = get_course_page_id(course_name)
        if course_page_id:
            payload["properties"]["courses"] = {
                "relation": [{"id": course_page_id}]
            }
        else:
            print(
                f"  [!] Course page '{course_name}' was not found; "
                "creating the event without a course."
            )

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
                course_name = route["course_name"]
                if course_name and set_course_on_page(
                    duplicate_status["id"], course_name
                ):
                    print(f"  [~] Assigned existing '{summary}' -> ({course_name})")
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
                route["course_name"],
            ):
                events_processed += 1

    print(f"\nDone! Processed {events_processed} new calendar events.")

if __name__ == "__main__":
    run_calendar_sync()
