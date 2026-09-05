# -*- coding: utf-8 -*-
"""날씨 스냅샷·환율 환산액을 최신값으로 교체.

대상 파일은 argv[1], 기본값은 index.html (GitHub Actions에서 매시 실행).
원본 HTML을 넘기면 아티팩트용 스냅샷도 같이 갱신된다.
"""
import io
import sys
import json
import re
import urllib.request
from datetime import datetime, timedelta

WX_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=48.8566,46.6242,46.5474,47.0502,45.4642,45.4408,43.7696,40.8518,41.9028"
    "&longitude=2.3522,8.0342,7.9855,8.3093,9.1900,12.3155,11.2558,14.2681,12.4964"
    "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m"
    "&daily=temperature_2m_max,temperature_2m_min"
    "&timezone=Europe%2FBerlin&forecast_days=1"
)
FX_URL = "https://open.er-api.com/v6/latest/USD"

CODE = {0: "맑음", 1: "대체로 맑음", 2: "부분 흐림", 3: "흐림", 45: "안개", 48: "서리 안개",
        51: "이슬비", 53: "이슬비", 55: "이슬비", 61: "비", 63: "비", 65: "비",
        66: "어는 비", 67: "어는 비", 71: "눈", 73: "눈", 75: "눈", 77: "싸락눈",
        80: "소나기", 81: "소나기", 82: "소나기", 85: "소낙눈", 86: "소낙눈",
        95: "뇌우", 96: "우박 뇌우", 99: "우박 뇌우"}
CITIES = ["파리", "그린델발트 <em>1,034m</em>", "융프라우요흐 <em>3,454m</em>",
          "루체른", "밀라노", "베네치아", "피렌체", "나폴리", "로마"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "trip-weather/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def num(x):
    return ("%.1f" % float(x)).replace("-", "−")


TARGET = sys.argv[1] if len(sys.argv) > 1 else "index.html"

s = io.open(TARGET, encoding="utf-8").read()

# ---- 날씨 ----
wx = get(WX_URL)
assert isinstance(wx, list) and len(wx) == 9, "unexpected weather payload"

cards = []
for i, d in enumerate(wx):
    c, dl = d["current"], d["daily"]
    t, ap = num(c["temperature_2m"]), num(c["apparent_temperature"])
    w = CODE.get(c["weather_code"], "기타")
    if i == 2:
        m = f"체감 {ap}° · 바람 {num(c['wind_speed_10m'])}km/h"
        cards.append(f'<div class="sc-card alp"><span class="sc-city">{CITIES[i]}</span>'
                     f'<span class="sc-t">{t}°</span><span class="sc-m">{m}</span>'
                     f'<span class="sc-w">{w}</span></div>')
    else:
        m = f"체감 {ap}° · {num(dl['temperature_2m_min'][0])}–{num(dl['temperature_2m_max'][0])}°"
        cards.append(f'<div class="sc-card"><span class="sc-city">{CITIES[i]}</span>'
                     f'<span class="sc-t">{t}°</span><span class="sc-m">{m}</span>'
                     f'<span class="sc-w">{w}</span></div>')

grid = "\n    " + "\n    ".join(cards) + "\n  "
s, n1 = re.subn(r'(<div class="snap-grid">)[\s\S]*?(\n  </div>)',
                lambda mm: mm.group(1) + grid + mm.group(2), s, count=1)
assert n1 == 1, "snap-grid not found"

loc = datetime.fromisoformat(wx[0]["current"]["time"])
kst = loc + timedelta(seconds=9 * 3600 - wx[0]["utc_offset_seconds"])
stamp = (f"{loc.year}.{loc.month:02}.{loc.day:02} {loc.hour:02}:{loc.minute:02} 현지 조회"
         f" · 한국시간 {kst.hour:02}:{kst.minute:02}")
s, n2 = re.subn(r'(<span class="snap-time">)[^<]*(</span>)',
                lambda mm: mm.group(1) + stamp + mm.group(2), s, count=1)
assert n2 == 1, "snap-time not found"

# ---- 환율 (실패해도 날씨는 유지) ----
try:
    fx = get(FX_URL)
    krw = float(fx["rates"]["KRW"])
    chf_krw = krw / float(fx["rates"]["CHF"])
    rate = {"USD": krw, "CHF": chf_krw}

    def krw_repl(mm):
        v = round(float(mm.group(3)) * rate[mm.group(2)] / 1000) * 1000
        return mm.group(1) + f"약 ₩{v:,}" + mm.group(4)

    s = re.sub(r'(<span class="krw" data-cur="(USD|CHF)" data-amt="([\d.]+)">)[^<]*(</span>)',
               krw_repl, s)
    fxd = kst  # 한국 날짜 기준
    fxs = f"{fxd.year}.{fxd.month:02}.{fxd.day:02} · USD {round(krw):,}원 · CHF {round(chf_krw):,}원"
    s = re.sub(r'(<span id="fxTime">)[^<]*(</span>)',
               lambda mm: mm.group(1) + fxs + mm.group(2), s, count=1)
except Exception as e:  # noqa: BLE001
    print("fx skipped:", e)

io.open(TARGET, "w", encoding="utf-8").write(s)
print("updated:", stamp, "->", TARGET)
