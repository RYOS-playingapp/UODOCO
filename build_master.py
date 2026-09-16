# -*- coding: utf-8 -*-
"""船釣り.jp から東京湾の船宿マスタ boats.json を生成する。"""
import json
import re
import time
import urllib.request
from collections import Counter

UA = "Mozilla/5.0 (compatible; uodoko-collector/0.2)"

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
    r"(シーバス|SEABASS|Frog|SEXY|BLUE DOG|BAY WORKS|Fighter|PALLAS|SEAKURO|"
    r"marina|BLEU|Ocean|JOY|VALENTON|WOLF|SEA MAN|PLAYFUL|うるとら|プレアデス|"
    r"クルーズ|Sunny|floating|TARGET|ファーストヒット|Mothership|ORCA|FriendShip|"
    r"アップタイド|ベイポイント|シーホース|ピーズ|なぶら|SWEET|海猫|REAL|"
    r"トレードウインズ|三河屋|縄定|内田|わくわく屋|佃中澤|芝浦石川|屋形)", re.I)

A_TAG = re.compile(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
TAGS = re.compile(r"<[^>]+>")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    for enc in ("utf-8", "cp932", "euc-jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def build():
    boats, seen = [], set()
    for pref, url in PREF_URLS.items():
        try:
            html = fetch(url)
        except Exception as e:
            print(f"  {pref}: 取得失敗 {e}")
            continue

        # ページ内の <a> をすべて拾い、area.cgi?group= の直後に来る外部リンクを宿とみなす
        links = []
        for m in A_TAG.finditer(html):
            href = m.group(1)
            text = TAGS.sub("", m.group(2)).strip()
            links.append((href, text))

        cur_area = None
        n0 = len(boats)
        for href, text in links:
            if "area.cgi?group=" in href:
                cur_area = text
                continue
            if "area.cgi?area=" in href:
                continue
            if not href.startswith("http"):
                continue
            if "funaduri.jp" in href:
                continue
            if not cur_area or cur_area not in TOKYO_BAY_AREAS:
                continue
            name = text
            if not name or len(name) > 30:
                continue
            if (name, cur_area) in seen:
                continue
            seen.add((name, cur_area))
            boats.append({
                "id
