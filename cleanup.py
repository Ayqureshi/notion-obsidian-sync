"""
cleanup.py -- Removes synced Obsidian notes whose Notion source is gone,
finished, or flagged "No Obsidian MD". automation.py only ever creates
files; this is the matching delete-side pass it is missing.

Dry-run by default (prints what it would remove). Pass --apply to
actually delete. Cleans both the local repo and the live Obsidian
vault (OBSIDIAN_BASE_DIR) using plain file deletion only -- no git,
no content reads against the vault, so it does not hit the iCloud
materialization issues git/rsync run into there.
"""
import os
import subprocess
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

from automation import (
    HEADERS,
    sanitize_filename,
    process_personal_task,
    process_research_task,
    process_class_and_ta_task,
)

load_dotenv()

REPO_DIR = Path(__file__).resolve().parent
VAULT_DIR = os.environ.get("OBSIDIAN_BASE_DIR")

PIPELINES = [
    {
        "db_id": os.environ.get("NOTION_LAB_DB_ID"),
        "relative_base": os.path.join("20_Areas", "21_Personal-Tasks"),
        "parser": process_personal_task,
        "label": "Personal Tasks",
    },
    {
        "db_id": os.environ.get("NOTION_RESEARCH_DB_ID"),
        "relative_base": os.path.join("20_Areas", "22_PhD-Research"),
        "parser": process_research_task,
        "label": "Research To-Do List",
    },
    {
        "db_id": os.environ.get("NOTION_DATABASE_ID"),
        "relative_base": "10_Projects",
        "parser": process_class_and_ta_task,
        "label": "Class & TA Notes",
    },
]


def is_finished(page) -> bool:
    return page.get("properties", {}).get("Finished", {}).get("checkbox", False)


def skip_obsidian_sync(page) -> bool:
    return page.get("properties", {}).get("No Obsidian MD", {}).get("checkbox", False)


def expected_files_for_pipeline(pipeline, root: Path) -> set[Path]:
    """Every .md path that should currently exist under `root` for this pipeline."""
    db_id = pipeline["db_id"]
    if not db_id:
        return set()

    res = requests.post(f"https://api.notion.com/v1/databases/{db_id}/query", headers=HEADERS)
    if res.status_code != 200:
        print(f"  [!] Could not query {pipeline['label']}: {res.text}")
        return set()

    base_folder = root / pipeline["relative_base"]
    expected = set()
    for page in res.json().get("results", []):
        if is_finished(page) or skip_obsidian_sync(page):
            continue
        title, _content, target_folder = pipeline["parser"](page, str(base_folder))
        safe_title = sanitize_filename(title)
        expected.add((Path(target_folder) / f"{safe_title}.md").resolve())
    return expected


def clean_root(root: Path, label: str, apply: bool) -> int:
    if not root.exists():
        print(f"Skipping {label}: {root} does not exist.")
        return 0

    print(f"\n=== Cleaning {label} ({root}) ===")
    all_expected: set[Path] = set()
    scan_roots = set()
    for pipeline in PIPELINES:
        if not pipeline["db_id"]:
            continue
        all_expected |= expected_files_for_pipeline(pipeline, root)
        scan_roots.add(root / pipeline["relative_base"])

    removed = 0
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*.md"):
            if path.resolve() not in all_expected:
                action = "Removing" if apply else "Would remove"
                print(f"  [-] {action} orphaned note: {path.relative_to(root)}")
                if apply:
                    path.unlink()
                removed += 1

    verb = "Removed" if apply else "Would remove"
    print(f"{label}: {verb} {removed} orphaned note(s).")
    return removed


def main():
    apply = "--apply" in sys.argv
    if not apply:
        print("Dry run (pass --apply to actually delete).")

    repo_removed = clean_root(REPO_DIR, "Local repo", apply)
    vault_removed = 0
    if VAULT_DIR:
        vault_removed = clean_root(Path(VAULT_DIR), "Obsidian vault", apply)
    else:
        print("\nOBSIDIAN_BASE_DIR not set, skipping vault cleanup.")

    total = repo_removed + vault_removed
    if not apply and total:
        print(f"\n{total} total note(s) would be removed. Re-run with --apply to actually delete them.")

    if apply and repo_removed:
        print("\n=== Committing and pushing repo cleanup ===")
        subprocess.run(["git", "add", "-A"], cwd=REPO_DIR, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Cleanup: remove {repo_removed} orphaned/finished note(s)"],
            cwd=REPO_DIR, check=True,
        )
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=REPO_DIR, check=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)


if __name__ == "__main__":
    main()
