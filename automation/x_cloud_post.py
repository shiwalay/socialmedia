#!/usr/bin/env python3
"""X (Twitter) cloud poster for @shiwalay — runs in GitHub Actions at the 4 IST slots.

Finds the slot closest to now (IST), uploads the 4 slides from the repo checkout,
posts with the short caption, and records it in posted-x.log.
Skips silently if X secrets are not configured yet.

Env needed: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET.
"""
import csv, os, sys, datetime as dt
from pathlib import Path

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
SLOTS = ["08:00", "12:00", "16:00", "20:00"]
SLOT_TOLERANCE_MIN = 55
HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CAL = HERE / "posting-calendar.csv"
LOG = HERE / "posted-x.log"


def current_slot(now):
    best, gap = None, 10**9
    for s in SLOTS:
        h, m = map(int, s.split(":"))
        d = abs((now.hour * 60 + now.minute) - (h * 60 + m))
        if d < gap:
            best, gap = s, d
    return (best, gap) if gap <= SLOT_TOLERANCE_MIN else (None, gap)


def main():
    keys = [os.environ.get(k, "") for k in
            ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET")]
    if not all(keys):
        print("X keys not configured — skipping")
        return
    import tweepy

    now = dt.datetime.now(IST)
    force = os.environ.get("FORCE_SLOT")
    if force:
        slot = force
    else:
        slot, gap = current_slot(now)
        if not slot:
            print(f"no slot within tolerance (nearest {gap} min away) — exiting")
            return
    rows = list(csv.DictReader(open(CAL)))
    if force:
        key = "FORCE_TEST"
        row = rows[0]
        print("FORCE test mode: posting first calendar row (not logged)")
    else:
        key = f"{now:%Y-%m-%d}_{slot}"
        done = LOG.read_text().split() if LOG.exists() else []
        if key in done:
            print(key, "already posted — exiting")
            return
        row = next((r for r in rows if r["date"] == f"{now:%Y-%m-%d}"
                    and r["time_IST"] == slot), None)
        if not row:
            print("no calendar entry for", key, "— exiting")
            return

    rel = row["images_folder"].split("blacklight-all/", 1)[-1]
    files = [REPO / rel / f"slide-{i}.jpg" for i in range(1, 5)]
    if any(not f.exists() for f in files):
        print("images missing in repo for", rel, "— exiting")
        return

    print(f"posting {key} | {row['category']} | {row['title']}")
    auth = tweepy.OAuth1UserHandler(keys[0], keys[1], keys[2], keys[3])
    api_v1 = tweepy.API(auth)
    media_ids = [api_v1.media_upload(str(f)).media_id_string for f in files]
    client = tweepy.Client(consumer_key=keys[0], consumer_secret=keys[1],
                           access_token=keys[2], access_token_secret=keys[3])
    resp = client.create_tweet(text=row["caption_x"], media_ids=media_ids)
    print("X ok:", resp.data.get("id"))

    if not force:
        with open(LOG, "a") as f:
            f.write(key + "\n")


if __name__ == "__main__":
    main()
