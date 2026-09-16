# -*- coding: utf-8 -*-
"""船釣り.jp の都県別一覧から東京湾側の船宿マスタ boats.json を生成する。"""
import json
import re
import sys
import time
import urllib.request

UA = "uodoko-collector/0.1 (personal fishing log aggregator)"

PREF_URLS = {
    "tokyo": "https://funaduri.jp/pref.cgi?pref=tokyo",
    "kanagawa": "https://funaduri.jp/pref.cgi?pref=kanagawa",
    "chiba": "https://funaduri.jp/pref.cgi?pref=chiba",
}

TOKYO_BAY_AREAS = {
    "行徳", "新中川鹿本橋", "奥戸橋", "東葛西", "葛西橋", "千住大橋", "東京湾マリーナ",
    "深川", "浅草橋", "佃島", "品川", "田町", "立会川", "平和島", "羽田",
    "千葉寒川", "船橋", "浦安", "八潮",
    "川崎", "鶴見", "子安", "Ｄマリーナ", "Dマリーナ", "大黒運河沿い", "新山下", "本牧",
    "磯子", "磯子八幡橋", "小柴", "金沢漁港", "金沢八景",
    "新安浦", "大津", "走水", "鴨居", "浦賀", "久比里", "久里浜",
    "金谷", "竹岡", "上総湊", "富津", "木更津", "長浦",
}

NON_NORIAI = re.compile(
    r"(シーバス|SEABASS|Sea ?Frog|SEXY|BLUE DOG|BAY WORKS|Bay Fighter|PALLAS|SEAKURO|"
    r"D-marina|BLEU LANE|Ocean Master|JOY MARINE|VALENTON|SEA WOLF|THE SEA MAN|"
    r"PLAYFUL|うるとら|プレアデス|アイランドクルーズ|Sunny|Sea floating|TARGET|"
    r"ファーストヒット|Mothership|ORCA|FriendShip|アップタイド|ベイポイント|シーホース|"
    r"ピーズ|なぶら|SWEET WATERS|海猫|たけ丸丸|REAL|トレードウインズ|"
    r"三河屋|縄定|船宿内田|わくわく屋|佃中澤|芝浦石川)", re.I)

ROW = re.compile(
    r"\[(?P<area1>[^\]]+)\]\(https://funaduri\.jp/area\.cgi\?area=[^)]+\)"
    r"\[(?P<area2>[^\]]+)\]\(https://funaduri\.jp/area\.cgi\?group=[^)]+\)"
    r"\[(?P<name>[^\]]+)\]\((?P<url>https?://[^)]+)\)"
)


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


def html_to_rows(html: str):
    text = re.sub(r"<a[^>]+href=[\"'](?P<u>[^\"']+)[\"'][^>]*>(?P<t>.*?)</a>",
                  lambda m: f'[{re.sub(r"<[^>]+>", "", m.group("t")).strip()}]({m.group("u")})',
                  html, flags=re.S | re.I)
    text = re.sub(r"<li[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return text.split("\n")


def pre_detect(url: str) -> str:
    u = url.lower()
    if "gyo.ne.jp" in u: return "gyo"
    if "ggnet.co.jp" in u: return "ggnet"
    if "chowari.jp" in u: return "chowari"
    if "fishing-v.jp" in u: return "fv"
    return "own"


def build():
    boats, seen = [], set()
    for pref, url in PREF_URLS.items():
        html = fetch(url)
        for line in html_to_rows(html):
            m = ROW.search(line)
            if not m:
                continue
            area2 = m.group("area2").strip()
            if area2 not in TOKYO_BAY_AREAS:
                continue
            name = m.group("name").strip()
            site = m.group("url").strip()
            if (name, area2) in seen:
                continue
            seen.add((name, area2))
            boats.append({
                "id": f"{pref[:2]}-{len(boats)+1:03d}",
                "name": name,
                "pref": pref,
                "area": area2,
                "region": m.group("area1").strip(),
                "site": site,
                "platform": pre_detect(site),
                "noriai_likely": not bool(NON_NORIAI.search(name)),
                "catch_url": None,
            })
        time.sleep(1.5)
    return boats


if __name__ == "__main__":
    boats = build()
    from collections import Counter
    print("取得件数:", len(boats), dict(Counter(b["pref"] for b in boats)))
    print("乗合候補:", sum(1 for b in boats if b["noriai_likely"]))
    with open("boats.json", "w", encoding="utf-8") as f:
        json.dump(boats, f, ensure_ascii=False, indent=1)
    print("-> boats.json")
