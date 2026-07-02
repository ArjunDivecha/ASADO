# Morning Report — Triptych Ingestion Complete (2026-07-02)

**Request (overnight):** "Complete all parts of the triptych ingestion so that it's fully
functional by morning. All the data comes from T2 … rewire the data to pull from DuckDB —
one benefit is that we can now easily add all the other variables that ASADO has in DuckDB."

**Status: DONE.** Everything below is built, wired into the nightly loop, tested (20 new
tests + full 183-test cockpit/loop suite green), run end-to-end, and verified in the browser.

---

## What you wake up to

Open the cockpit — there is a new **"Triptych" desk tab** (next to Consensus / Fable's Desk):

- **The review queue**: 25 setups where a factor's *point-in-time* history is strong
  (|IC-t| ≥ 2, bucket-run R² ≥ 0.4, ≥ 60 observations) AND the country's current reading
  sits at a decile edge (D1–D2 or D9–D10). Top row tonight: **Taiwan / Copper z-score in
  decile 10** — 6M relative forward returns from that decile were negative in 24 of 24
  historical episodes (hit rate 0%, IC-t −3.5).
- Every t2-factor row carries a **⧉ deep link** that opens the exact same view in your
  visual Triptych tool (PIT thresholds pre-selected).
- Every **country letter** now has a "Conditional history · Triptych PIT priors" section:
  that country's 3 strongest priors.
- Chat understands it: type **"triptych priors"**, "the review queue", or "what does
  history say" in the cockpit ask box.

Everything is tagged **PRIOR** — PIT conditional history guides triage and horizon choice;
it is *not* evidence. The harness still owns validation.

## The one big architectural change

The old plan (worktree, never run) read Triptych's Excel scan export — which was
**full-sample only** (lookahead for predictive use). Instead of patching the external tool,
I **ported Triptych's analytics kernel into ASADO** (`scripts/loop/triptych_kernel.py`,
line-verified against the tool's `core.js`) and pointed it at **DuckDB directly**:

- **PIT mode is the default prior surface**: expanding-window deciles, 36-month warm-up,
  each observation bucketed only against history up to itself — exactly the tool's
  "point-in-time" thresholds mode. Canary-tested: appending future shocks cannot move a
  single past bucket (and the full-sample control test proves the modes actually differ).
- **Full-sample mode is still computed** (it matches your visual tool's default) but its
  prior confidence is **hard-zeroed** — descriptive only, it can never enter the queue.
- **The whole warehouse is now sweepable.** The scan covers all 52 t2_raw factors PLUS 28
  warehouse variables (EPU, GPR, BIS credit gap/property/REER, OECD CLI/BCI/CCI, VIX, broad
  USD, IMF inflation/rates/trade prices, debt structure, CDS, WIRP, ECFC CPI, passive-flow
  intensity …) declared in **`config/triptych_scan.yaml`** — add a line there and the
  nightly scan picks it up. 165,642 combo rows (81,582 PIT) in ~10 s on all cores.

## Parity validation (India / REER, the PRD's reference case)

PIT, history-z, 12M relative, all history — ASADO scan vs the live tool's reference:
current decile **1**, current-bucket n **20**, avg forward **+25.5%**, hit rate **100%**,
IC **−0.41**, D10−D1 spread **−27.3%**. All match the tool (IC reference −0.41; spread
−27.3% vs −27.2% shown in the tool — rounding). Full-sample cross-check also matches.

## Where everything lives

| Piece | Path |
|---|---|
| Kernel (PIT math, core.js parity) | `scripts/loop/triptych_kernel.py` |
| Nightly scan (step 29b of the loop) | `scripts/loop/build_triptych_scan.py` |
| Factor registry + queue gates | `config/triptych_scan.yaml` |
| URL builder (salvaged from worktree) | `scripts/triptych_tool_link.py` |
| Loop tables | `triptych_scan`, `triptych_review_queue`, view `triptych_priors` |
| Parquets (rebuild-proof) | `Data/loop/triptych_scan.parquet`, `Data/loop/triptych_review_queue.parquet` |
| Cockpit | Triptych desk tab + country-letter priors + chat intent |
| Fable | `triptych_priors` block in the nightly evidence packet (12 top rows, "triptych" is a citable surface) |
| MCP tools | `triptych_link`, `triptych_prior_snapshot(country)`, `triptych_queue` |
| Tests (20, all green) | `tests/loop/test_triptych.py` |
| Contracts | governance v1.3 (`build_triptych_scan` required step), schema v1.2 (both tables) |

## Worktree cleanup (as approved)

- `ASADO-Triptych/` worktree and the empty `ASADO_worktrees/` are **removed**.
- Salvaged first: `triptych_tool_link.py` + the workflow doc into the main repo;
  the old opportunity-scan script + full worktree patch archived in `docs/salvage/`
  (the Streamlit UI patch is obsolete — the cockpit replaced Streamlit).

## Epistemic contract (unchanged discipline)

1. PIT rows → **PRIOR** (confidence per PRD 7.3); full-sample rows → descriptive, conf = 0.
2. Forward-return variables (`1MRet` family) are refused as signals in the kernel itself.
3. The queue feeds **triage** (cockpit, Fable, MCP) — nothing becomes a trade or a verdict
   without `register_hypothesis` → `evaluate_signal` through the harness.
4. Custody: the Fable packet block carries no forward-return keys; the Discovery Lab
   (outcome-blind) is untouched.

## Follow-ups you may want

- **Register the strongest families in the harness** (e.g. Copper-z → Taiwan relative 6M;
  REER decile extremes) — deliberately NOT done overnight: hypothesis registration burns
  family trial counts, which felt like your call.
- Prune/extend the 28 warehouse factors in `config/triptych_scan.yaml` to taste.

## Artifacts

- Report: [docs/MORNING_REPORT_2026_07_02_TRIPTYCH.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/docs/MORNING_REPORT_2026_07_02_TRIPTYCH.md)
- Scan parquet: [Data/loop/triptych_scan.parquet](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/loop/triptych_scan.parquet)
- Review queue: [Data/loop/triptych_review_queue.parquet](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/loop/triptych_review_queue.parquet)
- Cockpit: [cos_mockups/cockpit_live.html](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/cos_mockups/cockpit_live.html)
