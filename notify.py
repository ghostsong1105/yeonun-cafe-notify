import json, os, requests
from datetime import datetime, timezone

CAFE_ID = "31511138"
BOARDS = {"1": "공지사항", "3": "이벤트"}
COLORS = {"1": 0x3B82F6, "3": 0xF59E0B}
WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
STATE = "state.json"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://cafe.naver.com/"}


def fetch(menu_id):
    url = (f"https://apis.naver.com/cafe-web/cafe-boardlist-api/v1/cafes/"
           f"{CAFE_ID}/menus/{menu_id}/articles")
    r = requests.get(url, headers=HEADERS, timeout=20,
                     params={"page": 1, "pageSize": 15, "sortBy": "TIME", "viewType": "L"})
    r.raise_for_status()
    return [x["item"] for x in r.json()["result"]["articleList"] if x.get("type") == "ARTICLE"]


def send(menu_id, name, a):
    link = f"https://cafe.naver.com/f-e/cafes/{CAFE_ID}/articles/{a['articleId']}"
    summary = (a.get("summary") or "").strip()
    embed = {
        "title": a["subject"][:256],
        "url": link,
        "description": summary[:300],
        "color": COLORS.get(menu_id, 0x5865F2),
        "author": {"name": f"연운 카페 · {name}"},
        "footer": {"text": a.get("writerInfo", {}).get("nickName", "")},
        "timestamp": datetime.fromtimestamp(
            a["writeDateTimestamp"] / 1000, tz=timezone.utc).isoformat(),
    }
    if a.get("representImage"):
        embed["image"] = {"url": a["representImage"]}
    r = requests.post(WEBHOOK, json={"embeds": [embed]}, timeout=20)
    r.raise_for_status()


def main():
    state = json.load(open(STATE)) if os.path.exists(STATE) else None
    first_run = state is None
    state = state or {}
    for menu_id, name in BOARDS.items():
        seen = set(state.get(menu_id, []))
        arts = fetch(menu_id)
        new = [a for a in arts if str(a["articleId"]) not in seen]
        if not first_run and menu_id in state:
            for a in sorted(new, key=lambda x: x["articleId"]):  # 오래된 글부터
                send(menu_id, name, a)
        state[menu_id] = sorted(seen | {str(a["articleId"]) for a in arts},
                                key=int)[-200:]
    json.dump(state, open(STATE, "w"))


main()
