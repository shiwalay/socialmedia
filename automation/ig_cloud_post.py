#!/usr/bin/env python3
"""Instagram cloud poster for @shiwalay — runs in GitHub Actions at the 4 IST slots.

Reads posting-calendar.csv, finds the slot closest to 'now' (IST), publishes that
carousel to Instagram via the Graph API, and records it in posted-ig.log
(committed back by the workflow) so a re-run can never double-post.

Env needed: FB_PAGE_TOKEN (repo secret), IG_USER_ID.
Images are fetched by Instagram from IMAGE_BASE — no files needed locally.
"""
import csv, os, sys, time, datetime as dt
from pathlib import Path
import requests

GRAPH = "https://graph.facebook.com/v21.0"
IMAGE_BASE = "https://www.shiwalay.com/carousels"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
SLOTS = ["08:00", "12:00", "16:00", "20:00"]
SLOT_TOLERANCE_MIN = 55        # actions cron can fire late; accept up to this
HERE = Path(__file__).resolve().parent
CAL = HERE / "posting-calendar.csv"
LOG = HERE / "posted-ig.log"


def current_slot(now):
    best, gap = None, 10**9
    for s in SLOTS:
        h, m = map(int, s.split(":"))
        slot_min = h * 60 + m
        now_min = now.hour * 60 + now.minute
        d = abs(now_min - slot_min)
        if d < gap:
            best, gap = s, d
    return (best, gap) if gap <= SLOT_TOLERANCE_MIN else (None, gap)


def main():
    token = os.environ["FB_PAGE_TOKEN"]
    ig_id = os.environ["IG_USER_ID"]
    now = dt.datetime.now(IST)
    slot, gap = current_slot(now)
    if not slot:
        print(f"no slot within tolerance (nearest is {gap} min away) — exiting")
        return
    key = f"{now:%Y-%m-%d}_{slot}"
    done = LOG.read_text().split() if LOG.exists() else []
    if key in done:
        print(key, "already posted — exiting")
        return

    rows = list(csv.DictReader(open(CAL)))
    row = next((r for r in rows if r["date"] == f"{now:%Y-%m-%d}"
                and r["time_IST"] == slot), None)
    if not row:
        print("no calendar entry for", key, "— exiting")
        return

    rel = row["images_folder"].split("blacklight-all/", 1)[-1]
    print(f"posting {key} | {row['category']} | {row['title']}")

    children = []
    for i in range(1, 5):
        url = f"{IMAGE_BASE}/{rel}/slide-{i}.jpg"
        r = requests.post(f"{GRAPH}/{ig_id}/media", timeout=180,
                          data={"image_url": url, "is_carousel_item": "true",
                                "access_token": token})
        r.raise_for_status()
        children.append(r.json()["id"])

    r = requests.post(f"{GRAPH}/{ig_id}/media", timeout=180,
                      data={"media_type": "CAROUSEL",
                            "caption": row["caption_fb_ig_li"],
                            "children": ",".join(children),
                            "access_token": token})
    r.raise_for_status()
    container = r.json()["id"]

    for _ in range(30):
        s = requests.get(f"{GRAPH}/{container}", timeout=180,
                         params={"fields": "status_code",
                                 "access_token": token}).json()
        if s.get("status_code") == "FINISHED":
            break
        time.sleep(3)

    r = requests.post(f"{GRAPH}/{ig_id}/media_publish", timeout=180,
                      data={"creation_id": container, "access_token": token})
    r.raise_for_status()
    print("IG ok:", r.json().get("id"))

    with open(LOG, "a") as f:
        f.write(key + "\n")


if __name__ == "__main__":
    main()
