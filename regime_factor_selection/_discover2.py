"""Scratch: broader search for MONTHLY IP-YoY for Netherlands, Thailand, Australia."""
import sys
sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
import blpapi  # noqa
from bbg import BBG, bloomberg_setup  # noqa

PHRASES = {
    "Netherlands": ["Netherlands Production Industry YoY", "Netherlands Industrial Production Monthly",
                    "Netherlands Manufacturing Production YoY", "Netherlands Industry YoY"],
    "Thailand": ["Thailand Manufacturing Production Index YoY", "Thailand Production Index YoY",
                 "Thailand Industrial Production YoY", "Thailand MPI YoY"],
    "Australia": ["Australia Industrial Production Monthly YoY", "Australia Manufacturing Production YoY"],
}

def search(session, svc, q, n=15):
    req = svc.createRequest("instrumentListRequest")
    req.set("query", q); req.set("maxResults", n)
    try: req.set("yellowKeyFilter", "YK_FILTER_INDX")
    except Exception: pass
    session.sendRequest(req)
    out=[]
    while True:
        ev=session.nextEvent(5000)
        for m in ev:
            if m.hasElement("results"):
                a=m.getElement("results")
                for i in range(a.numValues()):
                    e=a.getValue(i)
                    s=e.getElementAsString("security") if e.hasElement("security") else ""
                    d=e.getElementAsString("description") if e.hasElement("description") else ""
                    out.append((s,d))
        if ev.eventType()==blpapi.Event.RESPONSE: break
    return out

def main():
    try: bloomberg_setup()
    except Exception: bloomberg_setup()
    with BBG() as bbg:
        bbg.session.openService("//blp/instruments")
        svc=bbg.session.getService("//blp/instruments")
        for c,phr in PHRASES.items():
            print(f"\n===== {c} =====")
            seen=set()
            for p in phr:
                for s,d in search(bbg.session,svc,p):
                    if s in seen: continue
                    seen.add(s)
                    du=d.upper()
                    if ("YOY" in du or "YY%" in du or "YEAR" in du) and any(k in du for k in ("PRODUCTION","MANUFACTUR","INDUSTRIAL","IIP")):
                        print(f"  {s:24s} | {d}")

if __name__=="__main__":
    main()
