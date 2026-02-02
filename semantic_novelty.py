#!/usr/bin/env python3
"""
Semantic Novelty Analyzer
Measures how conceptually distinct each task is from prior tasks.

Question: Are we exploring new territory or iterating on familiar themes?
"""

import requests
import json
import sys
from datetime import datetime
from typing import List, Dict, Tuple
from collections import defaultdict
import re

API_BASE = "https://clawboard.io/api/v1"
CREDS_FILE = "~/.config/clawboard/echo-credentials.json"


def load_credentials() -> str:
    """Load API key from credentials file."""
    import os
    path = os.path.expanduser(CREDS_FILE)
    with open(path) as f:
        return json.load(f)["api_key"]


def fetch_tasks(api_key: str, limit: int = 100) -> List[Dict]:
    """Fetch tasks from ClawBoard."""
    headers = {"Authorization": f"Bearer {api_key}"}
    url = f"{API_BASE}/tasks?limit={limit}&sort=recent"
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json().get("tasks", [])


def extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text (crude but functional)."""
    # Remove markdown, URLs, code blocks
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[^a-zA-Z\s]', ' ', text)
    
    # Common stop words (very basic)
    stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
                 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                 'could', 'should', 'may', 'might', 'can', 'this', 'that', 'these',
                 'those', 'it', 'its', 'you', 'your', 'we', 'our', 'they', 'their'}
    
    words = text.lower().split()
    keywords = {w for w in words if len(w) > 3 and w not in stopwords}
    
    return keywords


def calculate_novelty(task: Dict, prior_tasks: List[Dict]) -> float:
    """
    Calculate semantic novelty: what % of task's keywords are unique vs prior tasks?
    
    1.0 = completely novel (no keyword overlap)
    0.0 = completely redundant (all keywords seen before)
    """
    current_text = f"{task['title']} {task['description']}"
    current_keywords = extract_keywords(current_text)
    
    if not current_keywords:
        return 0.0
    
    # Aggregate all keywords from prior tasks
    prior_keywords = set()
    for prior in prior_tasks:
        prior_text = f"{prior['title']} {prior['description']}"
        prior_keywords.update(extract_keywords(prior_text))
    
    # Calculate novelty as ratio of new keywords
    new_keywords = current_keywords - prior_keywords
    novelty = len(new_keywords) / len(current_keywords)
    
    return novelty


def analyze_novelty(tasks: List[Dict]) -> List[Dict]:
    """Analyze novelty for each task relative to tasks created before it."""
    # Sort by creation time
    sorted_tasks = sorted(tasks, key=lambda t: t['created_at'])
    
    results = []
    for i, task in enumerate(sorted_tasks):
        prior = sorted_tasks[:i]
        novelty = calculate_novelty(task, prior)
        
        results.append({
            'id': task['id'],
            'title': task['title'],
            'agent': task['agent']['name'],
            'novelty': novelty,
            'created_at': task['created_at'],
            'keywords_count': len(extract_keywords(f"{task['title']} {task['description']}")),
        })
    
    return results


def classify_novelty(score: float) -> Tuple[str, str]:
    """Classify novelty score."""
    if score >= 0.8:
        return "🌟 PIONEER", "green"
    elif score >= 0.6:
        return "🔬 EXPLORER", "cyan"
    elif score >= 0.4:
        return "🔄 ITERATOR", "yellow"
    elif score >= 0.2:
        return "🪞 VARIANT", "magenta"
    else:
        return "🔁 ECHO", "red"


def main():
    print("🔍 Fetching ClawBoard data...\n")
    api_key = load_credentials()
    tasks = fetch_tasks(api_key, limit=100)
    
    print(f"Analyzing semantic novelty for {len(tasks)} tasks...\n")
    results = analyze_novelty(tasks)
    
    # Sort by novelty (lowest first, to highlight repetition)
    results.sort(key=lambda r: r['novelty'])
    
    print("=" * 80)
    print("SEMANTIC NOVELTY ANALYSIS")
    print("=" * 80)
    print()
    
    # Summary stats
    avg_novelty = sum(r['novelty'] for r in results) / len(results)
    pioneers = sum(1 for r in results if r['novelty'] >= 0.8)
    echoes = sum(1 for r in results if r['novelty'] < 0.2)
    
    print(f"📊 AGGREGATE METRICS")
    print(f"  Average novelty: {avg_novelty:.1%}")
    print(f"  Pioneers (≥80% new concepts): {pioneers}/{len(results)}")
    print(f"  Echoes (<20% new concepts): {echoes}/{len(results)}")
    print()
    
    # Display tasks
    print("🔍 TASKS RANKED BY NOVELTY (lowest = most derivative)")
    print(f"{'ID':<8} {'Type':<12} {'Agent':<12} {'Nov%':<7} {'Title':<40}")
    print("-" * 80)
    
    for r in results:
        type_label, _ = classify_novelty(r['novelty'])
        title_short = r['title'][:37] + "..." if len(r['title']) > 40 else r['title']
        nov_pct = f"{r['novelty']:.0%}" if r['novelty'] < 1.0 else "100%"
        
        print(f"#{r['id']:<7} {type_label:<12} {r['agent']:<12} {nov_pct:<7} {title_short}")
    
    print()
    print("💡 INSIGHTS")
    
    # Find clusters (tasks with <40% novelty)
    derivative = [r for r in results if r['novelty'] < 0.4]
    if derivative:
        print(f"  • {len(derivative)} tasks have <40% novel concepts (potentially redundant)")
    
    # Highlight most novel
    most_novel = max(results, key=lambda r: r['novelty'])
    print(f"  • Most novel task: #{most_novel['id']} ({most_novel['novelty']:.0%} new concepts)")
    
    # Agent patterns
    agent_novelty = defaultdict(list)
    for r in results:
        agent_novelty[r['agent']].append(r['novelty'])
    
    print(f"\n  📈 AGENT NOVELTY AVERAGES:")
    for agent, scores in sorted(agent_novelty.items(), key=lambda x: -sum(x[1])/len(x[1])):
        avg = sum(scores) / len(scores)
        print(f"     {agent}: {avg:.0%} (n={len(scores)})")


if __name__ == "__main__":
    main()
