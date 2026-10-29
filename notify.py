import json, os, time, requests
from datetime import datetime, timezone, timedelta

LOUNGE = "Where_Winds_Meet"
BOARDS = {
    "11": ("📢 공지사항", 0x3B82F6),
    "12": ("📋 업데이트 노트", 0x10B981),
    "16": ("📺 인게임콘텐츠", 0x8B5CF6),
    "17": ("🛍️ 외관·상점 소식", 0xF59E0B),
}
WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
STATE = "state.json"
KST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://game.naver.com/",
    "Origin": "https://game.naver.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}
SKIP_LINES = ("안녕하세요, 협객 여러분", "연운 GM 연지입니다")


def fetch(board_id):
    url = f"https://comm-api.game.naver.com/nng_main/v1/community/lounge/{LOUNGE}/feed"
    r = requests.get(url, headers=HEADERS, timeout=20, params={
        "boardId": board_id, "buffFilteringYN": "N",
        "limit": 25, "offset": 0, "order": "NEW"})
    r.raise_for_status()
    feeds = r.json()["content"]["feeds"]
    return [f for f in feeds if not f["feed"].get("hideByCleanBot")]


def body_text(contents, limit=300):
    """contents(JSON 문자열)에서 본문 텍스트만 뽑는다."""
    try:
        comps = json.loads(contents)["document"]["components"]
    except Exception:
        return ""
    lines = []
    for c in comps:
        if c.get("@ctype") != "text":
            continue
        for p in c.get("value", []):
            line = "".join(n.get("value", "") for n in p.get("nodes", [])).strip()
            if line and not line.startswith(SKIP_LINES):
                lines.append(line)
    return "\n".join(lines)[:limit]


def send(board_id, item):
    f = item["feed"]
    name, color = BOARDS[board_id]
    created = datetime.strptime(f["createdDate"], "%Y%m%d%H%M%S").replace(tzinfo=KST)
    embed = {
        "title": f["title"][:256],
        "url": item["feedLink"]["pc"],
        "description": body_text(f.get("contents", "")),
        "color": color,
        "author": {"name": f"연운 라운지 · {name}"},
        "footer": {"text": item.get("user", {}).get("nickname", "")},
        "timestamp": created.astimezone(timezone.utc).isoformat(),
    }
    if f.get("repImageUrl"):
        embed["image"] = {"url": f["repImageUrl"]}
    r = requests.post(WEBHOOK, json={"embeds": [embed]}, timeout=20)
    r.raise_for_status()


def main():
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    failed = False
    for board_id in BOARDS:
        try:
            items = fetch(board_id)
        except Exception as e:
            print(f"[{board_id}] 조회 실패: {e!r}")
            failed = True
            continue
        seen = set(state.get(board_id, []))
        silent = board_id not in state          # 처음 보는 게시판은 알림 없이 기록만
        new = sorted((i for i in items if str(i["feed"]["feedId"]) not in seen),
                     key=lambda i: i["feed"]["feedId"])
        for item in new:
            fid = str(item["feed"]["feedId"])
            if not silent:
                try:
                    send(board_id, item)
                    time.sleep(1)
                except Exception as e:
                    print(f"[{board_id}] 전송 실패 {fid}: {e!r}")
                    failed = True
                    break                         # 실패한 글은 기록하지 않아 다음에 재시도
            seen.add(fid)
        state[board_id] = sorted(seen, key=int)[-200:]
    json.dump(state, open(STATE, "w"))
    if failed:
        raise SystemExit(1)


main()
