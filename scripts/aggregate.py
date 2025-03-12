#!/usr/bin/env python3
import json
import subprocess
import datetime
import os

AGG_FILE = 'aggregated_capacities.json'
SOURCE_FILE = 'capacities.json'
RETENTION_DAYS = 30

def load_aggregated_data():
    if os.path.exists(AGG_FILE):
        with open(AGG_FILE, 'r') as f:
            return json.load(f)
    else:
        # Start with an empty structure and no last processed commit
        return {"metadata": {"lastCommit": None}, "data": {}}

def save_aggregated_data(data):
    with open(AGG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_new_commits(last_commit):
    # If last_commit is provided, get commits after that one; otherwise, all commits for SOURCE_FILE.
    if last_commit:
        cmd = ['git', 'log', '--reverse', '--format=%H', f'{last_commit}..HEAD', '--', SOURCE_FILE]
    else:
        cmd = ['git', 'log', '--reverse', '--format=%H', '--', SOURCE_FILE]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    commits = result.stdout.strip().splitlines()
    return commits

def get_file_content_at_commit(commit):
    cmd = ['git', 'show', f'{commit}:{SOURCE_FILE}']
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout

def process_commit(commit, agg_data):
    content = get_file_content_at_commit(commit)
    if not content.strip():
        print(f"Empty content for commit {commit}, skipping.")
        return

    try:
        entries = json.loads(content)
    except Exception as e:
        print(f"Error processing commit {commit}: {e}")
        return

    # Define the target timezone (UTC+8)
    tz_utc8 = datetime.timezone(datetime.timedelta(hours=8))
    
    for entry in entries:
        timestamp = entry.get("timestamp")
        if not timestamp:
            continue

        # Convert from milliseconds to seconds and then create a datetime in UTC+8.
        dt = datetime.datetime.fromtimestamp(timestamp / 1000, tz=tz_utc8)
        date_str = dt.strftime('%Y-%m-%d')
        name = entry.get("name", "unknown")

        if name not in agg_data["data"]:
            agg_data["data"][name] = {}

        if date_str not in agg_data["data"][name]:
            agg_data["data"][name][date_str] = []

        agg_data["data"][name][date_str].append(entry)

    # Update the last processed commit to the current commit
    agg_data["metadata"]["lastCommit"] = commit

def apply_retention_policy(agg_data):
    tz_utc8 = datetime.timezone(datetime.timedelta(hours=8))
    # Calculate the cutoff date in UTC+8
    cutoff = datetime.datetime.now(tz=tz_utc8) - datetime.timedelta(days=RETENTION_DAYS)
    cutoff_str = cutoff.strftime('%Y-%m-%d')

    for name, dates in agg_data["data"].items():
        for date in list(dates.keys()):
            # If the date (as string) is older than the cutoff, summarize the data.
            if date < cutoff_str:
                entries = dates[date]
                numeric_caps = [entry["capacity"] for entry in entries if isinstance(entry.get("capacity"), (int, float))]
                avg = sum(numeric_caps)/len(numeric_caps) if numeric_caps else None
                agg_data["data"][name][date] = {
                    "average_capacity": avg,
                    "entry_count": len(entries)
                }

def main():
    agg_data = load_aggregated_data()
    last_commit = agg_data["metadata"].get("lastCommit")
    new_commits = get_new_commits(last_commit)
    
    if new_commits:
        print("Processing commits:", new_commits)
    else:
        print("No new commits to process.")
    
    for commit in new_commits:
        process_commit(commit, agg_data)
    
    apply_retention_policy(agg_data)
    save_aggregated_data(agg_data)
    print("Aggregation complete.")

if __name__ == '__main__':
    main()

