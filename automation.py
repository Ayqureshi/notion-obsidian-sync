from datetime import datetime
import os
import requests
from dotenv import load_dotenv

# -------------------------------------------------------------------
# Setup & Config
# -------------------------------------------------------------------
load_dotenv()

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
BASE_DIR = os.environ.get("OBSIDIAN_BASE_DIR", ".")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

COURSE_MAP = {
    "ec8ef0fd-44a1-8252-a4b9-01cc6d08aab2": "Linguistics",
    "609ef0fd-44a1-8301-bc13-013b0071b59b": "Psychology",
}

# -------------------------------------------------------------------
# Helper Parsing Functions
# -------------------------------------------------------------------
def get_plain_text(prop_obj, prop_type="title"):
    """Extracts text safely from various Notion property types."""
    if not prop_obj:
        return ""
    
    if prop_obj.get("type") == "formula":
        formula_data = prop_obj.get("formula", {})
        form_type = formula_data.get("type")
        if form_type == "string":
            return formula_data.get("string", "")
        elif form_type == "number":
            return str(formula_data.get("number", ""))
        return ""

    if prop_type in ["title", "rich_text"]:
        data = prop_obj.get(prop_type, [])
        return data[0]["plain_text"] if data else ""
    elif prop_type == "select":
        sel = prop_obj.get("select")
        return sel.get("name", "") if sel else ""
    elif prop_type == "status":
        stat = prop_obj.get("status")
        return stat.get("name", "") if stat else ""
    return ""

def format_date(date_prop, prop_name="due date"):
    """Formats Notion date ISO string into human readable text."""
    if not date_prop:
        return "No Due Date"
    date_obj = date_prop.get("date")
    if not date_obj:
        return "No Due Date"
    
    raw_date = date_obj.get("start")
    if not raw_date:
        return "No Due Date"
        
    try:
        dt = datetime.fromisoformat(raw_date)
        if prop_name == "due date":
            return dt.strftime("%B %d, %Y at %I:%M %p")
        return dt.strftime("%B %d, %Y")
    except ValueError:
        return raw_date

# -------------------------------------------------------------------
# Custom Pipeline Processors
# -------------------------------------------------------------------
def process_lab_work_task(page, target_folder):
    """Parser tailored to Lab Work properties (Impact, Urgency, Status)."""
    props = page.get("properties", {})
    
    title = get_plain_text(props.get("Name") or props.get("name") or props.get("Task"), "title") or "Untitled Task"
    status = get_plain_text(props.get("Status") or props.get("completion"), "status") or "To do"
    impact = get_plain_text(props.get("Impact"), "select") or "Unspecified Impact"
    urgency = get_plain_text(props.get("Urgency"), "select") or "Unspecified Urgency"
    due_date = format_date(props.get("Due Date") or props.get("due date"), "due date")

    content = f"""---
priority: {impact}
status: {status}
due_date: {due_date}
urgency: {urgency}
type: lab_task
---

# {title}

## Lab Notes
- 
"""
    return title, content, target_folder

def process_research_task(page, target_folder):
    """Parser tailored to Research To-Do List (Category, Priority, Recur)."""
    props = page.get("properties", {})
    
    title = get_plain_text(props.get("Name") or props.get("name"), "title") or "Untitled Task"
    status = get_plain_text(props.get("Status"), "status") or "To do"
    category = get_plain_text(props.get("Category"), "select") or "General"
    priority = get_plain_text(props.get("Priority"), "select") or "Normal"
    due_date = format_date(props.get("Due Date"), "simple")
    recur_interval = get_plain_text(props.get("Recur Interval"), "rich_text") or "None"

    content = f"""---
priority: {priority}
status: {status}
due_date: {due_date}
category: {category}
recurring: {recur_interval}
type: phd_research
---

# {title}

## Research Notes
- 
"""
    return title, content, target_folder

def process_class_and_ta_task(page, target_folder):
    """Dynamic parser that maps via Course Pages & TA roles strictly into 10_Projects."""
    props = page.get("properties", {})
    
    title_list = props.get("name", {}).get("title", [])
    title = title_list[0]["plain_text"] if title_list else "Untitled Task"

    due_date = format_date(props.get("due date"), "due date")

    status_obj = props.get("completion", {}).get("status")
    status = status_obj.get("name") if status_obj else "No Status"

    priority_obj = props.get("priority", {}).get("status")
    priority = priority_obj.get("name") if priority_obj else "No Priority"

    course_list = props.get("courses", {}).get("relation", [])
    course_id = course_list[0]["id"] if course_list else None
    course_name = COURSE_MAP.get(course_id, "No Course") if course_id else "No Course"

    # Deep lookup on Course Page to check for TA role
    is_ta = "student"
    if course_id:
        course_url = f"https://api.notion.com/v1/pages/{course_id}"
        c = requests.get(course_url, headers=HEADERS).json()
        is_ta_obj = c.get("properties", {}).get("role", {}).get("select")
        if is_ta_obj:
            is_ta = is_ta_obj.get("name", "student").lower()

    # Dynamically build destination path inside 10_Projects
    subfolder = "12_TA-ship" if is_ta == "ta" else "11_Classes"
    
    # Ensures path resolves to PhD Notes/10_Projects/11_Classes/<course_name>
    final_folder = os.path.join(target_folder, subfolder, course_name)

    content = f"""---
priority: {priority}
status: {status}
due_date: {due_date}
course: {course_name}
role: {is_ta}
---

# {title}

## Notes
- 
"""
    return title, content, final_folder

# -------------------------------------------------------------------
# Unified Pipeline Matrix
# -------------------------------------------------------------------
SYNC_PIPELINES = [
    {
        "db_id": os.environ.get("NOTION_LAB_DB_ID"),
        "base_folder": os.path.join(BASE_DIR, "20_Areas", "21_Lab-Research"),
        "parser": process_lab_work_task,
        "label": "Lab Work"
    },
    {
        "db_id": os.environ.get("NOTION_RESEARCH_DB_ID"),
        "base_folder": os.path.join(BASE_DIR, "20_Areas", "22_PhD-Research"),
        "parser": process_research_task,
        "label": "Research To-Do List"
    },
    {
        "db_id": os.environ.get("NOTION_DATABASE_ID"),
        "base_folder": os.path.join(BASE_DIR, "10_Projects"), # Explicitly maps under 10_Projects
        "parser": process_class_and_ta_task,
        "label": "Class & TA Notes"
    }
]

def run_sync():
    for pipeline in SYNC_PIPELINES:
        db_id = pipeline["db_id"]
        base_folder = pipeline["base_folder"]
        parse_func = pipeline["parser"]
        label = pipeline["label"]

        if not db_id:
            print(f"Skipping {label}: Database ID missing in environment configurations.")
            continue

        url = f"https://api.notion.com/v1/databases/{db_id}/query"
        res = requests.post(url, headers=HEADERS)

        if res.status_code != 200:
            print(f"Failed to query {label}: {res.text}")
            continue

        pages = res.json().get("results", [])
        print(f"\n=== Syncing Pipeline: {label} ({len(pages)} items) ===")

        for page in pages:
            title, md_content, final_target_dir = parse_func(page, base_folder)
            os.makedirs(final_target_dir, exist_ok=True)
            
            safe_title = title.replace("/", "-").replace(":", "-").replace("?", "")
            filepath = os.path.join(final_target_dir, f"{safe_title}.md")

            if not os.path.exists(filepath):
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(md_content)
                print(f"  [+] Created: {filepath}")
            else:
                print(f"  [-] Exists (Skipping): {filepath}")

if __name__ == "__main__":
    run_sync()
