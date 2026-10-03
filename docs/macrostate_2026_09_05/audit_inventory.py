"""Read-only metadata/coverage audit; each production connection closes after one aggregate.
No predictive evaluation. No production output. Run from ASADO root.
"""
import duckdb,json,csv,time,pathlib,datetime
ROOT=pathlib.Path.cwd(); OUT=ROOT/'docs/macrostate_2026_09_05'; OUT.mkdir(exist_ok=True)
rows=[];timings=[]
for db,path in [('warehouse','Data/asado.duckdb'),('loop','Data/loop/asado_loop.duckdb')]:
 schema=json.loads((OUT/f'{db}_schema.json').read_text())
 for table,cols in schema.items():
  if not {'variable','value','country'}.issubset(cols):continue
  date='date' if 'date' in cols else 'vintage_date' if 'vintage_date' in cols else None
  if date is None:continue
  source='source' if 'source' in cols else "'"+table+"'"
  query=f'''select variable,{source} as source,count(*) row_count,count(value) nonnull,
 count(*) filter(where value is not null and isfinite(value)) finite,
 count(distinct country) countries,min({date}) first_date,max({date}) last_date,
 count(distinct {date}) dates,string_agg(distinct country,'|' order by country) country_list,
 count(distinct (date_trunc('month',{date}),country)) filter(where value is not null and isfinite(value) and {date}>='2000-02-01' and {date}<'2025-10-01') grid_cells_200002_202509
 from "{table}" group by variable,{source}'''
  start=time.monotonic();con=duckdb.connect(str(ROOT/path),read_only=True)
  try:
   cur=con.execute(query); keys=[x[0] for x in cur.description]; result=[dict(zip(keys,r)) for r in cur.fetchall()]
  finally:con.close()
  secs=time.monotonic()-start;timings.append({'db':db,'table':table,'seconds':secs})
  for r in result:rows.append({'db':db,'table':table,**r})
  print(db,table,len(result),round(secs,3),flush=True)
with (OUT/'universe_inventory.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
(OUT/'query_timings.json').write_text(json.dumps(timings,indent=2))
print('TOTAL',len(rows))
