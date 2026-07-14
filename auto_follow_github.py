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

async def main():
    async with httpx.AsyncClient(http2=True) as client:
        # 1. Fetch initial score
        pts, rank = await get_current_score(client)
        print(f"Initial score: {pts} points (Rank {rank})")

        # 2. Fetch page 1 to check total teams
        page1 = await fetch_page(client, 1)
        if not page1:
            print("Failed to contact the server. Exiting.")
            return

        total_teams = page1.get("total", 0)
        page_size = page1.get("page_size", 20)
        total_pages = (total_teams + page_size - 1) // page_size
        print(f"Total teams: {total_teams} across {total_pages} pages.")

        # Gather teams from page 1
        all_teams = page1.get("items", [])

        # Fetch remaining pages concurrently
        if total_pages > 1:
            tasks = [fetch_page(client, p) for p in range(2, total_pages + 1)]
            results = await asyncio.gather(*tasks)
            for res in results:
                if res:
                    all_teams.extend(res.get("items", []))

        # 3. Filter for teams not followed yet
        to_follow = [t.get("slug") for t in all_teams if not t.get("is_following")]
        
        if not to_follow:
            print("You are already following all existing teams. No new actions.")
            return

        print(f"Found {len(to_follow)} new teams to follow. Subscribing...")

        # 4. Follow new teams concurrently
        follow_tasks = [follow_team(client, slug) for slug in to_follow]
        results = await asyncio.gather(*follow_tasks)
        
        successful_follows = sum(1 for r in results if r)
        print(f"Done! Successfully followed {successful_follows} new teams.")

        # 5. Fetch updated score
        new_pts, new_rank = await get_current_score(client)
        print(f"Updated score: {new_pts} points (Rank {new_rank})")

if __name__ == "__main__":
    asyncio.run(main())
