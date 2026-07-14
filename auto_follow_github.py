import asyncio
import httpx
import os
import sys

# Ensure stdout uses UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Read Token from GitHub Secret (Environment Variable)
TOKEN = os.environ.get("AI_HACKS_TOKEN")

if not TOKEN:
    print("[ERROR] AI_HACKS_TOKEN environment variable is not set. Exiting.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

TEAMS_URL = "https://hub-api.aiforvietnam.org/fan/teams"
LEADERBOARD_URL = "https://hub-api.aiforvietnam.org/fan/leaderboard"

async def fetch_page(client, page):
    try:
        res = await client.get(f"{TEAMS_URL}?page={page}", headers=HEADERS)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Error fetching page {page}: {e}")
    return None

async def follow_team(client, slug):
    url = f"{TEAMS_URL}/{slug}/follow"
    try:
        res = await client.post(url, headers=HEADERS)
        if res.status_code == 200:
            print(f"[SUCCESS] Followed team: {slug}")
            return True
        else:
            print(f"[FAILED] Team {slug}: Status {res.status_code}, Body: {res.text}")
    except Exception as e:
        print(f"[ERROR] Failed to follow {slug}: {e}")
    return False

async def get_current_score(client):
    try:
        res = await client.get(LEADERBOARD_URL, headers=HEADERS)
        if res.status_code == 200:
            me = res.json().get("me", {})
            return me.get("fan_points", 0), me.get("rank", 0)
    except Exception as e:
        print(f"Error fetching score: {e}")
    return None, None

async def check_once(client, last_total):
    # 1. Fetch page 1 to check total teams
    page1 = await fetch_page(client, 1)
    if not page1:
        print("Failed to contact the server. Skipping this iteration.")
        return last_total

    current_total = page1.get("total", 0)
    
    # If the number of teams hasn't changed, skip scanning remaining pages
    if current_total <= last_total and last_total > 0:
        return current_total

    print(f"\n[SCAN] Total teams changed or first run. Total teams: {current_total}")
    page_size = page1.get("page_size", 20)
    total_pages = (current_total + page_size - 1) // page_size

    # Gather teams from page 1
    all_teams = page1.get("items", [])

    # Fetch remaining pages concurrently
    if total_pages > 1:
        tasks = [fetch_page(client, p) for p in range(2, total_pages + 1)]
        results = await asyncio.gather(*tasks)
        for res in results:
            if res:
                all_teams.extend(res.get("items", []))

    # 2. Filter for teams not followed yet
    to_follow = [t.get("slug") for t in all_teams if not t.get("is_following")]
    
    if not to_follow:
        print("Already following all existing teams. No action needed.")
        return current_total

    print(f"Found {len(to_follow)} new teams to follow. Subscribing...")

    # 3. Follow new teams concurrently
    follow_tasks = [follow_team(client, slug) for slug in to_follow]
    results = await asyncio.gather(*follow_tasks)
    
    successful_follows = sum(1 for r in results if r)
    print(f"Successfully followed {successful_follows} new teams.")
    
    # Print updated score
    new_pts, new_rank = await get_current_score(client)
    print(f"Updated score: {new_pts} points (Rank {new_rank})")
    
    return current_total

async def main():
    print("Starting 1-minute resolution check loop (runs for 5 minutes total)...")
    # Initialize standard HTTP/1.1 client (removes h2 package requirement)
    async with httpx.AsyncClient() as client:
        last_total = 0
        for i in range(5):
            print(f"\n--- Checking Loop {i+1}/5 ---")
            last_total = await check_once(client, last_total)
            if i < 4:
                print("Sleeping for 60 seconds...")
                await asyncio.sleep(60)
        print("\nFinished 5-minute session execution. Exiting.")

if __name__ == "__main__":
    asyncio.run(main())
