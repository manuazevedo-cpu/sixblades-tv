import json, sys, time, urllib.request, datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

BASE = "https://app.gymdesk.com/widgets/schedule/getevents"
GYM_ID, SCHEDULE_ID = "20515", "30744"
today = datetime.datetime.now(ZoneInfo("America/Denver")).date().isoformat()
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


def get(direction):
    url = f"{BASE}?date={today}&id={GYM_ID}&schedule_id={SCHEDULE_ID}&direction={direction}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (SixBladesTV)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if attempt == 2:
                raise
            print(f"Download failed ({e}), retrying in 20 s")
            time.sleep(20)


class EventParser(HTMLParser):
    """Collects each schedule event: its data-event-info, its CSS classes
    (color and canceled state live there) and the instructor names."""

    def __init__(self):
        super().__init__()
        self.events, self.cur, self.depth = [], None, 0
        self.in_instr, self.in_name = 0, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if self.cur is None:
            if a.get("data-event-info") is not None:
                self.cur = {"info": json.loads(a["data-event-info"]),
                            "classes": (a.get("class") or "").split(), "names": []}
                self.depth = 0 if tag in VOID else 1
            return
        if tag in VOID:
            return
        self.depth += 1
        cls = (a.get("class") or "").split()
        if self.in_instr:
            self.in_instr += 1
        elif "instructors" in cls or "instructors-list" in cls:
            self.in_instr = 1
        self.in_name = bool(self.in_instr) and "name" in cls

    def handle_endtag(self, tag):
        if self.cur is None or tag in VOID:
            return
        self.in_name = False
        if self.in_instr:
            self.in_instr -= 1
        self.depth -= 1
        if self.depth <= 0:
            self.events.append(self.cur)
            self.cur, self.in_instr = None, 0

    def handle_data(self, data):
        name = data.strip()
        if self.cur is not None and self.in_name and name and name not in self.cur["names"]:
            self.cur["names"].append(name)


events, seen = [], set()
for direction in ("current", "next"):
    data = get(direction)
    if not data.get("success"):
        sys.exit("GymDesk returned success=false")
    p = EventParser()
    p.feed(data.get("events", ""))
    for ev in p.events:
        info, classes = ev["info"], ev["classes"]
        if "canceled" in classes or info.get("cancel") or info.get("canceled") \
                or not info.get("website_visible", 1):
            continue
        date = info.get("date") or info.get("scheduled")
        if not date or not info.get("start"):
            continue
        key = (info.get("id"), date, info["start"])
        if key in seen:
            continue
        seen.add(key)
        color = info.get("color") or next(
            (c[len("border-color-"):] for c in classes if c.startswith("border-color-")), "black")
        names = ev["names"]
        if not names and isinstance(info.get("instructors"), dict):
            names = [i.get("name", "") for i in info["instructors"].values()]
        events.append({
            "date": date,
            "start": info["start"][:5],
            "duration": int(info["duration"]),
            "title": info["title"],
            "color": color,
            "instructors": names,
        })

if not events:
    sys.exit("No events found - keeping previous schedule.json")

events.sort(key=lambda e: (e["date"], e["start"]))
with open("schedule.new.json", "w", encoding="utf-8") as f:
    json.dump({"events": events}, f, ensure_ascii=False, indent=1)
print(f"{len(events)} events")
