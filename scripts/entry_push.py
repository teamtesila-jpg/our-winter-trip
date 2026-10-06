#!/usr/bin/env python3
"""여행 중 휴대폰 알림 예약 발송 (ntfy.sh, 2026.10.6 박사님 요청: 입장 1시간 전 알림).

GitHub Actions(.github/workflows/entry-push.yml)가 2시간마다 이 스크립트를 돌린다.
push/entries.json 에서 앞으로 70시간 안에 보낼 알림을 ntfy.sh 에 예약 발송(At, 최대 3일)으로 맡기고,
맡긴 것은 push/sent.json 에 적어 두 번 보내지 않는다. 그래서 노트북이 꺼져 있어도 알림이 간다.
주제(NTFY_TOPIC)는 저장소 비밀값으로만 받는다. 표 파일, 예약번호, 이름은 넣지 않는다.

사용 : python scripts/entry_push.py          예약할 것 예약
       python scripts/entry_push.py --test   2분 뒤 시험 알림 한 번
       python scripts/entry_push.py --dry    무엇을 예약할지 출력만(주제 불필요)
"""
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENTRIES = ROOT / "push" / "entries.json"
SENT = ROOT / "push" / "sent.json"
CET = dt.timezone(dt.timedelta(hours=1))   # 12.23~1.12 파리, 스위스, 이탈리아 모두 UTC+1(겨울 시간)
HORIZON = dt.timedelta(hours=70)            # ntfy.sh 예약 발송 상한 3일 안쪽
LATE = dt.timedelta(minutes=30)             # 이보다 늦게 알게 되면 보내지 않음
CLICK = "https://teamtesila-jpg.github.io/our-winter-trip/"
TITLE = "유럽여행"


def post(topic, msg, at=None, tags="ticket"):
    url = "https://ntfy.sh/%s?title=%s" % (topic, urllib.parse.quote(TITLE))
    headers = {"Tags": tags, "Click": CLICK, "Priority": "high"}
    if at is not None:
        headers["At"] = str(int(at.timestamp()))
    req = urllib.request.Request(url, data=msg.encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8")).get("id", "")


def main():
    dry = "--dry" in sys.argv
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic and not dry:
        # 비밀값을 아직 안 넣었으면 실패로 남기지 않고 조용히 넘어감(실패 메일 방지)
        print("SKIP no NTFY_TOPIC secret yet")
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    if "--now" in sys.argv:  # 시험용: 가짜 현재 시각(로컬 CET), --dry 와 함께
        now = dt.datetime.fromisoformat(sys.argv[sys.argv.index("--now") + 1]).replace(tzinfo=CET)
    if "--test" in sys.argv:
        at = now + dt.timedelta(minutes=2)
        mid = post(topic, "[여행] 시험 알림입니다. 여행 중에는 입장 1시간 전쯤 이런 알림이 옵니다.", at)
        print("TEST queued for", at.isoformat(timespec="minutes"), mid)
        return 0
    entries = json.loads(ENTRIES.read_text(encoding="utf-8"))
    sent = json.loads(SENT.read_text(encoding="utf-8")) if SENT.exists() else {}
    changed = False
    for e in entries:
        if e["id"] in sent:
            continue
        at = dt.datetime.fromisoformat(e["at"]).replace(tzinfo=CET)
        if at > now + HORIZON:
            continue
        if at < now - LATE:
            sent[e["id"]] = {"at": e["at"], "skipped": "late"}
            changed = True
            continue
        when = at if at > now + dt.timedelta(seconds=30) else None
        if dry:
            print("WOULD QUEUE", e["id"], e["at"])
            continue
        mid = post(topic, e["msg"], when, e.get("tags", "ticket"))
        sent[e["id"]] = {"at": e["at"], "ntfy": mid, "queued": now.isoformat(timespec="minutes")}
        changed = True
        print("QUEUED", e["id"], e["at"], mid)
    if changed and not dry:
        SENT.write_text(json.dumps(sent, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("done", len(entries), "entries,", len(sent), "handled")
    return 0


if __name__ == "__main__":
    sys.exit(main())
