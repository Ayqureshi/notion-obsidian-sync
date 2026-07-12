from datetime import datetime
import json
import os
from dotenv import load_dotenv
import requests

# -------------------------------------------------------------------
# Environment & Setup
# -------------------------------------------------------------------
load_dotenv()

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = os.environ.get("NOTION_DATABASE_ID")
BASE_DIR = os.environ.get("OBSIDIAN_BASE_DIR")

url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

COURSE_MAP = {
    "ec8ef0fd-44a1-8252-a4b9-01cc6d08aab2": "Linguistics",
    "609ef0fd-44a1-8301-bc13-013b0071b59b": "Psychology",
}

# -------------------------------------------------------------------
# Fetch Notion Tasks
# -------------------------------------------------------------------
var = requests.post(url, headers=headers).json()
results = var.get("results", [])

for tasks in results:
    # 1. Assignment Name
    title_list = tasks["properties"].get("name", {}).get("title", [])
    assignment_name = (
        title_list[0]["plain_text"] if title_list else "Untitled Task"
    )

    # 2. Due Date Formatting
    date_obj = tasks["properties"].get("due date", {}).get("date")
    raw_date = date_obj.get("start") if date_obj else "No Due Date"

    if raw_date != "No Due Date":
        dt = datetime.fromisoformat(raw_date)
        due_date = dt.strftime("%B %d, %Y at %I:%M %p")
    else:
        due_date = "No Due Date"

    # 3. Status & Priority
    status_obj = tasks["properties"].get("completion", {}).get("status")
    status = status_obj.get("name") if status_obj else "No Status"

    priority_obj = tasks["properties"].get("priority", {}).get("status")
    priority = priority_obj.get("name") if priority_obj else "No Priority"

    # 4. Course Identification
    course_list = tasks["properties"].get("courses", {}).get("relation", [])
    course_id = course_list[0]["id"] if course_list else None
    course_name = (
        COURSE_MAP.get(course_id, "Unknown Course")
        if course_id
        else "No Course"
    )

    print(f"Assignment:  {assignment_name}")
    print(f"Status:      {status}")
    print(f"Priority:    {priority}")
    print(f"Due Date:    {due_date}")
    print(f"Course Name: {course_name}")
    print("-" * 30)

    # 5. Check Role via Course Page API
    is_ta = "student"
    if course_id:
        course_url = f"https://api.notion.com/v1/pages/{course_id}"
        c = requests.get(course_url, headers=headers).json()

        is_ta_obj = c.get("properties", {}).get("role", {}).get("select")
        if is_ta_obj:
            is_ta = is_ta_obj.get("name", "student").lower()

    folder = "12_TA-ship" if is_ta == "ta" else "11_Classes"
    print(f"Role:        {is_ta}")

    # 6. Build Target Directory & Filepath
    target_dir = os.path.join(BASE_DIR, folder, course_name)
    os.makedirs(target_dir, exist_ok=True)

    safe_title = (
        assignment_name.replace("/", "-").replace(":", "-").replace("?", "")
    )
    filepath = os.path.join(target_dir, f"{safe_title}.md")

    # 7. Write Markdown File
    if not os.path.exists(filepath):
        md_content = f"""---
priority: {priority}
status: {status}
due_date: {due_date}
course: {course_name}
role: {is_ta}
---

# {assignment_name}

## Notes
- 
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Created new Obsidian note: {filepath}")
    else:
        print(f"Note already exists (Skipping): {filepath}")