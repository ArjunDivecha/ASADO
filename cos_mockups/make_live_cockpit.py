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

VERSION: 1.0
LAST UPDATED: 2026-06-19
AUTHOR: Arjun Divecha / Claude Code

DESCRIPTION:
Transforms cockpit.html into a TRUE-DATA prototype by (1) injecting a
<script src="cockpit_data.js"> tag and (2) replacing the hardcoded /* DATA */
block with adapters that derive the same constant names from window.COCKPIT_DATA,
plus small honest patches where the loop DB has no series yet (signal IC chart,
country sparkline are labelled UNKNOWN/STALE rather than faked). Pure string
surgery on known anchors in the mock — no behavioural rewrite of the renderers.

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
const GAPFEED=TOP_GAPS.map(g=>[g.gap_class||"G", `${g.entity} · ${(g.direction||"").toUpperCase()} ${g.preferred_ticker||""}`, `${g.absorption_state||"unknown"} · ${Math.round((g.unabsorbed_fraction??0)*100)}% unabsorbed`, `${g.tension_score_current??"—"}`, 1, g.gap_id, g.entity]);
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
  const lede=`${n}: 10Y ${c.y10??"—"}%, 5Y CDS ${c.cds??"—"}bp, ERP percentile ${c.erp_pctile??"—"}.${gap?" Active gap: "+gap.gap_class+" "+gap.direction+" via "+(gap.preferred_ticker||"proxy")+".":(DISLO_READ[n]?" "+DISLO_READ[n]+".":"")}`;
  return [n,{y10:c.y10??null,cds:c.cds??null,s210:c.s210??null,eq:(RET[n]??0),cape:(c.cape_pctile??null),erp:(c.erp_pctile??null),reg,lede,thesis:(THE[n]||[])[0]||null,gap}];
}));
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
FVIEWS.overview={title:()=>`Today`,opts:()=>``,render:()=>`
  <div class="eyebrow">The standing brief · ${D.dislocations?.as_of||""}</div>
  <p class="narr" style="margin-bottom:14px">${(D.today||[]).length} things worth your attention — nothing here is a trade yet; all paper until the harness clears it.</p>
  ${(D.today||[]).map((s,i)=>ocard(_NUM[i],s.headline,s.why,_slotAction(s),s.source)).join("")||'<p class="narr">No promotions today.</p>'}`};'''
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
   <div style="margin-top:8px"><span class="chip" onclick="ask('the WEAK signals')"><span class="tag">SRC</span> harness_results · ${s.id||""}</span></div>`}};'''
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
FVIEWS.country={title:p=>`${p.name} <span class="where">· ${(COUNTRY[p.name]||{reg:'—'}).reg}</span>`,
  opts:p=>{const dd=DRAW[p.name];return dd?`<div class="opt-group"><div class="opt on">Markets</div><div class="opt" onclick="ask('downside if it keeps falling')">Tail</div></div>`:``;},
  render:p=>{const c=COUNTRY[p.name];const dd=DRAW[p.name];
   if(!c)return `<div class="eyebrow">Country letter · ${ISO[p.name]||""}</div><p class="narr">No sovereign/valuation fundamentals in the payload for <b>${p.name}</b> yet.${DISLO_READ[p.name]?" Dislocation: "+DISLO_READ[p.name]+".":""}${dd?" Trailing drawdown "+dd+"%.":""}</p>`;
   const th=c.thesis;
   return `<div class="eyebrow">Country letter · ${ISO[p.name]||""}</div>
   <p class="lede"><span class="dropcap">${p.name[0]}</span>${c.lede}</p>
   <div class="statline">
     <div class="stat"><div class="v">${_fmt(c.y10,2)}<span style="font-size:13px">%</span></div><div class="k">10Y</div></div>
     <div class="stat"><div class="v">${c.cds==null?"—":Math.round(c.cds)}<span style="font-size:13px">bp</span></div><div class="k">5Y CDS</div></div>
     <div class="stat"><div class="v ${c.eq>=0?'pos':'neg'}">${_sgn(c.eq,2)}<span style="font-size:13px">%</span></div><div class="k">ret · 1m</div></div>
     <div class="stat"><div class="v">${_sgn(c.s210,2)}</div><div class="k">2s10s</div></div></div>
   ${c.cape!=null?valBar("CAPE percentile",c.cape,c.cape<50?"cheap":"rich"):""}${c.erp!=null?valBar("ERP percentile",c.erp,c.erp<50?"cheap":"rich"):""}
   ${th?`<div style="margin-top:14px"><span class="chip" onclick="ask('mark the ${p.name} thesis')"><span class="tag">${th.paper?'PAPER':'LIVE'}</span> ${th.id} · ${(th.direction||'').toUpperCase()} ${p.name} · <b class="muted">p=${th.probability??'—'}</b></span></div>`:''}
   ${dd?`<div class="keyrow" onclick="ask('downside if it keeps falling')"><span class="sw" style="background:var(--oxblood)"></span>JST tail · ${dd}% trailing drawdown →</div>`:""}`}};'''
html = html.replace(old_country, new_country)

# ---- 6. gap-first map/feed/detail/routing ---------------------------------
html = html.replace('let MAPLAYER="dislocation";', 'let MAPLAYER=(GAP.status==="fresh"?"gap":"dislocation");')
html = html.replace(
    'function renderMapLayers(){$("#maplayers").innerHTML=["return","dislocation","signal"].map(l=>`<div class="opt ${MAPLAYER===l?\\\'on\\\':\\\'\\\'}" onclick="setLayer(\\\'${l}\\\')">${l[0].toUpperCase()+l.slice(1)}</div>`).join("")}',
    'function renderMapLayers(){const layers=(GAP.status==="fresh"?["gap","return","dislocation","signal"]:["return","dislocation","signal"]);$("#maplayers").innerHTML=layers.map(l=>`<div class="opt ${MAPLAYER===l?\\\'on\\\':\\\'\\\'}" onclick="setLayer(\\\'${l}\\\')">${l[0].toUpperCase()+l.slice(1)}</div>`).join("")}'
)
html = html.replace(
    '''function renderMapLayers(){$("#maplayers").innerHTML=["return","dislocation","signal"].map(l=>`<div class="opt ${MAPLAYER===l?'on':''}" onclick="setLayer('${l}')">${l[0].toUpperCase()+l.slice(1)}</div>`).join("")}''',
    '''function renderMapLayers(){const layers=(GAP.status==="fresh"?["gap","return","dislocation","signal"]:["return","dislocation","signal"]);$("#maplayers").innerHTML=layers.map(l=>`<div class="opt ${MAPLAYER===l?'on':''}" onclick="setLayer('${l}')">${l[0].toUpperCase()+l.slice(1)}</div>`).join("")}'''
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
  return `<div class="tile${SEL===n?' sel':''}${gt.gap_id?' ring':''}" style="background:${bg}" onclick="openCountry('${n}')" title="${title}"><span class="iso">${ISO[n]}</span>${dd}<span class="val">${val}</span></div>`;
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
   const un=g.unabsorbed_fraction==null?"—":Math.round(g.unabsorbed_fraction*100)+"%";
   const exp=g.expected_move==null?"—":(g.expected_move*100).toFixed(2)+"%";
   const real=g.realized_move==null?"—":(g.realized_move*100).toFixed(2)+"%";
   const adv=g.dollar_adv_21d==null?"—":"$"+Math.round(g.dollar_adv_21d/1e6).toLocaleString()+"M";
   return `<div class="eyebrow">Price-discovery gap · ${GAP.as_of||""} · ${g.epistemic_tag||"INFERENCE"}</div>
   <p class="lede"><span class="dropcap">${(g.entity||"G")[0]}</span>${g.mechanism_text||"World-state and price-state remain in tension."}</p>
   <div class="statline">
     <div class="stat"><div class="v">${g.tension_score_current??"—"}</div><div class="k">tension</div></div>
     <div class="stat"><div class="v">${un}</div><div class="k">unabsorbed</div></div>
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
    '/* LIVE: data generated by build_cockpit_data.py */',
)

OUT.write_text(html)
print(f"[OK] wrote {OUT}  ({len(html)//1024} KB)")
