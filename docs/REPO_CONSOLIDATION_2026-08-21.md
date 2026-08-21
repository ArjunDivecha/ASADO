# Repo consolidation — 2026-08-21

The ASADO repo was consolidated from **5 worktrees and 11 local branches** to **one
worktree and one branch (`main`)**. Nothing was lost; everything that was not merged is
reachable from an `archive/*` tag.

## What `main` is now

`main` was a direct ancestor of `Complexity`, so this was a **fast-forward** — no merge, no
conflicts, no history rewrite. `main` now carries all 44 commits that were on `Complexity`,
and the production checkout sits on `main`. Switching it changed **zero files on disk**, so
the launchd jobs were never at risk.

`Complexity` still exists, pointing at the same commit, purely so a concurrent session
working on it was not broken mid-task. It can be deleted once that session is closed:
`git branch -d Complexity`.

## Archive tags — what is in each, and why it was not merged

| tag | contents | why not merged |
|---|---|---|
| `archive/gmd-ingest` | GMD annual ingest WIP, full worktree snapshot. The standalone collector **was** merged; this also holds unreviewed pipeline wiring: `setup_duckdb.py` +146, `monthly_update.py` +17, `build_schema_registry.py` +14 | unreviewed WIP edits to production pipeline scripts, ~7 weeks behind main |
| `archive/neural-regime-model` | pre-registered hypothesis + Phase 0 pooled HGB baseline → **DEAD verdict**, 1,202 lines | research record; the verdict is the product, the code is not live |
| `archive/regime-ew-nightwatch` | `regime_ew/` per-country regime early-warning package (PRD) + `R3_Recession` rule fix, 1,998 lines | unfinished PRD |
| `archive/devin-source-alignment` | cross-source alignment check | **superseded** — main's `scripts/qa/check_source_alignment.py` is a later, larger version |
| `archive/codex-triptych-popup-row` | Triptych run-popup fix | **already on main** via another route (`tripOpen`/`tripClose` are in `make_live_cockpit.py`); the cherry-pick was empty |
| `archive/openwiki-bot-main` | `origin/main` tip: 7 automated OpenWiki doc commits + the commit that removed the OpenWiki CI workflow | bot-generated docs |
| `discarded/main-autocheckpoints-20260821` | two auto-checkpoints that landed on `main` after an unintended branch switch | incoherent hybrid state; see `docs/USER_FIX_LIST.md` |

Retrieve anything with `git checkout <tag> -- <path>` or `git log <tag>`.

## What was merged during the cleanup

`scripts/collect_gmd_annual.py` (21 KB) and `docs/GMD_INGEST_REVIEW_2026_07_03.md` —
they were **untracked in a worktree, present in no branch and no commit**, and would have
been destroyed by removing it. Rescued in `d509eac`, cherry-picked to main.

## How "nothing was lost" was established

Not by inspection. For every modified and untracked file in all four worktrees, the file's
content was hashed with `git hash-object` and looked up in the object store. Only files whose
exact content existed **nowhere in git** were treated as unique — that found 5 files in
`ASADO-gmd-ingest` (~188 KB) and **zero** in the other three worktrees, which were therefore
safe to delete outright. Their apparent "uncommitted changes" were stale drift: current file
content sitting on an old branch tip.

## Not done, deliberately

**Nothing was pushed.** `origin/main` is still at `cccd553` and has genuinely diverged — it
holds 7 OpenWiki bot commits local main never had. A future push would need `--force`, and
`.github/workflows/openwiki-update.yml` should be deleted first, or the push resurrects the
bot that `cccd553` deliberately removed. Three stale remote branches also remain
(`codex/triptych-popup-row`, `devin/…`, `claude/nightwatch-…`).
