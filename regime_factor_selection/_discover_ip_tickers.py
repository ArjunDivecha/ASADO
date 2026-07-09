"""
Discovery probe (scratch): search //blp/instruments for industrial-production
index tickers for the countries that failed or returned stale series in the
first pass of pull_industrial_production_bbg.py. Prints candidate tickers +
descriptions for human review; does NOT write any deliverable output.

Run: conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
     python3 _discover_ip_tickers.py
"""
import sys
sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
import blpapi  # noqa: E402
from bbg import BBG, bloomberg_setup  # noqa: E402

# country display -> list of search phrases to try
TARGETS = {
    "Australia":    ["Australia Industrial Production", "Australia Manufacturing"],
    "Brazil":       ["Brazil Industrial Production", "Brazil Manufacturing"],
    "Chile":        ["Chile Industrial Production", "Chile Manufacturing"],
    "Denmark":      ["Denmark Industrial Production", "Denmark Manufacturing"],
    "Indonesia":    ["Indonesia Industrial Production", "Indonesia Manufacturing"],
    "Netherlands":  ["Netherlands Industrial Production", "Netherlands Manufacturing"],
    "Philippines":  ["Philippines Industrial Production", "Philippines Manufacturing"],
    "Poland":       ["Poland Industrial Production", "Poland Sold Production"],
    "Saudi Arabia": ["Saudi Arabia Industrial Production", "Saudi Industrial"],
    "Singapore":    ["Singapore Industrial Production", "Singapore Manufacturing"],
    "South Africa": ["South Africa Manufacturing Production", "South Africa Industrial"],
    "Spain":        ["Spain Industrial Production", "Spain Manufacturing"],
    "Taiwan":       ["Taiwan Industrial Production", "Taiwan Manufacturing"],
    "Thailand":     ["Thailand Manufacturing Production", "Thailand Industrial"],
    "Turkey":       ["Turkey Industrial Production", "Turkey Manufacturing"],
    "Vietnam":      ["Vietnam Industrial Production", "Vietnam Manufacturing"],
    "India":        ["India Industrial Production", "India IIP"],
}


def search(session, svc, query, max_results=12):
    req = svc.createRequest("instrumentListRequest")
    req.set("query", query)
    req.set("maxResults", max_results)
    try:
        req.set("yellowKeyFilter", "YK_FILTER_INDX")
    except Exception:
        pass
    session.sendRequest(req)
    out = []
    while True:
        ev = session.nextEvent(5000)
        for msg in ev:
            if msg.hasElement("results"):
                arr = msg.getElement("results")
                for i in range(arr.numValues()):
                    el = arr.getValue(i)
                    sec = el.getElementAsString("security") if el.hasElement("security") else ""
                    desc = el.getElementAsString("description") if el.hasElement("description") else ""
                    out.append((sec, desc))
        if ev.eventType() == blpapi.Event.RESPONSE:
            break
    return out


def main():
    try:
        bloomberg_setup()
    except Exception:
        bloomberg_setup()
    with BBG() as bbg:
        if not bbg.session.openService("//blp/instruments"):
            raise RuntimeError("cannot open //blp/instruments")
        svc = bbg.session.getService("//blp/instruments")
        for country, phrases in TARGETS.items():
            print(f"\n===== {country} =====")
            seen = set()
            for ph in phrases:
                for sec, desc in search(bbg.session, svc, ph):
                    key = sec
                    if key in seen:
                        continue
                    seen.add(key)
                    du = desc.upper()
                    if any(k in du for k in ("PRODUCTION", "MANUFACTUR", "INDUSTRIAL", "IIP", "VALUE ADDED")):
                        print(f"  {sec:24s} | {desc}")


if __name__ == "__main__":
    main()
