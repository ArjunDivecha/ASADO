#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: make_live_cockpit.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/cockpit.html
    The scripted mock (source of CSS + markup + render functions).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/cockpit_live.html
    The same cockpit, wired to real data via window.COCKPIT_DATA (cockpit_data.js).

VERSION: 1.2
LAST UPDATED: 2026-07-01
AUTHOR: Arjun Divecha / Claude Code

DESCRIPTION:
Transforms cockpit.html into a TRUE-DATA prototype by (1) injecting a
<script src="cockpit_data.js"> tag and (2) replacing the hardcoded /* DATA */
block with adapters that derive the same constant names from window.COCKPIT_DATA,
plus small honest patches where the loop DB has no series yet (signal IC chart,
country sparkline are labelled UNKNOWN/STALE rather than faked). Pure string
surgery on known anchors in the mock — no behavioural rewrite of the renderers.

v1.1 (2026-07-01, frontend audit fixes F2-F7 + B2/B3/B5 from
docs/AUDIT_FRONTEND_2026_07_01.md):
- F2  absorption phrasing: repriced_against never shows "N% unabsorbed"
- F3  setHor() restored with the replaced signal view
- F4  Brief + Tail views bound to live dislocations/drawdowns/brief pointer
- F5  route()/openCountry() narrate from live TALLY/DRAW/CR, no scripted numbers
- F6  esc()/qs() on warehouse-string HTML sinks and onclick attribute args
- F7  neutral ribbon boot HTML + Return* staleness asterisk + stale-tab poll
- B3  INSUFF verdict badge; B5 producer-error banner; B2 grammar/rounding

