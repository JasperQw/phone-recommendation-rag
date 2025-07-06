#!/usr/bin/env python3
"""
GSMArena scraper – 2025‑06 update
• Converts ‘Price’ to RM
• Joins continuation rows with ‘, ’
• Uses a default phone list if no CLI args
"""

from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path
from typing import Dict, List
import time, functools, json as _json
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
BASE_URL = "https://www.gsmarena.com/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/125.0.0.0 Safari/537.36")
}
OUT_DIR = Path("gsma_specs")
OUT_DIR.mkdir(exist_ok=True)

DEFAULT_PHONES: List[str] = [
    "vivo_iqoo_10_pro-11701",
    "vivo_iqoo_8_pro-11057",
    "vivo_iqoo_9_pro-11309",
    "oppo_find_x2_pro-9529",
    "oppo_find_x3_pro-10627",
    "oppo_find_x5_pro-11236",
    "oppo_find_x6_pro-12105",
    "oppo_reno6_pro_5g-10904",
    "oppo_reno7_pro_5g-11190",
    "oppo_reno8_pro-11683",
    "realme_11_pro-12261",
    "realme_gt2_pro-11228",
    "realme_gt_neo_3-11436",
    "realme_gt_neo_5-12066",
    "realme_q3_pro_5g-10871"
]
# ---------------------------------------------------------------------------


# ────────────────────────── helper: URL / slug ─────────────────────────────
def slug_to_url(slug: str) -> str:
    if slug.startswith("http"):
        return slug
    return f"{BASE_URL}{slug}.php" if not slug.endswith(".php") else f"{BASE_URL}{slug}"

# ────────────────────────── helper: live FX rate ───────────────────────────


_FX_FALLBACK = {
    "USD": 4.71,   # snapshot 2025‑06‑28  —— feel free to update anytime
    "EUR": 5.17,
    "GBP": 6.11,
    "INR": 0.056,
}

@functools.lru_cache(maxsize=None)   # <15 min cache to be polite
def get_fx_rate(src: str, tgt: str = "MYR") -> float:
    """
    Return 1 unit of `src` in `tgt` (Ringgit by default).
    Tries exchangerate.host; if that fails, falls back to a snapshot table.
    """
    url = f"https://api.exchangerate.host/latest?base={src}&symbols={tgt}"
    try:
        rate = requests.get(url, timeout=8).json()["rates"][tgt]
        # guard against zero / nonsense
        if rate and rate > 0:
            return rate
    except Exception:
        pass                     # swallow and fall through

    # ––– Fallback –––
    if src == tgt:
        return 1.0
    if src in _FX_FALLBACK:
        return _FX_FALLBACK[src]
    raise RuntimeError(f"No FX data for {src}->{tgt}")

def convert_price_to_myr(raw: str) -> str:
    sym2ccy = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR"}

    # --- 1. find the first recognisable price token ----------------------
    token_patterns = [
        r"([$\u0024€£₹])\s*([\d.,]+)",        # $ 270.54   €226
        r"([\d.,]+)\s*([A-Z]{3})",            # 270.54 EUR
        r"([A-Z]{3})\s*([\d.,]+)",            # EUR 270.54
    ]

    currency = amount = None
    for pat in token_patterns:
        m = re.search(pat, raw)
        if m:
            g1, g2 = m.groups()
            if g1 in sym2ccy:                # symbol‑leading
                currency, amount = sym2ccy[g1], g2
            elif g2 in sym2ccy.values():     # amount + code
                amount, currency = g1, g2
            else:                            # code + amount
                currency, amount = g1, g2
            break

    if not currency or not amount:
        return raw            # nothing recognised → leave original text

    # --- 2. convert to MYR -----------------------------------------------
    try:
        value = float(amount.replace(",", "").replace(" ", "").replace(" ", ""))
        rm  = value * get_fx_rate(currency)   # may use API or fallback
        return f"RM {rm:,.0f}"
    except Exception:
        return raw            # conversion failed → leave original text


# ────────────────────────── core scraping logic ────────────────────────────
def fetch_specs(url: str) -> Dict[str, Dict[str, str]]:
    html = requests.get(url, headers=HEADERS, timeout=15).text
    soup = BeautifulSoup(html, "html.parser")

    # NEW — grab the <h1 class="specs-phone-name-title">
    model_tag = soup.find("h1", class_="specs-phone-name-title")
    model_name = model_tag.get_text(strip=True) if model_tag else "Unknown model"

    specs_div = soup.find("div", id="specs-list")
    if not specs_div:
        raise ValueError("specs‑list block not found")

    phone: Dict[str, Dict[str, str]] = {}
    for tbl in specs_div.select("table"):
        rows = tbl.find_all("tr")
        if not rows:
            continue

        section = rows[0].th.get_text(strip=True)
        sec_dict: Dict[str, str] = {}
        last_key: str | None = None

        for tr in rows:
            key_td = tr.find("td", class_="ttl")
            val_td = tr.find("td", class_="nfo")
            if not val_td:
                continue

            key = re.sub(r"\s+", " ",
                         key_td.get_text(" ", strip=True) if key_td else "")
            val = re.sub(r"\s+", " ", val_td.get_text(" ", strip=True))

            if not key and last_key:          # continuation row
                sec_dict[last_key] += ", " + val
            else:
                sec_dict[key] = val
                last_key = key

        # On‑the‑fly price conversion
        if section == "Misc" and "Price" in sec_dict:
            sec_dict["Price"] = convert_price_to_myr(sec_dict["Price"])

        if sec_dict:
            phone[section] = sec_dict
    phone["Model"] = model_name 
    return phone


# ────────────────────────── dump & driver ──────────────────────────────────
def dump_json(slug: str, payload):
    out = OUT_DIR / f"{slug}.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"✅ {slug}: saved → {out}")


def main(phones: List[str], delay: float):
    phones = phones or DEFAULT_PHONES
    for raw in phones:
        url = slug_to_url(raw)
        slug = Path(url).stem
        try:
            dump_json(slug, fetch_specs(url))
        except Exception as e:
            print(f"❌ {slug}: {e}", file=sys.stderr)
        time.sleep(delay)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Scrape GSMArena specs → JSON")
    p.add_argument("phones", nargs="*", help="slugs or full URLs (optional)")
    p.add_argument("--delay", type=float, default=1.5,
                   help="seconds to sleep between requests (default 1.5)")
    main(**vars(p.parse_args()))
