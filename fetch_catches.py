# -*- coding: utf-8 -*-
"""
宿マスタ(boats.json)をもとに、各宿の釣果ページから取得して catches.json に追記する。

  python fetch_catches.py                 # 全宿
  python fetch_catches.py --only 忠彦丸    # 宿名で絞る
  python fetch_catches.py --days 30       # 過去分もさかのぼる
"""
import argparse
import json
import os
import re
import time
import urllib.request
from datetime import date, timedelta

from parsers.core import parse_report

UA = "uodoko-collector/0.1 (personal fishing log aggregator)"
SLEEP = 2.0
RAW_DIR = "raw"

PLATFORMS = [
    ("gyo",     re.compile(r"gyo\.ne\.jp")),
    ("gyosan",  re.compile(r"gyosan|/search/(Archive|RealtimeDetail)/")),
    ("ggnet",   re.compile(r"ggnet\.co\.jp")),
    ("chowari", re.compile(r"chowari\.jp")),
    ("fv",      re.compile(r"fishing-v\.jp")),
]


def detect_platform(html: str, url: str) -> str:
    blob = (url or "") + " " + (html or "")[:200000]
    for name, pat in PLATFORMS:
        if pat.search(blob):
            return name
    return "own"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    for enc in ("utf-8", "cp932", "euc-jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def html_to_text(html: str) -> str:
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    h = re.sub(r"(?i)<br\s*/?>", "\n", h)
    h = re.sub(r"(?i)</(p|div|li|tr|h[1-6])>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = (h.replace("&nbsp;", " ").replace("&amp;", "&")
           .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    h = re.sub(r"[ \t\u3000]+", " ", h)
    h = re.sub(r"\n{2,}", "\n", h)
    return h.strip()


def catch_urls(boat: dict, days: int):
    pf, site = boat.get("platform"), boat.get("site") or ""
    urls = []
      if boat.get("catch_url"):
        return [boat["catch_url"]]

    if pf == "gyo":
        m = re.search(r"CID-([A-Za-z0-9_]+)", site)
        if m:
            cid = m.group(1)
            urls.append(f"https://www.gyo.ne.jp/rep_tsuri_view|CID-{cid}.htm")
            base = date.today()
            for i in range(1, days + 1):
                d = base - timedelta(days=i)
                urls.append(
                    "https://www.gyo.ne.jp/rep_tsuri_history_view"
                    f"|CID-{cid}|hdt-{d:%Y/%m/%d}|dt-{base:%Y/%m/%d}.htm")
        else:
            urls.append(site)

    elif pf == "gyosan":
        root = re.match(r"(https?://[^/]+)", site)
        root = root.group(1) if root else site
        ym, seen = date.today(), set()
        for _ in range(max(1, days // 28 + 1)):
            key = f"{ym:%Y%m}"
            if key not in seen:
                urls.append(f"{root}/search/Archive/{key}/")
                seen.add(key)
            ym = (ym.replace(day=1) - timedelta(days=1))

    else:
        urls.append(site)

    return urls


def collect(boats, days=3, only=None):
    os.makedirs(RAW_DIR, exist_ok=True)
    records, stats = [], {"ok": 0, "empty": 0, "error": 0}

    for b in boats:
        if only and only not in b["name"]:
            continue
        if not b.get("noriai_likely", True):
            continue
        try:
            if not b.get("platform") or b.get("platform") == "own":
                try:
                    html = fetch(b["site"])
                    time.sleep(SLEEP)
                    b["platform"] = detect_platform(html, b["site"])
                except Exception:
                    b["platform"] = b.get("platform") or "own"

            got = 0
            for url in catch_urls(b, days):
                try:
                    html = fetch(url)
                except Exception:
                    time.sleep(SLEEP)
                    continue
                time.sleep(SLEEP)

                text = html_to_text(html)
                fn = re.sub(r"[^A-Za-z0-9]+", "_", f'{b["id"]}_{url}')[:120]
                try:
                    with open(os.path.join(RAW_DIR, fn + ".txt"), "w", encoding="utf-8") as f:
                        f.write(text)
                except Exception:
                    pass

                base = date.today().isoformat()
                m = re.search(r"hdt-(\d{4})/(\d{2})/(\d{2})", url)
                if m:
                    base = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"

                for r in parse_report(text, default_year=date.today().year, base_date=base):
                    if not r.get("date"):
                        continue
                    r["boat"] = b["name"]
                    r["boat_id"] = b["id"]
                    r["area"] = b["area"]
                    r["platform"] = b["platform"]
                    r["source"] = url
                    records.append(r)
                    got += 1

            stats["ok" if got else "empty"] += 1
            print(f'{b["name"]:<14} {b["area"]:<8} {b["platform"]:<8} {got:>4}件')
        except Exception as e:
            stats["error"] += 1
            print(f'{b["name"]:<14} ERROR {type(e).__name__}: {e}')

    return records, stats


def dedupe(records):
    out, seen = [], set()
    for r in records:
        k = (r.get("boat_id"), r.get("trip"), r.get("date"),
             r.get("low"), r.get("top"), r.get("count_unit"))
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--only")
    ap.add_argument("--master", default="boats.json")
    args = ap.parse_args()

    boats = json.load(open(args.master, encoding="utf-8"))
    recs, stats = collect(boats, days=args.days, only=args.only)
    recs = dedupe(recs)

    old = []
    if os.path.exists("catches.json"):
                old = json.load(open("catches.json", encoding="utf-8"))

