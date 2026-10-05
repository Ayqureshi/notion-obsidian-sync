"""
daily_digest.py -- Writes a "Today's To-Do List" toggle block onto the
Ameezymane's Dashboard Notion page, listing everything due today or
overdue (and not finished) across all three task databases.

Safe to re-run: it finds its own toggle block by its marker text and
replaces its contents each time, rather than appending duplicates.
"""
import os
from datetime import datetime, date

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ["NOTION_TOKEN"]
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

DASHBOARD_PAGE_ID = "0833878f-7fd5-4524-8bff-b2b70ecf8549"
MARKER = "Today's To-Do List"

SOURCES = [
    {
        "label": "Personal Tasks",
        "db_id": os.environ.get("NOTION_LAB_DB_ID"),
        "title_prop": "Name",
        "due_prop": "Due Date",
    },
    {
        "label": "Research To-Do List",
        "db_id": os.environ.get("NOTION_RESEARCH_DB_ID"),
        "title_prop": "Name",
        "due_prop": "Due Date",
    },
    {
        "label": "Class & TA Notes",
        "db_id": os.environ.get("NOTION_DATABASE_ID"),
        "title_prop": "name",
        "due_prop": "due date",
    },
]


def get_title(page, prop_name):
    prop = page.get("properties", {}).get(prop_name, {})
    parts = prop.get("title", [])
    return "".join(p.get("plain_text", "") for p in parts) or "(untitled)"


def get_due_date(page, prop_name):
    date_obj = page.get("properties", {}).get(prop_name, {}).get("date")
    if not date_obj or not date_obj.get("start"):
        return None
    raw = date_obj["start"]
    try:
        return datetime.fromisoformat(raw).date()
    except ValueError:
        return None


def is_finished(page):
    return page.get("properties", {}).get("Finished", {}).get("checkbox", False)


def collect_due_items():
    today = date.today()
    items = []
    for source in SOURCES:
        db_id = source["db_id"]
        if not db_id:
            continue
        res = requests.post(f"https://api.notion.com/v1/databases/{db_id}/query", headers=HEADERS)
        if res.status_code != 200:
            print(f"  [!] Could not query {source['label']}: {res.text}")
            continue
        for page in res.json().get("results", []):
            if is_finished(page):
                continue
            due = get_due_date(page, source["due_prop"])
            if due is None or due > today:
                continue
            title = get_title(page, source["title_prop"])
            overdue = due < today
            items.append({"label": source["label"], "title": title, "due": due, "overdue": overdue})
    return items


def build_children(items):
    if not items:
        return [{
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"text": {"content": "Nothing due today. 🎉"}}]},
        }]

    children = []
    by_label = {}
    for item in items:
        by_label.setdefault(item["label"], []).append(item)

    for label, group in by_label.items():
        children.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {"rich_text": [{"text": {"content": label}}]},
        })
        for item in group:
            suffix = f" (overdue since {item['due'].isoformat()})" if item["overdue"] else ""
            children.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"text": {"content": f"{item['title']}{suffix}"}}],
                    "checked": False,
                },
            })
    return children


def find_existing_toggle():
    res = requests.get(f"https://api.notion.com/v1/blocks/{DASHBOARD_PAGE_ID}/children", headers=HEADERS)
    res.raise_for_status()
    for block in res.json().get("results", []):
        if block.get("type") != "toggle":
            continue
        text = "".join(t.get("plain_text", "") for t in block["toggle"].get("rich_text", []))
        if MARKER in text:
            return block["id"]
    return None


def clear_children(block_id):
    res = requests.get(f"https://api.notion.com/v1/blocks/{block_id}/children", headers=HEADERS)
    res.raise_for_status()
    for child in res.json().get("results", []):
        requests.delete(f"https://api.notion.com/v1/blocks/{child['id']}", headers=HEADERS)


def append_children(block_id, children):
    # Notion caps children-per-request; our lists are small so one call is fine.
    res = requests.patch(
        f"https://api.notion.com/v1/blocks/{block_id}/children",
        headers=HEADERS,
        json={"children": children},
    )
    res.raise_for_status()


def main():
    items = collect_due_items()
    children = build_children(items)
    now_label = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    toggle_id = find_existing_toggle()
    if toggle_id:
        print(f"Updating existing toggle ({toggle_id})...")
        clear_children(toggle_id)
        append_children(toggle_id, children)
    else:
        print("Creating new toggle block...")
        res = requests.patch(
            f"https://api.notion.com/v1/blocks/{DASHBOARD_PAGE_ID}/children",
            headers=HEADERS,
            json={"children": [{
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"text": {"content": f"\U0001F4CB {MARKER}"}}],
                    "children": children,
                },
            }]},
        )
        res.raise_for_status()

    print(f"Done. {len(items)} item(s) due today or overdue, as of {now_label}.")


if __name__ == "__main__":
    main()
