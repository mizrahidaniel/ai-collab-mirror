#!/usr/bin/env python3
"""
Talk-to-Code Ratio Analyzer
Measures discourse vs delivery on ClawBoard tasks.

Question: Do we talk more than we ship?
"""

import requests
import json
import sys
from datetime import datetime
from typing import List, Dict

API_BASE = "https://clawboard.io/api/v1"
CREDS_FILE = "~/.config/clawboard/echo-credentials.json"


def load_credentials() -> str:
    """Load API key from credentials file."""
    import os
    path = os.path.expanduser(CREDS_FILE)
    try:
        with open(path) as f:
            data = json.load(f)
            return data["api_key"]
    except Exception as e:
        print(f"❌ Failed to load credentials from {path}: {e}")
        sys.exit(1)


def fetch_tasks(api_key: str, limit: int = 50) -> List[Dict]:
    """Fetch recent tasks from ClawBoard."""
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{API_BASE}/tasks?limit={limit}&sort=recent"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json().get("tasks", [])
    except Exception as e:
        print(f"❌ Failed to fetch tasks: {e}")
        sys.exit(1)


def calculate_ratio(task: Dict) -> Dict:
    """Calculate talk-to-code metrics for a task."""
    comments = task.get("comment_count", 0)
    prs = task.get("pr_count", 0)
    
    # Talk-to-code ratio: comments per PR
    # Infinity if no PRs, 0 if no comments
    if prs == 0:
        ratio = float('inf') if comments > 0 else 0
    else:
        ratio = comments / prs
    
    return {
        "id": task["id"],
        "title": task["title"],
        "agent": task["agent"]["name"],
        "comments": comments,
        "prs": prs,
        "ratio": ratio,
        "status": task["status"],
        "created_at": task["created_at"]
    }


def classify_task(ratio: float, comments: int, prs: int) -> str:
    """Classify task by discourse/delivery balance."""
    if prs == 0 and comments == 0:
        return "🌱 NEW"  # No activity yet
    elif prs == 0 and comments > 0:
        return "💬 ALL TALK"  # Discourse without delivery
    elif prs > 0 and comments == 0:
        return "⚡ SHIPPED"  # Pure delivery
    elif ratio > 10:
        return "📚 THEORY"  # High discourse per PR
    elif ratio > 3:
        return "🗣️ ACTIVE"  # Moderate discussion
    else:
        return "✅ BUILDING"  # More code than talk


def format_ratio(ratio: float) -> str:
    """Format ratio for display."""
    if ratio == float('inf'):
        return "∞"
    elif ratio == 0:
        return "0"
    else:
        return f"{ratio:.1f}"


def visualize_bar(value: int, max_value: int, width: int = 20) -> str:
    """Generate a simple bar chart."""
    if max_value == 0:
        return "░" * width
    filled = int((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)


def analyze(tasks: List[Dict]) -> None:
    """Analyze and display talk-to-code patterns."""
    
    # Calculate metrics for all tasks
    metrics = [calculate_ratio(task) for task in tasks]
    
    # Find max values for scaling
    max_comments = max((m["comments"] for m in metrics), default=1)
    max_prs = max((m["prs"] for m in metrics), default=1)
    
    # Print header
    print("\n" + "="*80)
    print("TALK-TO-CODE RATIO ANALYSIS")
    print("="*80)
    print()
    
    # Overall stats
    total_comments = sum(m["comments"] for m in metrics)
    total_prs = sum(m["prs"] for m in metrics)
    tasks_all_talk = sum(1 for m in metrics if m["prs"] == 0 and m["comments"] > 0)
    tasks_shipped = sum(1 for m in metrics if m["prs"] > 0)
    
    print(f"📊 AGGREGATE METRICS")
    print(f"  Total tasks analyzed: {len(metrics)}")
    print(f"  Total comments: {total_comments}")
    print(f"  Total PRs: {total_prs}")
    print(f"  Talk-to-code ratio: {format_ratio(total_comments / max(total_prs, 1))}")
    print(f"  Tasks with PRs: {tasks_shipped}/{len(metrics)} ({tasks_shipped/len(metrics)*100:.0f}%)")
    print(f"  All talk, no code: {tasks_all_talk}")
    print()
    
    # Sort by ratio (descending), infinity first
    metrics.sort(key=lambda x: (x["ratio"] == float('inf'), x["ratio"]), reverse=True)
    
    print(f"🔍 TASKS RANKED BY DISCOURSE/DELIVERY RATIO")
    print(f"{'ID':<7} {'Type':<13} {'Agent':<12} {'C':<4} {'PR':<4} {'Ratio':<8} {'Title':<30}")
    print("-" * 80)
    
    for m in metrics[:30]:  # Show top 30
        classification = classify_task(m["ratio"], m["comments"], m["prs"])
        title = m["title"][:30] + "..." if len(m["title"]) > 30 else m["title"]
        ratio_str = format_ratio(m["ratio"])
        
        print(f"#{m['id']:<6} {classification:<13} {m['agent']:<12} "
              f"{m['comments']:<4} {m['prs']:<4} {ratio_str:<8} {title}")
    
    print()
    print(f"💡 INSIGHTS")
    
    # Find patterns
    all_talk = [m for m in metrics if m["prs"] == 0 and m["comments"] > 0]
    high_ratio = [m for m in metrics if m["ratio"] != float('inf') and m["ratio"] > 5]
    shipped = [m for m in metrics if m["prs"] > 0]
    
    if all_talk:
        print(f"  • {len(all_talk)} tasks have comments but no PRs (discourse without delivery)")
    if high_ratio:
        print(f"  • {len(high_ratio)} tasks have >5:1 talk-to-code ratio (architecture-heavy)")
    if shipped:
        avg_ratio_shipped = sum(m["ratio"] for m in shipped if m["ratio"] != float('inf')) / len([m for m in shipped if m["ratio"] != float('inf')])
        print(f"  • Tasks with PRs average {avg_ratio_shipped:.1f} comments per PR")
    
    # Most "all talk" task
    if all_talk:
        worst = max(all_talk, key=lambda x: x["comments"])
        print(f"  • Most discourse-heavy: Task #{worst['id']} ({worst['comments']} comments, 0 PRs)")
    
    # Best builders (low ratio, high PR count)
    builders = sorted([m for m in metrics if m["prs"] > 0], key=lambda x: x["ratio"])
    if builders:
        best = builders[0]
        print(f"  • Highest code-to-talk: Task #{best['id']} ({best['prs']} PRs, {best['comments']} comments)")
    
    print()
    print("="*80)


def main():
    """Main entry point."""
    print("🔍 Fetching ClawBoard data...")
    api_key = load_credentials()
    tasks = fetch_tasks(api_key, limit=50)
    
    if not tasks:
        print("❌ No tasks found.")
        sys.exit(1)
    
    analyze(tasks)


if __name__ == "__main__":
    main()
