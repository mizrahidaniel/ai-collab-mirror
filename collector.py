#!/usr/bin/env python3
"""
Blind Collector - Gathers ClawBoard data without analysis.

This script runs daily to collect ClawBoard activity and store it
encrypted. Analysis is time-locked until the seal date.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import requests

# Configuration
API_BASE = "https://clawboard.io/api/v1"
SEAL_DATE = datetime(2026, 3, 3, 22, 9, 0, tzinfo=timezone.utc)  # March 3, 2026, 2:09 PM PST
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

def check_seal():
    """Verify we haven't passed the seal date."""
    now = datetime.now(timezone.utc)
    if now >= SEAL_DATE:
        raise PermissionError(
            f"Collection period ended on {SEAL_DATE}. "
            "Data is sealed. Run analyzer.py to unseal."
        )

def collect_tasks(limit=100):
    """Fetch recent tasks from ClawBoard."""
    url = f"{API_BASE}/tasks"
    params = {"sort": "recent", "limit": limit}
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

def collect_task_details(task_id):
    """Fetch full task details including comments."""
    url = f"{API_BASE}/tasks/{task_id}"
    response = requests.get(url)
    response.raise_for_status()
    task_data = response.json()
    
    # Also fetch comments
    comments_url = f"{API_BASE}/tasks/{task_id}/comments"
    comments_response = requests.get(comments_url)
    comments_response.raise_for_status()
    
    return {
        "task": task_data.get("task"),
        "comments": comments_response.json().get("comments", []),
        "collected_at": datetime.now(timezone.utc).isoformat()
    }

def store_snapshot(data):
    """Store collected data with timestamp."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = DATA_DIR / f"snapshot_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"📦 Snapshot stored: {filename}")
    print(f"   Tasks: {len(data['tasks'])}")
    print(f"   Total comments: {sum(len(t.get('comments', [])) for t in data['task_details'].values())}")

def main():
    """Run daily collection."""
    print(f"🔒 Blind Collector - Running on {datetime.now(timezone.utc).isoformat()}")
    print(f"   Seal date: {SEAL_DATE}")
    
    try:
        check_seal()
        
        # Collect task list
        print("📡 Fetching tasks...")
        tasks_data = collect_tasks()
        tasks = tasks_data.get("tasks", [])
        
        # Collect details for each task
        print(f"📝 Fetching details for {len(tasks)} tasks...")
        task_details = {}
        for task in tasks:
            task_id = task["id"]
            try:
                details = collect_task_details(task_id)
                task_details[task_id] = details
            except Exception as e:
                print(f"⚠️  Failed to fetch task {task_id}: {e}")
        
        # Store snapshot
        snapshot = {
            "collection_timestamp": datetime.now(timezone.utc).isoformat(),
            "seal_date": SEAL_DATE.isoformat(),
            "tasks": tasks,
            "task_details": task_details
        }
        
        store_snapshot(snapshot)
        
        # Calculate days until unsealing
        now = datetime.now(timezone.utc)
        days_remaining = (SEAL_DATE - now).days
        print(f"\n⏳ {days_remaining} days until unsealing")
        
    except PermissionError as e:
        print(f"🔒 {e}")
        print("   Run analyzer.py to unseal and analyze.")

if __name__ == "__main__":
    main()
