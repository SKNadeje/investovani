#!/usr/bin/env python3
"""Stáhne denní historii cen zlata, stříbra, kurz USD/CZK a inflaci. Zapíše history.json."""
import csv, datetime as dt, io, json, sys, time, urllib.parse, urllib.request

UA = {"User-Agent": "Mozilla/5.0"}
START = "2020-09-01"

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read().decode()

def yahoo(sym):
    p1 = int(dt.datetime(2020, 9, 1).timestamp()); p2 = int(time.time()) + 86400
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?period1=%d&period2=%d&interval=1d" % (urllib.parse.quote(sym), p1, p2)
    r = json.loads(get(url))["chart"]["result"][0]
    return {dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"): c
            for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c}

def yahoo_intraday(sym):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=5d&interval=15m" % urllib.parse.quote(sym)
    r = json.loads(get(url))["chart"]["result"][0]
    return {int(t)*1000: c for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c}

def stooq(sym):
    rows = csv.DictReader(io.StringIO(get("https://stooq.com/q/d/l/?s=%s&i=d" % sym)))
    return {r["Date"]: float(r["Close"]) for r in rows if r["Date"] >= START and r.get("Close")}

def frankfurter():
    j = json.loads(get("https://api.frankfurter.dev/v1/%s..?base=USD&symbols=CZK" % START))
    return {d: v["CZK"] for d, v in j["rates"].items()}

def first(name, *fns):
    for f in fns:
        try:
            d = f()
            if len(d) > 50:
                print(name, "OK", len(d)); return d
        except Exception as e:
            print(name, "selhalo:", e)
    print(name, "nedostupné"); return {}

def inflation():
    try:
        j = json.loads(get("https://api.worldbank.org/v2/country/CZ/indicator/FP.CPI.TOTL.ZG?format=json&per_page=20&date=2020:2026"))
        return {r["date"]: round(r["value"], 2) for r in j[1] if r.get("value") is not None}
    except Exception as e:
        print("inflace selhala:", e); return {}

xau = first("zlato", lambda: yahoo("XAUUSD=X"), lambda: stooq("xauusd"), lambda: yahoo("GC=F"))
xag = first("stříbro", lambda: yahoo("XAGUSD=X"), lambda: stooq("xagusd"), lambda: yahoo("SI=F"))
fx = first("kurz", frankfurter, lambda: yahoo("CZK=X"), lambda: stooq("usdczk"))
if not (xau and xag and fx):
    sys.exit("Chybí zdroj cen, history.json se nevytvoří.")

rows, last = [], [None, None, None]
for d in sorted(set(xau) | set(xag) | set(fx)):
    last = [xau.get(d, last[0]), xag.get(d, last[1]), fx.get(d, last[2])]
    if None not in last:
        rows.append([d, round(last[0], 2), round(last[1], 3), round(last[2], 4)])

intra = []
try:
    gi, si = yahoo_intraday("XAUUSD=X"), yahoo_intraday("XAGUSD=X")
    fxd, fxlast = {r[0]: r[3] for r in rows}, rows[-1][3]
    lx = ls = None
    for t in sorted(set(gi) | set(si)):
        lx, ls = gi.get(t, lx), si.get(t, ls)
        if lx and ls:
            day = dt.datetime.utcfromtimestamp(t/1000).strftime("%Y-%m-%d")
            intra.append([t, round(lx, 2), round(ls, 3), fxd.get(day, fxlast)])
    print("intraday:", len(intra), "bodů")
except Exception as e:
    print("intraday selhal:", e)

out = {"updated": dt.datetime.utcnow().isoformat() + "Z", "daily": rows, "intraday": intra, "inflation": inflation()}
with open("history.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
print("history.json:", len(rows), "dnů")
