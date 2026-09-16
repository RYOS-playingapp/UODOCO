# -*- coding: utf-8 -*-
"""
釣果テキスト → 構造化データ

船宿が公開するのは「その日の最少〜最多（スソ〜竿頭）」のレンジ。
乗船者ごとの内訳は公開されないので、レンジと船種を正確に取ることに集中する。

同じ「アジ」でも 午前アジ / 午後アジ / タチアジリレー は
コンディションが違う別物として分離して保持する。
"""
import re
import unicodedata

# ---- 正規化 ----------------------------------------------------------------

def normalize(text: str) -> str:
    """全角英数・記号を半角へ。波ダッシュ類を ~ に統一。"""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)
    for ch in ("〜", "～", "‐", "–", "—"):
        t = t.replace(ch, "~")
    t = re.sub(r"[ \t\u3000]+", " ", t)
    return t


# ---- 船種（便）の見出し ----------------------------------------------------
TRIP_BRACKET = re.compile(r"[【≪\[（(]\s*([^】≫\]）)]{2,30}?船?)\s*[】≫\]）)]")
LEAD_DECO = re.compile(r"^[^ぁ-んァ-ヶ一-龥A-Za-z0-9【≪\[（(]+")
TRIP_BARE = re.compile(r"^([ぁ-んァ-ヶー一-龥A-Za-z0-9・／/ 　]{2,28}船)\s*(?:[（(][^）)]{0,10}[）)])?\s*$")

TRIP_HINT = re.compile(
    r"(午前|午後|夜|ショート|半日|一日|1日|リレー|テンヤ|天秤|ビシ|LT|ＬＴ|ライト|スポット|バチコン|"
    r"アジ|タチ|タコ|ダコ|フグ|キス|ギス|カサゴ|メバル|アナゴ|ナゴ|カワハギ|ハギ|イカ|マゴチ|ゴチ|"
    r"マダイ|ダイ|五目|ウィリー|サワラ|ヒラメ|イサキ|ワラサ|アカムツ|ムツ|カレイ|ハゼ|スミイカ)"
)

TRIP_NG = re.compile(r"(料金|予約|キャンセル|定休|案内|規定|レンタル|割引|注意|お願い|募集|保険|駐車)")


def find_trip(line: str):
    """1行から便名を取り出す。見つからなければ None。"""
    s = normalize(line).strip()
    s = re.sub(r"※.*$", "", s).strip()
    if not s or TRIP_NG.search(s):
        return None
    if re.search(r"\d+\s*~\s*\d+\s*(?:匹|本|杯|尾|枚)", s):
        return None
    s = LEAD_DECO.sub("", s).strip()
    if not s:
        return None
    m2 = TRIP_BARE.match(s)
    cand = m2.group(1).strip() if m2 else None
    if cand is None:
        m = TRIP_BRACKET.search(s)
        if m and m.start() <= 2:
            cand = m.group(1).strip()
    if cand and TRIP_HINT.search(cand) and len(cand) <= 25:
        return re.sub(r"\s+", "", cand)
    return None


# ---- 釣果レンジ ------------------------------------------------------------
COUNT_UNITS = "匹|本|杯|尾|枚|ハイ"
SIZE_RE = r"(\d+(?:\.\d+)?)\s*~\s*(\d+(?:\.\d+)?)\s*(cm|kg|g)"
COUNT_RE = rf"(\d+)\s*~\s*(\d+)\s*({COUNT_UNITS})"

RE_SIZE_COUNT = re.compile(rf"{SIZE_RE}\s*[ 、,/／:：]*\s*{COUNT_RE}")
RE_COUNT_ONLY = re.compile(COUNT_RE)
RE_MAX_COUNT = re.compile(rf"最大\s*(\d+(?:\.\d+)?)\s*(cm|kg|g)\s*[ 、,/／:：]*\s*{COUNT_RE}")

