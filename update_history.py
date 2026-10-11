#!/usr/bin/env python3
"""Stáhne historii cen zlata, stříbra a kurz USD/CZK. Zapíše history.json, intraday.json a status.md."""
import csv, datetime as dt, io, json, sys, time, urllib.parse, urllib.request

START = "2020-09-01"
HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json,text/csv,*/*", "Accept-Language": "en-US,en;q=0.9"}
LOG = []

def log(m):
    print(m); LOG.append(m)

def get(url, tries=3):
    err = None
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=HEAD), timeout=40).read().decode()
        except Exception as e:
            err = e; time.sleep(2 * (i + 1))
    raise err

def yahoo(sym, intraday=False):
    p1 = int(dt.datetime(2020, 9, 1).timestamp()); p2 = int(time.time()) + 86400
    q = "range=5d&interval=15m" if intraday else "period1=%d&period2=%d&interval=1d" % (p1, p2)
    last = None
    for host in ("query1", "query2"):
        try:
            r = json.loads(get("https://%s.finance.yahoo.com/v8/finance/chart/%s?%s" % (host, urllib.parse.quote(sym), q), 2))["chart"]["result"][0]
            pairs = [(t, c) for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c]
            if intraday:
                return {int(t) * 1000: c for t, c in pairs}
            return {dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"): c for t, c in pairs}
        except Exception as e:
            last = e
    raise last

def stooq(sym):
    rows = csv.DictReader(io.StringIO(get("https://stooq.com/q/d/l/?s=%s&i=d" % sym)))
    return {r["Date"]: float(r["Close"]) for r in rows if r["Date"] >= START and r.get("Close")}

def frankfurter():
    j = json.loads(get("https://api.frankfurter.dev/v1/%s..?base=USD&symbols=CZK" % START))
    return {d: v["CZK"] for d, v in j["rates"].items()}

def first(name, *cands):
    for label, fn in cands:
        try:
            d = fn()
            if len(d) > 50:
                log("OK: %s ze zdroje %s (%d bodů)" % (name, label, len(d))); return d
            log("MÁLO DAT: %s ze zdroje %s (%d bodů)" % (name, label, len(d)))
        except Exception as e:
            log("CHYBA: %s ze zdroje %s: %s" % (name, label, str(e)[:140]))
    return {}

def inflation():
    try:
        j = json.loads(get("https://api.worldbank.org/v2/country/CZ/indicator/FP.CPI.TOTL.ZG?format=json&per_page=20&date=2020:2026"))
        return {r["date"]: round(r["value"], 2) for r in j[1] if r.get("value") is not None}
    except Exception as e:
        log("CHYBA: inflace: %s" % str(e)[:140]); return {}

def save_status(ok):
    with open("status.md", "w", encoding="utf-8") as f:
        f.write("## Stažení historických cen: %s\n\n" % ("v pořádku" if ok else "SELHALO"))
        f.write("\n".join("- " + m for m in LOG) + "\n")

def main():
    xau = first("zlato", ("Yahoo XAUUSD=X", lambda: yahoo("XAUUSD=X")), ("Stooq xauusd", lambda: stooq("xauusd")), ("Yahoo GC=F", lambda: yahoo("GC=F")))
    xag = first("stříbro", ("Yahoo XAGUSD=X", lambda: yahoo("XAGUSD=X")), ("Stooq xagusd", lambda: stooq("xagusd")), ("Yahoo SI=F", lambda: yahoo("SI=F")))
    fx = first("kurz USD/CZK", ("Frankfurter", frankfurter), ("Yahoo CZK=X", lambda: yahoo("CZK=X")), ("Stooq usdczk", lambda: stooq("usdczk")))
    if not (xau and xag and fx):
        log("Nepodařilo se získat všechny tři řady, history.json se nemění (zůstává předchozí, pokud existuje).")
        save_status(False); sys.exit(1)

    rows, last = [], [None, None, None]
    for d in sorted(set(xau) | set(xag) | set(fx)):
        last = [xau.get(d, last[0]), xag.get(d, last[1]), fx.get(d, last[2])]
        if None not in last:
            rows.append([d, round(last[0], 2), round(last[1], 3), round(last[2], 4)])
    now = dt.datetime.utcnow().isoformat() + "Z"
    with open("history.json", "w") as f:
        json.dump({"updated": now, "daily": rows, "inflation": inflation()}, f, separators=(",", ":"))
    log("history.json: %d dnů" % len(rows))

    intra = []
    try:
        gi, si = yahoo("XAUUSD=X", True), yahoo("XAGUSD=X", True)
        fxd, fxlast, lx, ls = {r[0]: r[3] for r in rows}, rows[-1][3], None, None
        for t in sorted(set(gi) | set(si)):
            lx, ls = gi.get(t, lx), si.get(t, ls)
            if lx and ls:
                intra.append([t, round(lx, 2), round(ls, 3), fxd.get(dt.datetime.utcfromtimestamp(t / 1000).strftime("%Y-%m-%d"), fxlast)])
        log("OK: intradenní data (%d bodů)" % len(intra))
    except Exception as e:
        log("CHYBA: intradenní data: %s" % str(e)[:140])
    with open("intraday.json", "w") as f:
        json.dump({"updated": now, "intraday": intra}, f, separators=(",", ":"))
    save_status(True)

if __name__ == "__main__":
    main()
