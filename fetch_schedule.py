import json, re, html, sys, urllib.request, datetime
from zoneinfo import ZoneInfo

BASE = "https://app.gymdesk.com/widgets/schedule/getevents"
GYM_ID, SCHEDULE_ID = "20515", "30744"
today = datetime.datetime.now(ZoneInfo("America/Denver")).date().isoformat()

def get(direction):
    url = f"{BASE}?date={today}&id={GYM_ID}&schedule_id={SCHEDULE_ID}&direction={direction}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SixBladesTV)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

events, seen = [], set()
for direction in ("current", "next"):
    data = get(direction)
    if not data.get("success"):
        sys.exit("GymDesk returned success=false")
    for raw in re.findall(r'data-event-info="([^"]*)"', data.get("events", "")):
        info = json.loads(html.unescape(raw))
        if info.get("cancel") or info.get("canceled") or not info.get("website_visible", 1):
            continue
        key = (info["id"], info["scheduled"])
        if key in seen:
            continue
        seen.add(key)
        names = [i.get("name", "") for i in (info.get("instructors") or {}).values()] \
            if isinstance(info.get("instructors"), dict) else []
        events.append({
            "date": info["scheduled"],
            "start": info["start"][:5],
            "duration": int(info["duration"]),
            "title": info["title"],
            "color": info.get("color") or "black",
            "instructors": names,
        })

if not events:
    sys.exit("No events found - keeping previous schedule.json")

events.sort(key=lambda e: (e["date"], e["start"]))
out = {"events": events}
with open("schedule.new.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"{len(events)} events")