FISH_WORDS = [
    "マアジ", "アジ", "タチウオ", "タチ", "マダコ", "タコ", "ショウサイフグ", "アカメフグ", "フグ",
    "シロギス", "キス", "アナゴ", "カサゴ", "メバル", "カワハギ", "マゴチ", "マダイ", "イシモチ",
    "サワラ", "スルメイカ", "ヤリイカ", "スミイカ", "アオリイカ", "イカ", "ワラサ", "イナダ",
    "ヒラメ", "イサキ", "五目",
]
RE_FISH = re.compile("(" + "|".join(FISH_WORDS) + ")")


def parse_catch_line(line: str):
    s = normalize(line)
    if not s:
        return None

    fish = None
    mf = RE_FISH.search(s)
    if mf:
        fish = mf.group(1)

    m = RE_SIZE_COUNT.search(s)
    if m:
        return {
            "fish": fish,
            "size_min": float(m.group(1)), "size_max": float(m.group(2)), "size_unit": m.group(3),
            "low": int(m.group(4)), "top": int(m.group(5)), "count_unit": m.group(6),
        }

    m = RE_MAX_COUNT.search(s)
    if m:
        return {
            "fish": fish,
            "size_min": None, "size_max": float(m.group(1)), "size_unit": m.group(2),
            "low": int(m.group(3)), "top": int(m.group(4)), "count_unit": m.group(5),
        }

    m = RE_COUNT_ONLY.search(s)
    if m:
        return {
            "fish": fish,
            "size_min": None, "size_max": None, "size_unit": None,
            "low": int(m.group(1)), "top": int(m.group(2)), "count_unit": m.group(3),
        }
    return None


# ---- 日付 ------------------------------------------------------------------
RE_DATE_FULL = re.compile(r"(20\d{2})[/年\.\-](\d{1,2})[/月\.\-](\d{1,2})")
RE_DATE_MD = re.compile(r"(?<!\d)(\d{1,2})[/月](\d{1,2})日?")
RE_DATE_D = re.compile(r"(?<!\d)(\d{1,2})日(?!\d)")


def parse_date(text: str, default_year: int = None, base_date: str = None):
    s = normalize(text)
    m = RE_DATE_FULL.search(s)
    if m:
        return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = RE_DATE_MD.search(s)
    if m and default_year:
        return f"{default_year:04d}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    if base_date:
        m = RE_DATE_D.search(s)
        if m:
            by, bm, bd = (int(x) for x in base_date.split("-"))
            d = int(m.group(1))
            if d > bd:
                bm -= 1
                if bm == 0:
                    bm = 12
                    by -= 1
            return f"{by:04d}-{bm:02d}-{d:02d}"
    return None


# ---- 本体 ------------------------------------------------------------------

def parse_report(text: str, date: str = None, default_year: int = None, base_date: str = None):
    lines = [l for l in normalize(text).split("\n")]
    out = []
    cur_trip = None
    cur_date = date or base_date
    pending_comment = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        d = parse_date(line, default_year, base_date)
        if d and (len(line) < 40 or "釣果" in line):
            cur_date = d

        t = find_trip(line)
        if t:
            if out and pending_comment:
                out[-1]["comment"] = " ".join(pending_comment)[:300]
            pending_comment = []
            cur_trip = t
            c = parse_catch_line(line)
            if c and (c["top"] or c["low"]):
                rec = {"trip": cur_trip, "date": cur_date, "comment": ""}
                rec.update(c)
                out.append(rec)
            continue

        c = parse_catch_line(line)
        if c:
            if out and pending_comment:
                out[-1]["comment"] = " ".join(pending_comment)[:300]
                pending_comment = []
            rec = {"trip": cur_trip, "date": cur_date, "comment": ""}
            rec.update(c)
            out.append(rec)
        else:
            if out and 6 <= len(line) <= 200 and not TRIP_NG.search(line):
                pending_comment.append(line)

    if out and pending_comment:
        out[-1]["comment"] = " ".join(pending_comment)[:300]

    return [r for r in out if r.get("trip") or r.get("fish")]