v1.2 (2026-07-01, Frontend Alpha Rethink Phase 2 — PRD P1/P2 + Fable's Desk):
- Edge Board view (FVIEWS.edge) replaces "Today" as the default focus —
  ranked claims from gaps, family consensus, event windows, expiring theses
- Consensus Matrix view (FVIEWS.consensus) — 34 countries x validated family
  ranks, quintile agreement votes, conflict flags, per-column verdict chips
- Fable's Desk view (FVIEWS.fable) — the nightly non-deterministic Fable
  connections, every card hard-labelled CONJECTURE with falsifiable checks
- Edge map layer (agreement score) is the new default when consensus fresh;
  combiner-colored "Signal" layer retitled "Lean" (it is outcome-trained)
- Router intents: edge board / consensus·families / fable·connections;
  chips row gains "The Edge Board" and "Fable's desk"

DEPENDENCIES: none (standard library)

USAGE:
  python cos_mockups/make_live_cockpit.py     # writes cockpit_live.html
  (run build_cockpit_data.py first so cockpit_data.js exists)
=============================================================================
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "cockpit.html"
OUT = HERE / "cockpit_live.html"

html = SRC.read_text()

# ---- 1. add a "LIVE" mark in the masthead and load the data global ---------
html = html.replace(
    '<title>ASADO · Chief of Staff</title>',
    '<title>ASADO · Chief of Staff — LIVE</title>',
)
html = html.replace(
    '<title>ASADO · Chief of Staff — LIVE</title>',
    '<title>ASADO · Chief of Staff — LIVE</title>\n'
    '<link rel="icon" href="data:image/svg+xml,'
    '%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E'
    '%3Crect width=%2232%22 height=%2232%22 rx=%226%22 fill=%22%23221F18%22/%3E'
    '%3Ctext x=%2216%22 y=%2222%22 text-anchor=%22middle%22 font-size=%2220%22 fill=%22%23F4EEE1%22 font-family=%22serif%22%3EA%3C/text%3E'
    '%3C/svg%3E">',
)
html = html.replace(
    '<span class="sub">a standing brief, in conversation</span>',
    '<span class="sub">a standing brief, in conversation</span>'
    '<span class="folio" style="margin-left:8px;color:var(--teal);border-color:var(--teal)">LIVE DATA</span>',
)
html = html.replace('The <em>Dislocations</em>', 'Price-Discovery <em>Gaps</em>')
html = html.replace('<span class="where">· 79</span>', '<span class="where">· live</span>')
html = html.replace('id="dislo"></div>', 'id="dislo"></div>')
html = html.replace("<script>\n/* ===== DATA ===== */", '<script src="cockpit_data.js"></script>\n<script>\n/* ===== DATA (LIVE ADAPTER) ===== */')

# ---- 2. replace the hardcoded DATA block with the live adapter -------------
# anchors: from 'const SCORE=' down to the COUNTRY const line (inclusive).
start = html.index("const SCORE=[")
end = html.index("\n", html.index('const COUNTRY={"Brazil"'))
adapter = r'''const D = (window.COCKPIT_DATA)||{};
const STATIC_ISO={"Canada":"CAN","U.S.":"US","NASDAQ":"NDX","US SmallCap":"SML","Mexico":"MEX","Brazil":"BRA","Chile":"CHL","U.K.":"UK","France":"FRA","Germany":"DEU","Netherlands":"NLD","Switzerland":"CHE","Italy":"ITA","Spain":"ESP","Sweden":"SWE","Denmark":"DNK","Poland":"POL","South Africa":"ZAF","Saudi Arabia":"SAU","Turkey":"TUR","ChinaA":"CNA","ChinaH":"CNH","Hong Kong":"HK","Japan":"JPN","Korea":"KOR","Taiwan":"TWN","India":"IND","Indonesia":"IDN","Malaysia":"MYS","Philippines":"PHL","Singapore":"SGP","Thailand":"THA","Vietnam":"VNM","Australia":"AUS"};
const ISO=STATIC_ISO;
// governance pips/scorecard
const SCORE=(D.governance?.dimensions||[]).map(d=>[d.name,(d.status||"red")]);
const GOV_OVERALL=(D.governance?.overall||"amber").toUpperCase();
const GOV_DETAIL=Object.fromEntries((D.governance?.dimensions||[]).map(d=>[d.name,d]));
// gap engine: primary price-discovery object
const GAP=D.gap_engine||{status:"missing",top:[],by_country:{}};
const TOP_GAPS=GAP.top||[];
const GAP_BY_ID=Object.fromEntries(TOP_GAPS.map(g=>[g.gap_id,g]));
Object.values(GAP.by_country||{}).forEach(b=>(b.all||[]).forEach(g=>{if(!(g.gap_id in GAP_BY_ID))GAP_BY_ID[g.gap_id]=g;}));
const GAP_COUNTRY=Object.fromEntries(Object.entries(GAP.by_country||{}).map(([k,v])=>[k,v.primary]));
// Absorption phrasing (F2, 2026-07-01): NEVER render "N% unabsorbed" for a
// repriced_against gap — the unabsorbed fraction clamps to 100% exactly when
// price is moving AGAINST the mechanism, which reads as maximally attractive.
// Show the signed absorption index instead.
function absPhrase(g){const st=g.absorption_state||"unknown";const idx=g.price_absorption_index;
  if(st==="repriced_against")return `repriced against · index ${idx!=null?Number(idx).toFixed(2):"—"}`;
  if(st==="insufficient_signal")return "insufficient signal";
  return `${st} · ${g.unabsorbed_fraction!=null?Math.round(g.unabsorbed_fraction*100)+"% unabsorbed":"—"}`;}
// qs(): quote-safe interpolation for onclick='fn("...")' attribute sinks (F6).
// Escapes backslash + single quote for the JS string literal, then the HTML-
// attribute terminators. esc() (defined later in the mock body) is for text sinks.
function qs(x){return String(x??"").replace(/\\/g,"\\\\").replace(/'/g,"\\'").replace(/"/g,"&quot;").replace(/</g,"&lt;")}
const GAPFEED=TOP_GAPS.map(g=>[g.gap_class||"G", `${g.entity} · ${(g.direction||"").toUpperCase()} ${g.preferred_ticker||""}`, absPhrase(g), `${g.tension_score_current??"—"}`, 1, g.gap_id, g.entity]);
const TILE_BY_COUNTRY=Object.fromEntries((D.map||[]).flatMap(r=>r.tiles.map(t=>[t.country,t])));
// map regions: [region,[[country,return]]]
const REGIONS=(D.map||[]).map(r=>[r.region, r.tiles.map(t=>[t.country, (t.return??0)])]);
// dislocation flags for map tiles (country_ranked)
const CR=(D.dislocations?.country_ranked||[]);
const DISLO=Object.fromEntries(CR.map(x=>[x.entity, `${x.detector} ${x.direction} ${x.severity}σ`]));
const DISLO_READ=Object.fromEntries(CR.map(x=>[x.entity, x.reading||x.archetype]));
const DRAW=D.drawdowns||{};
// signals: dedup by name keeping the strongest (registry already sorted)
const VLABEL={WATCH:"WATCH",WEAK:"WEAK",DEAD:"DEAD",INSUFFICIENT_COVERAGE:"INSUFF"};
const _seen=new Set();
const SIGNALS=(D.signals?.registry||[]).filter(s=>!s.is_sanity).filter(s=>{if(_seen.has(s.name))return false;_seen.add(s.name);return true;})
  .slice(0,7).map(s=>[s.name, VLABEL[s.verdict]||s.verdict, (s.ic??0), (s.nw_t??0), `${s.horizon||""} · harness verdict`]);
const SIGMAP={}; (D.signals?.registry||[]).forEach(s=>{if(!(s.name in SIGMAP))SIGMAP[s.name]=s;}); // keep-first (best, registry is sorted)
function _sigHors(s){return Object.keys(s?.ic_series?.horizons||{});}
function _pickHor(s){const hs=_sigHors(s);if(!hs.length)return null;if(hs.includes(ICHOR))return ICHOR;if(s.horizon&&hs.includes(s.horizon))return s.horizon;return hs[0];}
function _dateShort(d){return (d||"").slice(0,10);}
// tally in fixed order
const _t=D.signals?.tally||{};
const TALLY=[[String(_t.WATCH||0),"WATCH"],[String(_t.WEAK||0),"WEAK"],[String(_t.DEAD||0),"DEAD"],[String(_t.INSUFFICIENT_COVERAGE||0),"INSUFF"]];
const RESEARCH=D.research_desk||{discovery_lab:[],analog_shelf:[],under_triage:[],blind_rulings:[],prospective:[],graveyard:[]};
// dislocation feed: top country rows + structural detector tallies
const _cnt=D.dislocations?.counts||{};
const DISLOFEED=CR.slice(0,5).map(x=>[x.detector, `${x.entity} · ${x.archetype}`, (x.reading||""), `${x.severity}`, (Math.abs(x.severity)>=2?1:0), x.entity])
  .concat((_cnt.D8?[["D8","Stewardship",`${_cnt.D8} open theses`,String(_cnt.D8),0,null]]:[]))
  .concat((_cnt.D9?[["D9","Index-vs-ETF basis",`${_cnt.D9} gaps`,String(_cnt.D9),0,null]]:[]));
// per-country letter data, built from real fundamentals + returns + thesis
const RET=D.returns?.by_country||{};
const THE=D.theses||{};
const COUNTRY=Object.fromEntries(Object.entries(D.countries||{}).map(([n,c])=>{
  const dd=DRAW[n]; const gap=GAP_COUNTRY[n]; const reg=gap?"gap":(DISLO[n]?"dislocation":"—");
  const lede=`${n}: 10Y ${c.y10!=null?Number(c.y10).toFixed(2):"—"}%, 5Y CDS ${c.cds!=null?Math.round(c.cds):"—"}bp, ERP percentile ${c.erp_pctile!=null?Math.round(c.erp_pctile):"—"}.${gap?" Active gap: "+gap.gap_class+" "+gap.direction+" via "+(gap.preferred_ticker||"proxy")+".":(DISLO_READ[n]?" "+DISLO_READ[n]+".":"")}`;
  return [n,{y10:c.y10??null,cds:c.cds??null,s210:c.s210??null,eq:(RET[n]??0),cape:(c.cape_pctile??null),erp:(c.erp_pctile??null),reg,lede,thesis:(THE[n]||[])[0]||null,gap}];
}));
// A7 (2026-07-01): returns layer staleness vs the gap/dislocation clock.
// Rendered as an asterisk on the Return map layer (stale-with-asterisk rule).
const RET_STALE=(()=>{try{const r=new Date(D.returns?.as_of),g=new Date(D.dislocations?.as_of||D.meta?.generated_ts);return Number.isFinite(g-r)&&(g-r)/864e5>35;}catch(e){return false}})();
// Phase 2 (2026-07-01, PRD P1/P2 + Fable's Desk): consensus matrix,
// edge board, and the non-deterministic Fable connections surface.
const CONS=D.consensus||{status:"missing",as_of:null,families:[],matrix:{},agreement:{},conflicts:[],leaders:{long:[],short:[]}};
const EDGE_AGREE=CONS.agreement||{};
const _consFresh=()=>CONS.status==="fresh"||CONS.status==="stale";
const EDGEB=D.edge_board||{as_of:null,slots:[]};
const FABLE=D.fable||{status:"missing",as_of:null,model:null,connections:[]};
'''
html = html[:start] + adapter + html[end:]

# ---- 3. overview "Today" -> real promotion slots --------------------------
old_overview = '''FVIEWS.overview={title:()=>`Today`,opts:()=>``,render:()=>`
  <div class="eyebrow">The standing brief · 17 Jun</div>
  <p class="narr" style="margin-bottom:14px">Three things worth your attention this morning — nothing here is a trade yet; all paper until the harness clears it.</p>
  ${ocard("①","Governance is AMBER","Only because cross-source coverage is partial <em>by design</em> — every other dimension is green.","is the system healthy?","scorecard.json")}
  ${ocard("②","The combiner is your only WATCH","IC 0.057, NW-t 10.7 — but components were selected in-sample. A ceiling, not proof.","open the combiner","live_signals")}
  ${ocard("③","Fresh D1 · Chile","A copper terms-of-trade impulse (+2.0σ) that hasn't repriced into equities.","open Chile","brief · 2026-06-16")}`};'''
new_overview = '''const _NUM=["①","②","③","④","⑤"];
function _slotAction(s){const r=s.route||{};if(r.view==="health")return "is the system healthy?";if(r.view==="signal")return "open signal "+(r.name||"");if(r.view==="gap")return "open gap "+(r.gap_id||"");if(r.view==="country")return "open "+(r.name||"");return s.headline;}
FVIEWS.overview={title:()=>`Today`,opts:()=>``,render:()=>{const _n=(D.today||[]).length;
  return `<div class="eyebrow">The standing brief · ${D.dislocations?.as_of||""}</div>
  <p class="narr" style="margin-bottom:14px">${_n} thing${_n===1?"":"s"} worth your attention — nothing here is a trade yet; all paper until the harness clears it.</p>
  ${(D.today||[]).map((s,i)=>ocard(_NUM[i],esc(s.headline),esc(s.why),qs(_slotAction(s)),esc(s.source))).join("")||'<p class="narr">No promotions today.</p>'}`}};'''
html = html.replace(old_overview, new_overview)

# ---- 4. signal view -> real per-signal stats, honest about missing series --
old_signal = '''FVIEWS.signal={title:p=>`${p.name}`,
  opts:()=>`<div class="opt-group"><div class="opt ${ICHOR==='21'?'on':''}" onclick="setHor('21')">21d</div><div class="opt ${ICHOR==='63'?'on':''}" onclick="setHor('63')">63d</div></div>`,
  render:p=>{const ser=ICHOR==="21"?COMBINER_IC:COMBINER_IC_63;const last=ser[ser.length-1];
   return `<div class="eyebrow">Information coefficient · ${ICHOR}-day</div>
   <div class="subpanel" style="margin-top:0">${lineChart(500,130,ser,"#2C7A6B")}<div style="font-size:10.5px;color:var(--ink-3);margin-top:5px;display:flex;justify-content:space-between"><span>2025-09</span><span>latest <b class="tl">${last.toFixed(3)}</b></span><span>2026-06</span></div></div>
   <div class="statline"><div class="stat"><div class="v tl">${last.toFixed(3)}</div><div class="k">Rank IC</div></div><div class="stat"><div class="v">${ICHOR==='21'?'10.7':'8.1'}</div><div class="k">NW-t</div></div><div class="stat"><div class="v">−</div><div class="k">Defl. SR</div></div></div>
   <p class="narr"><span class="ox">⚑ Caveat (INFERENCE).</span> Strongest IC in the registry, but components were <b>selected in-sample (2026-06)</b> and deflated Sharpe is still negative. A <b>ceiling</b>, not proof — it has not earned champion status.</p>
   <div style="margin-top:8px"><span class="chip" onclick="ask('is the system healthy?')"><span class="tag">SRC</span> live_signals · harness_runs</span></div>`}};
function setHor(h){ICHOR=h;renderFocus()}'''
new_signal = '''FVIEWS.signal={title:p=>`${p.name}`,
  opts:p=>{const s=SIGMAP[p.name]||{};const hs=_sigHors(s);const h=_pickHor(s);if(h)ICHOR=h;return hs.length>1?`<div class="opt-group">${hs.map(x=>`<div class="opt ${ICHOR===x?'on':''}" onclick="setHor('${x}')">${x}</div>`).join("")}</div>`:"";},
  render:p=>{const s=SIGMAP[p.name]||{};const vl={WATCH:"v-watch",WEAK:"v-weak",DEAD:"v-dead",INSUFFICIENT_COVERAGE:"v-dead"}[s.verdict]||"v-weak";const h=_pickHor(s);if(h)ICHOR=h;
   const block=h?(s.ic_series?.horizons?.[h]||{}):{};const pts=block.points||[];const vals=pts.map(x=>x.ic);const stats=(s.ic_horizons||{})[h]||{};
   const mean=stats.mean_ic??s.ic;const nwt=stats.nw_t??s.nw_t;const latest=block.latest_ic??(vals.length?vals[vals.length-1]:null);
   const chart=vals.length>1?`<div class="subpanel" style="margin-top:0">${lineChart(500,130,vals,"#2C7A6B")}<div style="font-size:10.5px;color:var(--ink-3);margin-top:5px;display:flex;justify-content:space-between"><span>${_dateShort(pts[0]?.date)}</span><span>latest <b class="${(latest??0)>=0?'tl':'ox'}">${latest!=null?Number(latest).toFixed(3):"—"}</b></span><span>${_dateShort(block.latest_date||pts[pts.length-1]?.date)}</span></div></div>`:`<p class="narr"><span class="ox">Series unavailable.</span> This archived harness run cannot be reconstructed into a chart; the latest summary row is still shown.</p>`;
   return `<div class="eyebrow">Information coefficient · ${h||s.horizon||"horizon"}</div>
   <div style="margin:2px 0 12px"><span class="verdict ${vl}">${VLABEL[s.verdict]||s.verdict||"—"}</span></div>
   ${chart}
   <div class="statline"><div class="stat"><div class="v ${(mean||0)>0?'pos':'neg'}">${mean!=null?Number(mean).toFixed(3):"—"}</div><div class="k">Mean IC</div></div><div class="stat"><div class="v">${nwt!=null?Number(nwt).toFixed(1):"—"}</div><div class="k">NW-t</div></div><div class="stat"><div class="v">${s.deflated_sharpe!=null?Number(s.deflated_sharpe).toFixed(2):"−"}</div><div class="k">Defl. SR</div></div></div>
   ${vals.length>1?`<p class="narr"><span class="cite">FACT · harness_ic_series</span> ${block.sampled?`${block.sampled_points} sampled points from ${block.n_dates}`:`${block.n_dates||vals.length} points`} of persisted rank-IC history. The verdict is still the <b>harness's</b>, not the Chief of Staff's.</p>`:""}
   ${s.is_sanity?'<p class="narr"><span class="ox">⚑ Diagnostic.</span> This is a sanity-check family, not a promotable signal.</p>':''}
   <div style="margin-top:8px"><span class="chip" onclick="ask('the WEAK signals')"><span class="tag">SRC</span> harness_results · ${s.id||""}</span></div>`}};
function setHor(h){ICHOR=h;renderFocus()}'''
html = html.replace(old_signal, new_signal)
html = html.replace('let ICHOR="21";', 'let ICHOR=null;')

# ---- 5. country letter: null-safe, signed, real thesis chip, no fake spark --
old_country = '''FVIEWS.country={title:p=>`${p.name} <span class="where">· ${(COUNTRY[p.name]||{reg:'—'}).reg}</span>`,
  opts:()=>`<div class="opt-group"><div class="opt on">Markets</div><div class="opt" onclick="ask('downside if it keeps falling')">Tail</div></div>`,
  render:p=>{const c=COUNTRY[p.name]||COUNTRY.Brazil;const dd=DRAW[p.name];
   return `<div class="eyebrow">Country letter · ${ISO[p.name]||""}</div>
   <p class="lede"><span class="dropcap">${p.name[0]}</span>${c.lede}</p>
   <div class="statline">
     <div class="stat"><div class="v">${c.y10.toFixed(2)}<span style="font-size:13px">%</span></div><div class="k">10Y</div></div>
     <div class="stat"><div class="v">${c.cds}<span style="font-size:13px">bp</span></div><div class="k">5Y CDS</div></div>
     <div class="stat"><div class="v pos">+${c.eq}<span style="font-size:13px">%</span></div><div class="k">eq · 21d</div></div>
     <div class="stat"><div class="v">+${c.s210}</div><div class="k">2s10s</div></div></div>
   ${valBar("CAPE percentile",c.cape,"cheap")}${valBar("ERP percentile",c.erp,"rich")}
   <div class="subpanel"><h4>Equity · trailing 21 sessions</h4>${spark(500,70,[0,.4,.2,.7,.5,1.1,.9,1.6,1.3,2.1,1.9,2.6,2.4,3,3.2],"#2C7A6B")}
     <div style="font-size:10.5px;color:var(--ink-3);margin-top:5px;display:flex;justify-content:space-between"><span>26 May</span><span>+3.2%</span><span>16 Jun</span></div></div>
   <div style="margin-top:13px"><span class="chip" onclick="ask('mark the Indonesia thesis')"><span class="tag">PAPER</span> T_20260610_001 · LONG Indonesia · <b class="tl">+8.1%</b></span></div>
   ${dd?`<div class="keyrow" onclick="ask('downside if it keeps falling')"><span class="sw" style="background:var(--oxblood)"></span>JST tail · ${dd}% drawdown →</div>`:""}`}};'''
new_country = '''const _fmt=(v,d=2,suf="")=>v==null?"—":(v.toFixed(d)+suf);
const _sgn=(v,d=1)=>v==null?"—":((v>=0?"+":"")+v.toFixed(d));
FVIEWS.country={title:p=>{const r=(COUNTRY[p.name]||{}).reg;return `${p.name}${r&&r!=="—"?` <span class="where">· ${r}</span>`:""}`},
  opts:p=>{const dd=DRAW[p.name];return dd?`<div class="opt-group"><div class="opt on">Markets</div><div class="opt" onclick="ask('downside if it keeps falling')">Tail</div></div>`:``;},
  render:p=>{const c=COUNTRY[p.name];const dd=DRAW[p.name];
   if(!c)return `<div class="eyebrow">Country letter · ${ISO[p.name]||""}</div><p class="narr">No sovereign/valuation fundamentals in the payload for <b>${esc(p.name)}</b> yet.${DISLO_READ[p.name]?" Dislocation: "+esc(DISLO_READ[p.name])+".":""}${dd?" Trailing drawdown "+dd+"%.":""}</p>`;
   const th=c.thesis;
   return `<div class="eyebrow">Country letter · ${ISO[p.name]||""}</div>
   <p class="lede"><span class="dropcap">${p.name[0]}</span>${esc(c.lede)}</p>
   <div class="statline">
     <div class="stat"><div class="v">${_fmt(c.y10,2)}<span style="font-size:13px">%</span></div><div class="k">10Y</div></div>
     <div class="stat"><div class="v">${c.cds==null?"—":Math.round(c.cds)}<span style="font-size:13px">bp</span></div><div class="k">5Y CDS</div></div>
     <div class="stat"><div class="v ${c.eq>=0?'pos':'neg'}">${_sgn(c.eq,2)}<span style="font-size:13px">%</span></div><div class="k">ret · 1m</div></div>
     <div class="stat"><div class="v">${_sgn(c.s210,2)}</div><div class="k">2s10s</div></div></div>
   ${c.cape!=null?valBar("CAPE percentile",c.cape,c.cape<50?"cheap":"rich"):""}${c.erp!=null?valBar("ERP percentile",c.erp,c.erp<50?"cheap":"rich"):""}
   ${th?`<div style="margin-top:14px"><span class="chip" onclick="ask('mark the ${p.name} thesis')"><span class="tag">${th.paper?'PAPER':'LIVE'}</span> ${th.id} · ${(th.direction||'').toUpperCase()} ${p.name} · <b class="muted">p=${th.probability??'—'}</b></span></div>`:''}
   ${dd?`<div class="keyrow" onclick="ask('downside if it keeps falling')"><span class="sw" style="background:var(--oxblood)"></span>JST tail · ${dd}% trailing drawdown →</div>`:""}`}};'''
html = html.replace(old_country, new_country)

# ---- 5b. Brief view: live as-of/rows + live JST tail + brief file pointer --
# (F4, 2026-07-01) The mock hardcoded "As-of 16 Jun · 79 rows" and a fixed
# Indonesia/Denmark JST footer. Bind all of it to the payload.
old_dislo = '''FVIEWS.dislo={title:()=>`The <em>Brief</em>`,opts:()=>``,render:()=>`
   <div class="eyebrow">As-of 16 Jun · 79 rows</div>
   ${DISLOFEED.map(d=>`<div class="lrow" style="padding-left:0" onclick="${d[5]?`openCountry('${d[5]}')`:`ask('explain stewardship')`}"><div class="code ${d[4]?'hot':''}">${d[0]}</div><div><div class="nm">${d[1]}</div><div class="sub">${d[2]}</div></div><div class="rt"><span class="z">${d[3]}</span></div></div>`).join("")}
   <div class="subpanel" style="border-color:var(--gold-soft)"><h4>Long-cycle tail · JST 1870–2020</h4>
     <div class="keyrow" onclick="openCountry('Indonesia')"><span class="sw" style="background:var(--rust)"></span><b>Indonesia</b> −50% · EM-analogy</div>
     <div class="keyrow" onclick="openCountry('Denmark')"><span class="sw" style="background:var(--oxblood)"></span><b>Denmark</b> −45% · DM (Novo) · p10 →</div></div>`};'''
new_dislo = '''FVIEWS.dislo={title:()=>`The <em>Brief</em>`,opts:()=>``,render:()=>`
   <div class="eyebrow">As-of ${D.dislocations?.as_of||"—"} · ${D.dislocations?.total??"—"} rows</div>
   ${DISLOFEED.map(d=>`<div class="lrow" style="padding-left:0" onclick="${d[5]?`openCountry('${qs(d[5])}')`:`ask('explain stewardship')`}"><div class="code ${d[4]?'hot':''}">${d[0]}</div><div><div class="nm">${esc(d[1])}</div><div class="sub">${esc(d[2])}</div></div><div class="rt"><span class="z">${d[3]}</span></div></div>`).join("")}
   ${Object.keys(DRAW).length?`<div class="subpanel" style="border-color:var(--gold-soft)"><h4>Long-cycle tail · trailing drawdowns</h4>
     ${Object.entries(DRAW).sort((a,b)=>a[1]-b[1]).map(([n,v])=>`<div class="keyrow" onclick="openCountry('${qs(n)}')"><span class="sw" style="background:var(--oxblood)"></span><b>${esc(n)}</b> ${v}% · JST context →</div>`).join("")}</div>`:""}
   ${D.brief?.name?`<p class="narr" style="margin-top:10px"><span class="cite">FACT</span> Full nightly brief: <b>${esc(D.brief.name)}</b> — the richest artifact the loop produces; open it from Data/dislocations/.</p>`:""}`};'''
html = html.replace(old_dislo, new_dislo)

# ---- 5c. Tail view: live drawdowns, honest labels (F4/A3, 2026-07-01) ------
old_tail = '''FVIEWS.tail={title:()=>`Long-cycle <em>Tail</em>`,opts:()=>``,render:()=>`
   <div class="eyebrow">Forward 3y real return · by drawdown bucket</div>
   <div class="subpanel" style="margin-top:0">${fan(500,150)}<div style="font-size:10.5px;color:var(--ink-3);margin-top:6px;text-align:center">p10 · median · p90 · 65 banking-crisis onsets</div></div>
   <p class="narr">Indonesia's <b class="ox">−50% drawdown</b> maps to a bucket with median <b>+18%</b> but p10 <b class="ox">−22%</b> forward 3y — the once-in-a-century downside the modern sample can't see.</p>
   <p class="narr"><span class="ox">UNKNOWN/STALE.</span> Live drawdown is nominal vs a real, DM-calibrated distribution; Indonesia is an <b>EM-analogy</b>. Context only — must clear the harness before sizing.</p>`};'''
new_tail = '''FVIEWS.tail={title:()=>`Long-cycle <em>Tail</em>`,opts:()=>``,render:()=>{
   const dds=Object.entries(DRAW).sort((a,b)=>a[1]-b[1]);const w=dds[0];
   return `<div class="eyebrow">Forward 3y real return · by drawdown bucket · JST 1870–2020</div>
   <div class="subpanel" style="margin-top:0">${fan(500,150)}<div style="font-size:10.5px;color:var(--ink-3);margin-top:6px;text-align:center">p10 · median · p90 · 65 banking-crisis onsets · <b>static DM calibration shape</b></div></div>
   ${dds.length?`<div class="subpanel"><h4>Live trailing drawdowns (nominal)</h4>${dds.map(([n,v])=>`<div class="keyrow" onclick="openCountry('${qs(n)}')"><span class="sw" style="background:var(--oxblood)"></span><b>${esc(n)}</b> ${v}%</div>`).join("")}</div>`:`<p class="narr">No country currently crosses the deep-drawdown threshold.</p>`}
   ${w?`<p class="narr">Deepest: <b class="ox">${esc(w[0])} ${w[1]}%</b>. The dated per-country forward 1/3/5y distributions live in <span class="cite">Data/loop/risk_reports/jst_tail_risk_*.xlsx</span>.</p>`:""}
   <p class="narr"><span class="ox">UNKNOWN/STALE.</span> Live drawdowns are <b>nominal</b> vs a <b>real, DM-calibrated</b> distribution; non-JST countries are EM-analogies. Context only — must clear the harness before sizing.</p>`}};'''
html = html.replace(old_tail, new_tail)

# ---- 6. gap-first map/feed/detail/routing ---------------------------------
html = html.replace('let MAPLAYER="dislocation";', 'let MAPLAYER=(GAP.status==="fresh"?"gap":"dislocation");')
html = html.replace(
    'function renderMapLayers(){$("#maplayers").innerHTML=["return","dislocation","signal"].map(l=>`<div class="opt ${MAPLAYER===l?\\\'on\\\':\\\'\\\'}" onclick="setLayer(\\\'${l}\\\')">${l[0].toUpperCase()+l.slice(1)}</div>`).join("")}',
    'function renderMapLayers(){const layers=(GAP.status==="fresh"?["gap","return","dislocation","signal"]:["return","dislocation","signal"]);$("#maplayers").innerHTML=layers.map(l=>`<div class="opt ${MAPLAYER===l?\\\'on\\\':\\\'\\\'}" onclick="setLayer(\\\'${l}\\\')">${l[0].toUpperCase()+l.slice(1)}</div>`).join("")}'
)
html = html.replace(
    '''function renderMapLayers(){$("#maplayers").innerHTML=["return","dislocation","signal"].map(l=>`<div class="opt ${MAPLAYER===l?'on':''}" onclick="setLayer('${l}')">${l[0].toUpperCase()+l.slice(1)}</div>`).join("")}''',
    '''function renderMapLayers(){const layers=(GAP.status==="fresh"?["gap","return","dislocation","signal"]:["return","dislocation","signal"]);$("#maplayers").innerHTML=layers.map(l=>{const lab=l[0].toUpperCase()+l.slice(1)+(l==="return"&&RET_STALE?"*":"");const tip=(l==="return"&&RET_STALE)?` title="* stale — returns as-of ${(D.returns?.as_of||"").slice(0,10)} vs gaps ${D.dislocations?.as_of||""}"`:"";return `<div class="opt ${MAPLAYER===l?'on':''}"${tip} onclick="setLayer('${l}')">${lab}</div>`}).join("")}'''
)
html = html.replace(
    '''function signalColor(n){const s={"Brazil":.9,"Korea":.8,"Chile":.75,"India":.7,"Mexico":.65,"Taiwan":.6,"Indonesia":.25,"Denmark":.2,"ChinaA":.3,"ChinaH":.3}[n]??.5;return mix([233,220,196],[44,122,107],s)}''',
    '''function signalColor(n){const vals=Object.values(D.combiner?.scores||{}).filter(Number.isFinite);const mn=Math.min(...vals,0),mx=Math.max(...vals,1);const raw=D.combiner?.scores?.[n];const s=raw==null?.5:((raw-mn)/(mx-mn||1));return mix([233,220,196],[44,122,107],Math.max(0,Math.min(1,s)))}'''
)
html = html.replace(
    '''function tile(n,v){let bg,val;
  if(MAPLAYER==="return"){bg=retColor(v);val=(v>0?"+":"")+v.toFixed(1)}
  else if(MAPLAYER==="dislocation"){bg=disloColor(n);val=DISLO[n]?"⚑":""}
  else{bg=signalColor(n);val=""}
  const dd=DRAW[n]?`<span class="dot" style="background:var(--oxblood)"></span>`:"";
  return `<div class="tile${SEL===n?' sel':''}${n==='Saudi Arabia'?' ring':''}" style="background:${bg}" onclick="openCountry('${n}')" title="${n}${DISLO[n]?' · '+DISLO[n]:''}"><span class="iso">${ISO[n]}</span>${dd}<span class="val">${val}</span></div>`;
}''',
    '''function gapColor(n){const g=GAP_COUNTRY[n];if(!g)return 'rgba(233,220,196,.5)';const t=Math.max(0,Math.min(1,(g.tension_score_current??0)/.65));return (g.direction==="long")?mix([233,220,196],[44,122,107],t):mix([233,220,196],[124,45,45],t)}
function tile(n,v){let bg,val;const gt=TILE_BY_COUNTRY[n]||{};const g=GAP_COUNTRY[n];
  if(MAPLAYER==="return"){bg=retColor(v);val=(v>0?"+":"")+v.toFixed(1)}
  else if(MAPLAYER==="gap"){bg=gapColor(n);val=g?"◆":""}
  else if(MAPLAYER==="dislocation"){bg=disloColor(n);val=DISLO[n]?"⚑":""}
  else{bg=signalColor(n);val=""}
  const dd=DRAW[n]?`<span class="dot" style="background:var(--oxblood)"></span>`:"";
  const title=g?`${n} · ${g.gap_class} ${g.direction} ${g.preferred_ticker||''} · ${g.absorption_state||''}`:`${n}${DISLO[n]?' · '+DISLO[n]:''}`;
  return `<div class="tile${SEL===n?' sel':''}${gt.gap_id?' ring':''}" style="background:${bg}" onclick="openCountry('${qs(n)}')" title="${esc(title)}"><span class="iso">${ISO[n]}</span>${dd}<span class="val">${val}</span></div>`;
}'''
)
html = html.replace(
    '''function renderDislo(){$("#dislo").innerHTML=DISLOFEED.map(d=>`<div class="lrow" onclick="${d[5]?`openCountry('${d[5]}')`:`ask('explain stewardship')`}">
    <div class="code ${d[4]?'hot':''}">${d[0]}</div>
    <div><div class="nm" style="font-size:12.5px">${d[1]}</div><div class="sub">${d[2]}</div></div>
    <div class="rt"><span class="z">${d[3]}</span></div></div>`).join("");}''',
    '''function renderDislo(){const rows=(GAP.status==="fresh"&&GAPFEED.length)?GAPFEED:DISLOFEED;$("#dislo").innerHTML=rows.map(d=>`<div class="lrow" onclick="${d[5]?(GAP.status==="fresh"&&GAPFEED.length?`openGap('${d[5]}')`:`openCountry('${d[5]}')`):`ask('explain stewardship')`}">
    <div class="code ${d[4]?'hot':''}">${d[0]}</div>
    <div><div class="nm" style="font-size:12.5px">${d[1]}</div><div class="sub">${d[2]}</div></div>
    <div class="rt"><span class="z">${Number(d[3]).toFixed?Number(d[3]).toFixed(2):d[3]}</span></div></div>`).join("");}'''
)
html = html.replace(
    '''function openSignal(n){go("signal",{name:n});pushMsg("cos",`<b>${n}</b> — its IC history is in the focus panel. The verdict is the harness's, not mine. <span class="cite">live_signals</span>`);}''',
    '''function openSignal(n){ICHOR=null;go("signal",{name:n});pushMsg("cos",`<b>${n}</b> — persisted IC history and latest harness stats are in the focus panel. The verdict is the harness's, not mine. <span class="cite">harness_ic_series</span>`);}
function openGap(id){const g=GAP_BY_ID[id];if(!g)return;go("gap",{id});pushMsg("cos",`Opening <b>${g.entity} ${g.direction}</b> gap via <b>${g.preferred_ticker||'proxy'}</b>. Absorption: ${g.absorption_state||'unknown'}. <span class="cite">gap_episode_marks</span>`);}'''
)

gap_view = r'''
FVIEWS.gap={title:p=>{const g=GAP_BY_ID[p.id]||{};return `${g.entity||"Gap"} <span class="where">· ${(g.gap_class||"gap")} ${(g.direction||"").toUpperCase()}</span>`},
  opts:p=>{const g=GAP_BY_ID[p.id]||{};return g.entity?`<div class="opt-group"><div class="opt on">Gap</div><div class="opt" onclick="openCountry('${g.entity}')">Country</div></div>`:"";},
  render:p=>{const g=GAP_BY_ID[p.id];if(!g)return `<p class="narr">Gap not found in the current payload.</p>`;
   const repAgainst=g.absorption_state==="repriced_against";
   const un=repAgainst?(g.price_absorption_index!=null?Number(g.price_absorption_index).toFixed(2):"—")
            :(g.unabsorbed_fraction==null?"—":Math.round(g.unabsorbed_fraction*100)+"%");
   const unLabel=repAgainst?"absorption idx":"unabsorbed";
   const exp=g.expected_move==null?"—":(g.expected_move*100).toFixed(2)+"%";
   const real=g.realized_move==null?"—":(g.realized_move*100).toFixed(2)+"%";
   const adv=g.dollar_adv_21d==null?"—":"$"+Math.round(g.dollar_adv_21d/1e6).toLocaleString()+"M";
   return `<div class="eyebrow">Price-discovery gap · ${GAP.as_of||""} · ${g.epistemic_tag||"INFERENCE"}</div>
   <p class="lede"><span class="dropcap">${(g.entity||"G")[0]}</span>${esc(g.mechanism_text||"World-state and price-state remain in tension.")}</p>
   ${repAgainst?`<p class="narr"><span class="ox">⚑ Repricing against.</span> Price has moved <b>against</b> this mechanism since open — the market is rejecting the gap, not absorbing it. Tension is decayed accordingly.</p>`:""}
   <div class="statline">
     <div class="stat"><div class="v${repAgainst?" ox":""}">${g.tension_score_current??"—"}</div><div class="k">tension</div></div>
     <div class="stat"><div class="v${repAgainst?" ox":""}">${un}</div><div class="k">${unLabel}</div></div>
     <div class="stat"><div class="v">${g.days_active??"—"}</div><div class="k">days active</div></div>
     <div class="stat"><div class="v">${g.preferred_ticker||"—"}</div><div class="k">expression</div></div></div>
   <div class="subpanel"><h4>Absorption mark</h4>
     <div class="barrow"><div class="k">Expected move</div><div class="track"><div class="fill" style="width:${Math.min(100,Math.abs((g.expected_move||0))*3000)}%;background:var(--gold)"></div></div><div class="pc">${exp}</div></div>
     <div class="barrow"><div class="k">Realized move</div><div class="track"><div class="fill" style="width:${Math.min(100,Math.abs((g.realized_move||0))*3000)}%;background:var(--teal)"></div></div><div class="pc">${real}</div></div>
     <p class="narr" style="margin-top:10px">State: <b>${g.absorption_state||"unknown"}</b>. Provisional until the registered ${g.horizon_bucket||"horizon"} window closes.</p></div>
   <div class="subpanel"><h4>ETF/proxy expression</h4>
     <div class="keyrow"><span class="sw" style="background:var(--teal)"></span><b>${g.preferred_ticker||"—"}</b> · ${g.proxy_type||"proxy"} · ${g.currency_basis||"basis unknown"}</div>
     <div class="keyrow"><span class="sw" style="background:var(--gold)"></span>ADV ${adv} · expense ${g.expense_ratio_bps??"—"} bps · quality ${g.expression_quality??"—"} · liquidity ${g.liquidity_tier||"—"}</div></div>
   <div class="subpanel"><h4>Invalidation</h4><p class="narr">${g.invalidation_rule||"No invalidation rule recorded."}</p></div>
   <div style="margin-top:12px"><span class="chip" onclick="openCountry('${g.entity}')"><span class="tag">COUNTRY</span>${g.entity}</span> <span class="chip"><span class="tag">SRC</span>${(g.source_dislocation_ids||[]).join(", ")||"gap tables"}</span></div>`}};
'''
html = html.replace('FVIEWS.dislo={title:()=>`The <em>Brief</em>`', gap_view + '\nFVIEWS.dislo={title:()=>`The <em>Brief</em>`')

html = html.replace(
    '''function route(t){const q=t.toLowerCase();
  if(/(what should i|care about|brief me|three things|priorit|matter|today|overview)/.test(q)){go("overview");return pushMsg("cos",`Three things, in the focus panel. ① Governance <b style="color:var(--amber)">AMBER</b> (coverage partial by design) <span class="cite" onclick="ask('health')">scorecard.json</span> ② the combiner WATCH — a ceiling <span class="cite" onclick="openSignal('combiner_ridge_daily')">live_signals</span> ③ fresh Chile D1 <span class="cite" onclick="openCountry('Chile')">brief</span>.`)}''',
    '''function route(t){const q=t.toLowerCase();
  if(q.startsWith("open gap ")){openGap(t.split(" ").pop());return}
  if(q.startsWith("open signal ")){openSignal(t.replace(/^open signal /,""));return}
  if(/(what should i|care about|brief me|three things|priorit|matter|today|overview)/.test(q)){go("overview");return pushMsg("cos",`Today is in the focus panel. The third card is now a price-discovery gap when the gap engine is fresh. <span class="cite">cockpit_data</span>`)}'''
)
html = html.replace(
    '''if(/(disloc|brief|tonight|fired|nightly)/.test(q)){go("dislo");return pushMsg("cos",`Tonight's brief — Chile D1, Korea D2, Indonesia D5. <span class="cite">brief · 2026-06-16</span>`)}''',
    '''if(/(gap|price discovery|unabsorbed|absorption|what does price not know)/.test(q)){if(TOP_GAPS[0]){openGap(TOP_GAPS[0].gap_id);return}go("dislo");return pushMsg("cos",`No fresh gap is available; falling back to raw dislocations. <span class="cite">gap_engine</span>`)}
  if(/(disloc|brief|tonight|fired|nightly)/.test(q)){go("dislo");return pushMsg("cos",`The panel lists price-discovery gaps first when fresh; raw detector firings remain the drilldown substrate. <span class="cite">brief · ${D.dislocations?.as_of||""}</span>`)}'''
)
html = html.replace(
    '''if(/(health|scorecard|governance|amber)/.test(q)){go("health");return pushMsg("cos",`Governance is <b style="color:var(--amber)">AMBER</b> — partial cross-source coverage <em>by design</em>; everything else green. <span class="cite">scorecard.json</span>`)}''',
    '''if(/(health|scorecard|governance|amber|red)/.test(q)){go("health");return pushMsg("cos",`Governance is <b>${GOV_OVERALL}</b>; worst dimension wins. <span class="cite">scorecard.json</span>`)}'''
)
html = html.replace(
    '''FVIEWS.health={title:()=>`Governance <em>Scorecard</em>`,opts:()=>``,render:()=>`
   <p class="narr">Overall <b style="color:var(--amber)">AMBER</b> — the system being <em>honest</em>, not broken. Six green; the only amber is <b>cross-source coverage</b>, partial <em>by design</em> until the full sweep ships.</p>
   <table class="dt" style="margin-top:12px"><tbody>${[["run_manifest","green","steps ran fresh; no stale-but-green"],["liveness","green","loop clean; brief committed"],["ledger_integrity","green","no retired reads as live"],["family_registry","green","every variable classifies"],["pit_lag_proof","green","no unproven lag-0"],["cross_source_minimal","amber","coverage 1.0 — partial by design"],["config_guard","green","trust-roots committed"]].map(r=>`<tr style="cursor:default"><td style="width:16px"><span class="pip ${r[1]}"></span></td><td style="font-family:var(--serif);font-size:13px;width:160px">${r[0]}</td><td style="font-family:var(--serif);color:var(--ink-2);font-size:12px">${r[2]}</td></tr>`).join("")}</tbody></table>`};''',
    '''FVIEWS.health={title:()=>`Governance <em>Scorecard</em>`,opts:()=>``,render:()=>`
   <p class="narr">Overall <b class="${(D.governance?.overall||"amber")==="red"?"ox":"tl"}">${GOV_OVERALL}</b> — worst dimension wins. Amber can be honest by design; red means a real trust-root exception is being surfaced.</p>
   <table class="dt" style="margin-top:12px"><tbody>${(D.governance?.dimensions||[]).map(r=>`<tr style="cursor:default"><td style="width:16px"><span class="pip ${r.status||"red"}"></span></td><td style="font-family:var(--serif);font-size:13px;width:160px">${r.name}</td><td style="font-family:var(--serif);color:var(--ink-2);font-size:12px">${r.detail||""}${r.amber_by_design?" · by design":""}</td></tr>`).join("")}</tbody></table>`};'''
)

# ---- 6a-2. Phase 2 (2026-07-01): Edge Board / Consensus Matrix / Fable ----
# PRD_Frontend_Alpha_Rethink P1+P2 + the user's Fable's-Desk request. These
# chained replaces operate on strings ALREADY produced by sections 2/6 above;
# the parity check at the bottom fails loudly if any anchor drifts.

# (a) Edge map layer: agreement color + vote glyphs; combiner layer keeps its
#     key "signal" but is retitled "Lean" (it is outcome-trained, not a vote).
html = html.replace(
    '''function gapColor(n){const g=GAP_COUNTRY[n];''',
    '''function edgeColor(n){const a=EDGE_AGREE[n];if(!a||a.edge==null)return 'rgba(233,220,196,.5)';const t=Math.max(0,Math.min(1,Math.abs(a.edge)));return a.edge>=0?mix([233,220,196],[44,122,107],t):mix([233,220,196],[124,45,45],t)}
function gapColor(n){const g=GAP_COUNTRY[n];'''
)
html = html.replace(
    '''function tile(n,v){let bg,val;const gt=TILE_BY_COUNTRY[n]||{};const g=GAP_COUNTRY[n];
  if(MAPLAYER==="return"){bg=retColor(v);val=(v>0?"+":"")+v.toFixed(1)}
  else if(MAPLAYER==="gap"){bg=gapColor(n);val=g?"◆":""}''',
    '''function tile(n,v){let bg,val;const gt=TILE_BY_COUNTRY[n]||{};const g=GAP_COUNTRY[n];const ag=EDGE_AGREE[n];
  if(MAPLAYER==="return"){bg=retColor(v);val=(v>0?"+":"")+v.toFixed(1)}
  else if(MAPLAYER==="edge"){bg=edgeColor(n);val=ag?(ag.conflict?"✕":(ag.long>=3?"▲":(ag.short>=3?"▼":""))):""}
  else if(MAPLAYER==="gap"){bg=gapColor(n);val=g?"◆":""}'''
)
html = html.replace(
    '''  const title=g?`${n} · ${g.gap_class} ${g.direction} ${g.preferred_ticker||''} · ${g.absorption_state||''}`:`${n}${DISLO[n]?' · '+DISLO[n]:''}`;''',
    '''  const title=(MAPLAYER==="edge"&&ag)?`${n} · edge ${ag.edge??"—"} · ${gt.edge_votes||""}${ag.conflict?" · CONFLICT":""}`:(g?`${n} · ${g.gap_class} ${g.direction} ${g.preferred_ticker||''} · ${g.absorption_state||''}`:`${n}${DISLO[n]?' · '+DISLO[n]:''}`);'''
)
html = html.replace(
    'let MAPLAYER=(GAP.status==="fresh"?"gap":"dislocation");',
    'let MAPLAYER=_consFresh()?"edge":(GAP.status==="fresh"?"gap":"dislocation");'
)
html = html.replace(
    'const layers=(GAP.status==="fresh"?["gap","return","dislocation","signal"]:["return","dislocation","signal"]);',
    'const layers=[...(_consFresh()?["edge"]:[]),...(GAP.status==="fresh"?["gap"]:[]),"return","dislocation","signal"];'
)
html = html.replace(
    'const lab=l[0].toUpperCase()+l.slice(1)+(l==="return"&&RET_STALE?"*":"");',
    'const lab=(l==="signal"?"Lean":l[0].toUpperCase()+l.slice(1))+(l==="return"&&RET_STALE?"*":"");'
)

# (b) The three new focus views, inserted (like gap_view) before the Brief.
phase2_views = r'''
/* ===== Phase 2: Edge Board (P1) — ranked claims from ALL surfaces ===== */
FVIEWS.edge={title:()=>`The <em>Edge Board</em>`,opts:()=>``,render:()=>{
  const slots=EDGEB.slots||[];
  if(!slots.length)return `<p class="narr"><span class="ox">UNKNOWN.</span> No board slots in this payload — either edge_board hasn't been built yet or every claim surface is quiet. <span class="cite">edge_board</span></p>`;
  return `<div class="eyebrow">Ranked claims · ${EDGEB.as_of||"—"} · a governance exception always claims ①</div>
  ${slots.map((s,i)=>`<div class="subpanel" style="cursor:pointer" onclick="edgeRoute(${i})">
    <div style="display:flex;gap:12px"><div style="font-family:var(--display);font-size:24px;color:var(--gold)">${_NUM[i]||(i+1)}</div>
    <div style="flex:1"><div style="display:flex;justify-content:space-between;gap:8px;align-items:baseline"><div style="font-family:var(--display);font-weight:540;font-size:15px;margin-bottom:3px">${esc(s.headline)}</div><span class="cite">${esc(s.epistemic_tag||"INFERENCE")}</span></div>
    <div class="narr">${esc(s.why||"")}</div>
    ${s.agreement_line?`<div class="narr" style="margin-top:4px;color:var(--ink-2)">Agreement: ${esc(s.agreement_line)}</div>`:""}
    ${s.wrong_if?`<div class="narr" style="margin-top:4px"><span class="ox">Wrong if:</span> ${esc(s.wrong_if)}</div>`:""}
    <div style="margin-top:7px"><span class="cite">${esc(s.source||"")}</span></div></div></div></div>`).join("")}
  <p class="narr" style="margin-top:10px"><span class="cite">selection</span> ${esc(EDGEB.selection_note||"")}</p>`}};
function edgeRoute(i){const s=(EDGEB.slots||[])[i];if(!s)return;const r=s.route||{};
  if(r.view==="health")return go("health");
  if(r.view==="gap"&&GAP_BY_ID[r.gap_id])return openGap(r.gap_id);
  if(r.view==="consensus")return go("consensus",{name:r.name});
  if(r.view==="country"&&r.name)return openCountry(r.name);
  go("consensus");}

/* ===== Phase 2: Consensus Matrix (P2) — countries × validated families ===== */
const _VCHIP={WATCH:"v-watch",WEAK:"v-weak",DEAD:"v-dead",UNTESTED:"v-dead"};
function famInfo(k){const f=(CONS.families||[]).find(x=>x.key===k);if(!f)return;
  pushMsg("cos",`<b>${esc(f.label)}</b> — <span class="verdict ${_VCHIP[f.verdict]||"v-weak"}">${esc(f.verdict||"UNTESTED")}</span>${f.ic!=null?` · registered IC ${f.ic}`:""}${f.nw_t!=null?` · NW-t ${f.nw_t}`:""}${f.horizon?` · ${esc(f.horizon)}`:""}. ${esc(f.note||"")} <span class="cite">${esc(f.hypothesis_id||"family_ranks.yaml")}</span>`);}
FVIEWS.consensus={title:()=>`Consensus <em>Matrix</em>`,opts:()=>``,render:p=>{
  if(!(CONS.families||[]).length)return `<p class="narr"><span class="ox">UNKNOWN.</span> family_ranks_daily is not in this payload — run scripts/loop/build_family_ranks.py, then rebuild cockpit_data. <span class="cite">consensus</span></p>`;
  const fams=CONS.families||[];const mat=CONS.matrix||{};
  const rows=Object.keys(mat).sort((a,b)=>((EDGE_AGREE[b]?.edge||0)-(EDGE_AGREE[a]?.edge||0))||a.localeCompare(b));
  const cell=(c,f)=>{const x=(mat[c]||{})[f.key];if(!x)return `<td class="num" style="color:var(--ink-3)">—</td>`;
    const q=Math.max(1,Math.ceil(x.n*.2));const top=x.rank<=q,bot=x.rank>x.n-q;
    const st=top?'background:rgba(44,122,107,.16);font-weight:600':(bot?'background:rgba(124,45,45,.13);font-weight:600':'');
    return `<td class="num" style="${st}" title="${esc(f.label)} · rank ${x.rank} of ${x.n}">${x.rank}</td>`;};
  return `<div class="eyebrow">Rank 1 = strongest long lean · quintile votes · ${CONS.as_of||"—"}${CONS.status==="stale"?` · <span class="ox">STALE vs the dislocation clock</span>`:""}</div>
  <p class="narr">${esc(CONS.voting_note||"")} Header chips carry the <b>harness's</b> verdicts — thin, real edges, not oracle output. ° = context column, never a vote.</p>
  <div style="overflow-x:auto"><table class="dt"><thead><tr><th>Country</th><th style="text-align:right">Votes</th>${fams.map(f=>`<th style="text-align:right;cursor:pointer" onclick="famInfo('${qs(f.key)}')" title="${esc(f.label)} · ${esc(f.verdict||"UNTESTED")}${f.ic!=null?` · IC ${f.ic}`:""}">${esc(f.key)}${f.count_in_agreement?"":"°"}</th>`).join("")}</tr></thead><tbody>
  ${rows.map(c=>{const a=EDGE_AGREE[c];const hl=(p&&p.name===c);return `<tr ${hl?'style="outline:2px solid var(--gold)"':""} onclick="openCountry('${qs(c)}')"><td style="font-family:var(--serif);font-size:12.5px">${esc(c)}</td><td class="num">${a&&a.eligible?`${a.long}L/${a.short}S${a.conflict?' <b class="ox">✕</b>':""}`:"—"}</td>${fams.map(f=>cell(c,f)).join("")}</tr>`}).join("")}
  </tbody></table></div>
  ${(CONS.conflicts||[]).length?`<div class="subpanel"><h4>Conflicts — families in opposite extremes</h4>${CONS.conflicts.map(x=>`<div class="keyrow" onclick="openCountry('${qs(x.country)}')"><span class="sw" style="background:var(--gold)"></span><b>${esc(x.country)}</b> · long: ${(x.long_families||[]).map(esc).join(", ")} vs short: ${(x.short_families||[]).map(esc).join(", ")}</div>`).join("")}<p class="narr" style="margin-top:8px">Disagreement is information — these are candidate looks for the Discovery Lab, not errors.</p></div>`:""}`}};

/* ===== Phase 2: Fable's Desk — non-deterministic synthesis, CONJECTURE only ===== */
FVIEWS.fable={title:()=>`Fable's <em>Desk</em>`,opts:()=>``,render:()=>{
  const cs=FABLE.connections||[];
  const head=`<div class="eyebrow">Non-deterministic synthesis · ${FABLE.as_of||"—"}${FABLE.model?` · ${esc(FABLE.model)}`:""}</div>
  <p class="narr"><span class="ox">CONJECTURE.</span> ${esc(FABLE.note||"Nothing here is a verdict or a trade; every claim must go through the Lab/harness.")}</p>`;
  if(!cs.length)return head+`<p class="narr">No connections artifact — the nightly Fable pass hasn't produced one yet (missing key, ASADO_SKIP_FABLE, or first run pending). <span class="cite">build_fable_connections</span></p>`;
  return head+cs.map((c,i)=>`<details class="subpanel desk-card" ${i===0?"open":""}><summary><h4>CONJECTURE · ${esc(c.confidence||"low")} confidence${c.direction_hint&&c.direction_hint!=="none"?` · ${esc(c.direction_hint)}`:""}</h4>
    <div style="font-family:var(--display);font-size:15px;margin-bottom:7px">${esc(c.title||"")}</div>
    <div>${(c.entities||[]).slice(0,6).map(e=>`<span class="chip" onclick="event.preventDefault();event.stopPropagation();openCountry('${qs(e)}')"><span class="tag">C</span>${esc(e)}</span>`).join(" ")}</div></summary>
    <div class="desk-section"><h5>Mechanism (conjecture)</h5><p class="narr" style="margin:0">${esc(c.mechanism||"")}</p></div>
    <div class="desk-section"><h5>Why non-obvious</h5><p class="narr" style="margin:0">${esc(c.why_non_obvious||"")}</p></div>
    <div class="desk-section"><h5>Falsifiable check</h5><p class="narr" style="margin:0">${esc(c.falsifiable_check||"")}</p></div>
    <div class="muted" style="font-size:10px;margin-top:7px">surfaces: ${(c.surfaces||[]).map(esc).join(", ")} · horizon ${esc(c.horizon||"—")} · ${esc(c.id||"")}</div></details>`).join("")}};
'''
html = html.replace('FVIEWS.dislo={title:()=>`The <em>Brief</em>`', phase2_views + '\nFVIEWS.dislo={title:()=>`The <em>Brief</em>`')

# (c) Persistent nav: the three new views join the desk tabs, in front.
html = html.replace(
    'const DESK_TABS=[["desk_discovery","Discovery Lab"],',
    'const DESK_TABS=[["edge","Edge Board"],["consensus","Consensus"],["fable","Fable\\u2019s Desk"],["desk_discovery","Discovery Lab"],'
)

# (d) Boot into the Edge Board when it has slots (P1 replaces "Today").
html = html.replace(
    'CUR={view:"overview",params:{}};renderFocus();',
    'CUR={view:((EDGEB.slots||[]).length?"edge":"overview"),params:{}};renderFocus();'
)

# (e) Router intents: edge board / consensus·families / fable; the "today"
#     intent lands on the Edge Board when it has slots.
html = html.replace(
    '''  if(/(what should i|care about|brief me|three things|priorit|matter|today|overview)/.test(q)){go("overview");return pushMsg("cos",`Today is in the focus panel. The third card is now a price-discovery gap when the gap engine is fresh. <span class="cite">cockpit_data</span>`)}''',
    '''  if(/(edge board|the board|top claims|best ideas|ranked claims|conviction)/.test(q)){go("edge");return pushMsg("cos",`The Edge Board — ranked claims from every surface (gaps, family consensus, event windows, expiring theses); a governance exception always claims ①. <span class="cite">edge_board · ${EDGEB.as_of||""}</span>`)}
  if(/(consensus|matrix|famil(y|ies)|who do the families|agree|conflict)/.test(q)){go("consensus");const _cl=(CONS.leaders?.long||[])[0];return pushMsg("cos",`The Consensus Matrix — ${(CONS.families||[]).length} validated families, quintile votes, conflicts flagged.${_cl?` Strongest long agreement: <b class="tl">${esc(_cl.country)}</b> (${_cl.votes} votes).`:""} <span class="cite">family_ranks_daily · ${CONS.as_of||""}</span>`)}
  if(/(fable|big.?brain|connection|conjecture|non.?deterministic)/.test(q)){go("fable");return pushMsg("cos",`Fable's Desk — ${(FABLE.connections||[]).length} cross-surface conjecture(s) from the nightly pass. Everything there is <b>CONJECTURE</b> until the Lab/harness clears it. <span class="cite">fable_connections · ${FABLE.as_of||""}</span>`)}
  if(/(what should i|care about|brief me|three things|priorit|matter|today|overview)/.test(q)){if((EDGEB.slots||[]).length){go("edge");return pushMsg("cos",`The Edge Board is in the focus panel — ${EDGEB.slots.length} ranked claim(s) tonight, governance exception first. <span class="cite">edge_board · ${EDGEB.as_of||""}</span>`)}go("overview");return pushMsg("cos",`Today is in the focus panel. The third card is now a price-discovery gap when the gap engine is fresh. <span class="cite">cockpit_data</span>`)}'''
)

# (f) Chips + epistemic legend: new entry points, CONJECTURE quarantined.
html = html.replace(
    '$("#chips").innerHTML=["What should I care about today?","Research Desk","Where is pressure building?","The WEAK signals","Brazil","Downside if Indonesia keeps falling?"]',
    '$("#chips").innerHTML=["What should I care about today?","The Edge Board","Consensus Matrix","Fable\\u2019s desk","Where is pressure building?","The WEAK signals","Research Desk"]'
)
html = html.replace(
    '<span class="gkey"><span><b>FACT</b> cited</span><span><b>INFERENCE</b> labelled</span><span><b>UNKNOWN/STALE</b> aloud</span></span>',
    '<span class="gkey"><span><b>FACT</b> cited</span><span><b>INFERENCE</b> labelled</span><span><b>CONJECTURE</b> quarantined</span><span><b>UNKNOWN/STALE</b> aloud</span></span>'
)

# ---- 6b. F5/F6/B2/B3 (2026-07-01): live narrations, escaped sinks ---------
# Sidebar signal list: INSUFF badge class + quote-safe onclick (B3/F6).
html = html.replace(
    '''function renderSigs(){const vmap={WATCH:"v-watch",WEAK:"v-weak",DEAD:"v-dead"};
  $("#sigs").innerHTML=SIGNALS.map(s=>`<div class="lrow" onclick="openSignal('${s[0]}')">
    <div><div class="nm">${s[0]}</div><div class="sub">t ${s[3].toFixed(1)} · IC ${s[2].toFixed(3)}</div></div>
    <div class="rt"><span class="verdict ${vmap[s[1]]}">${s[1]}</span></div></div>`).join("");}''',
    '''function renderSigs(){const vmap={WATCH:"v-watch",WEAK:"v-weak",DEAD:"v-dead",INSUFF:"v-dead"};
  $("#sigs").innerHTML=SIGNALS.map(s=>`<div class="lrow" onclick="openSignal('${qs(s[0])}')">
    <div><div class="nm">${esc(s[0])}</div><div class="sub">t ${s[3].toFixed(1)} · IC ${s[2].toFixed(3)}</div></div>
    <div class="rt"><span class="verdict ${vmap[s[1]]||"v-weak"}">${s[1]}</span></div></div>`).join("");}'''
)
# Signals table: same badge + escaping treatment.
html = html.replace(
    '''render:()=>{let r=[...SIGNALS];if(SIGSORT==='ic')r.sort((a,b)=>b[2]-a[2]);else r.sort((a,b)=>b[3]-a[3]);const vmap={WATCH:"v-watch",WEAK:"v-weak",DEAD:"v-dead"};
   return `<table class="dt"><thead><tr><th>Signal</th><th>Verdict</th><th style="text-align:right" onclick="setSort('ic')">IC</th><th style="text-align:right" onclick="setSort('nwt')">NW-t</th></tr></thead><tbody>
   ${r.map(s=>`<tr onclick="openSignal('${s[0]}')"><td style="font-family:var(--serif);font-size:13px">${s[0]}</td><td><span class="verdict ${vmap[s[1]]}">${s[1]}</span></td><td class="num">${s[2].toFixed(3)}</td><td class="num">${s[3].toFixed(1)}</td></tr>`).join("")}''',
    '''render:()=>{let r=[...SIGNALS];if(SIGSORT==='ic')r.sort((a,b)=>b[2]-a[2]);else r.sort((a,b)=>b[3]-a[3]);const vmap={WATCH:"v-watch",WEAK:"v-weak",DEAD:"v-dead",INSUFF:"v-dead"};
   return `<table class="dt"><thead><tr><th>Signal</th><th>Verdict</th><th style="text-align:right" onclick="setSort('ic')">IC</th><th style="text-align:right" onclick="setSort('nwt')">NW-t</th></tr></thead><tbody>
   ${r.map(s=>`<tr onclick="openSignal('${qs(s[0])}')"><td style="font-family:var(--serif);font-size:13px">${esc(s[0])}</td><td><span class="verdict ${vmap[s[1]]||"v-weak"}">${s[1]}</span></td><td class="num">${s[2].toFixed(3)}</td><td class="num">${s[3].toFixed(1)}</td></tr>`).join("")}'''
)
# openCountry(): drop the hardcoded "reflation"; narrate from live state (A5).
html = html.replace(
    '''function openCountry(n){go("country",{name:n});pushMsg("cos",`Opening <b>${n}</b> into the focus panel — ${COUNTRY[n]?`10Y ${COUNTRY[n].y10}%, reflation`:`${DISLO[n]?DISLO[n]+'; ':''}${DRAW[n]?DRAW[n]+'% drawdown':'no active dislocation'}`}. <span class="cite">country panel</span>`);}''',
    '''function openCountry(n){go("country",{name:n});const c=COUNTRY[n];const bits=[];
  if(c&&c.y10!=null)bits.push(`10Y ${Number(c.y10).toFixed(2)}%`);
  if(c&&c.gap)bits.push(`active ${c.gap.gap_class} gap ${c.gap.direction}`);
  else if(DISLO[n])bits.push(esc(DISLO[n]));
  if(DRAW[n])bits.push(`${DRAW[n]}% drawdown`);
  pushMsg("cos",`Opening <b>${esc(n)}</b> into the focus panel${bits.length?" — "+bits.join(", "):""}. <span class="cite">country panel</span>`);}'''
)
# route(): registry tally from TALLY, live tail/pressure leaders, honest fallback (A5).
html = html.replace(
    '''if(/(weak|signals|registry|verdict|dead|all the signal)/.test(q)){go("signals");return pushMsg("cos",`The registry — <b>2 WATCH · 39 WEAK · 31 DEAD</b>. <span class="cite">live_signals</span>`)}''',
    '''if(/(weak|signals|registry|verdict|dead|all the signal)/.test(q)){go("signals");return pushMsg("cos",`The registry — <b>${TALLY.map(([n,l])=>`${n} ${l}`).join(" · ")}</b>. <span class="cite">live_signals</span>`)}'''
)
html = html.replace(
    '''if(/(downside|tail|drawdown|jst|crash|falling)/.test(q)){go("tail");return pushMsg("cos",`The long-cycle tail. Indonesia's −50% → median +18% but <b class="ox">p10 −22%</b> forward 3y. Context only. <span class="cite">jst_tail_risk</span>`)}''',
    '''if(/(downside|tail|drawdown|jst|crash|falling)/.test(q)){go("tail");const _dd=Object.entries(DRAW).sort((a,b)=>a[1]-b[1])[0];return pushMsg("cos",`The long-cycle tail.${_dd?` Deepest live drawdown: <b class="ox">${esc(_dd[0])} ${_dd[1]}%</b> — nominal, read against a real DM-calibrated JST distribution.`:" No country currently crosses the deep-drawdown threshold."} Context only. <span class="cite">jst_tail_risk</span>`)}'''
)
html = html.replace(
    '''if(/(pressure|map|where|flows|world)/.test(q)){go("overview");setLayer("dislocation");return pushMsg("cos",`Pressure is in three places — see the map (dislocation layer): <b class="ox">Chile</b>, <b class="ox">Korea</b>, <b class="ox">Indonesia</b>. Click any to drill in. <span class="cite">brief</span>`)}''',
    '''if(/(pressure|map|where|flows|world)/.test(q)){go("overview");setLayer(GAP.status==="fresh"?"gap":"dislocation");const _ld=CR.slice(0,3).map(x=>`<b class="ox">${esc(x.entity)}</b>`).join(", ");return pushMsg("cos",`Pressure now — see the map: ${_ld||"no ranked countries tonight"}. Click any tile to drill in. <span class="cite">brief · ${D.dislocations?.as_of||""}</span>`)}'''
)
html = html.replace(
    '''go("overview");pushMsg("cos",`Here's today. Try "the WEAK signals", "Brazil", or "downside if Indonesia keeps falling". <span class="muted">(prototype: scripted)</span>`)}''',
    '''go("overview");pushMsg("cos",`Here's today. Try "the WEAK signals", a country name, or "downside if it keeps falling". <span class="cite">local router</span>`)}'''
)
# Ribbon initial HTML: neutral until boot binds live values (A6).
html = html.replace(
    '<span class="lab">Governance</span><span class="overall">AMBER</span>',
    '<span class="lab">Governance</span><span class="overall">—</span>'
)
html = html.replace(
    'data as-of <b>16 Jun 2026</b><br><span class="muted">refreshed 07:32 · loop ✓</span>',
    'data as-of <b>—</b><br><span class="muted">loading…</span>'
)

# ---- 7. openSignal should route by real name; keep generic --------------
# (openSignal already calls go("signal",{name:n}) — fine.)

# ---- 8. boot chrome and greeting: make them live/generic ------------------
html = html.replace(
    '''$("#pips").innerHTML=SCORE.map(s=>`<span class="pip ${s[1]}" title="${s[0]}"></span>`).join("");''',
    '''$("#pips").innerHTML=SCORE.map(s=>`<span class="pip ${s[1]}" title="${s[0]}"></span>`).join("");
document.querySelector(".scorecard .overall").textContent=GOV_OVERALL;
document.querySelector(".scorecard .overall").style.color=(D.governance?.overall==="red"?"var(--red)":(D.governance?.overall==="green"?"var(--green)":"var(--amber)"));
document.querySelector(".date b").textContent=GAP.as_of||D.dislocations?.as_of||D.returns?.as_of||"—";
document.querySelector(".date .muted").textContent=`generated ${D.meta?.generated_ts||"—"} · gap ${GAP.status||"missing"}`;'''
)
html = html.replace(
    'pushMsg("you","What should I care about today?");route("what should I care about today");',
    'pushMsg("you","What should I care about today?");route("what should I care about today");\n'
    '/* LIVE: data generated by build_cockpit_data.py */\n'
    '/* B5 (2026-07-01): surface a producer error instead of silently empty panels */\n'
    'if(D.error){pushMsg("cos",`<span class="ox">⚑ Producer error.</span> ${esc(D.error)} — panels may be empty or stale until build_cockpit_data.py succeeds. <span class="cite">build_cockpit_data</span>`);}\n'
    '/* A8 (2026-07-01): stale-tab detection — poll cockpit_data.js for a newer generated_ts */\n'
    '(function(){const cur=D.meta?.generated_ts;if(!cur||location.protocol==="file:")return;\n'
    'setInterval(async()=>{try{const r=await fetch("cockpit_data.js?ts="+Date.now(),{cache:"no-store"});if(!r.ok)return;const txt=await r.text();const m=txt.match(/"generated_ts":\\s*"([^"]+)"/);\n'
    'if(m&&m[1]!==cur&&!document.getElementById("stale-banner")){const b=document.createElement("div");b.id="stale-banner";\n'
    'b.style.cssText="position:fixed;top:0;left:0;right:0;z-index:99;background:var(--gold);color:#221F18;font-family:var(--display);font-size:13px;text-align:center;padding:7px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.25)";\n'
    'b.textContent="Data refreshed ("+m[1]+") — click to reload";b.onclick=()=>location.reload();document.body.appendChild(b);}}catch(e){}},300000);})();',
)

# ---- 9. generation parity check (F3/audit item 3, 2026-07-01) --------------
# String surgery silently no-ops when an anchor in cockpit.html drifts. FAIL
# LOUDLY instead: every function the generated page calls must exist, and no
# scripted mock narration may survive into the live build.
REQUIRED = [
    "function setHor(",            # B1: horizon toggle handler
    "function absPhrase(",         # F2: absorption phrasing
    "function qs(",                # F6: quote-safe onclick args
    "function openGap(",           # gap feed click handler
    "FVIEWS.gap=",                 # gap detail view
    "window.COCKPIT_DATA",         # live adapter bound
    "stale-banner",                # A8: stale-tab poll
    "RET_STALE",                   # A7: returns staleness asterisk
    # Phase 2 (2026-07-01): Edge Board / Consensus Matrix / Fable's Desk
    "FVIEWS.edge=",                # P1: the Edge Board view
    "FVIEWS.consensus=",           # P2: the Consensus Matrix view
    "FVIEWS.fable=",               # Fable's Desk view
    "function edgeColor(",         # Edge map layer coloring
    "function edgeRoute(",         # board card routing
    "function famInfo(",           # matrix column header drilldown
    "CONJECTURE</b> quarantined",  # epistemic legend extended
    'MAPLAYER=_consFresh()?"edge"',# Edge is the default map layer when fresh
]
FORBIDDEN = [
    "(prototype: scripted)",       # A5: scripted fallback
    "2 WATCH · 39 WEAK · 31 DEAD", # A5: stale tally
    "16 Jun 2026",                 # A6: mock ribbon date
    "%, reflation",                # A5: openCountry mock narration
    "Indonesia</b> −50%",          # A3/A4: mock JST rows
    "As-of 16 Jun · 79 rows",      # A4: mock brief header
]
_missing = [t for t in REQUIRED if t not in html]
_leaked = [t for t in FORBIDDEN if t in html]
if _missing or _leaked:
    raise SystemExit(
        f"[FAIL] generation parity: missing={_missing} leaked_mock={_leaked} — "
        "an anchor in cockpit.html has drifted; fix make_live_cockpit.py before shipping."
    )

OUT.write_text(html)
print(f"[OK] wrote {OUT}  ({len(html)//1024} KB, parity checks passed)")
