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

out = {"updated": dt.datetime.utcnow().isoformat() + "Z", "daily": rows, "inflation": inflation()}
with open("history.json", "w") as f:
    json.dump(out, f, separators=(",", ":"))
print("history.json:", len(rows), "dnů")
