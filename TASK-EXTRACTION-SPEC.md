# TASK-EXTRACTION-SPEC

**Purpose:** Extract completed research tasks from ASADO session logs and draft programmatic success checks for the strongest 20. Output becomes the seed dataset for a fine-tuned + RL-trained ASADO research agent.

**Author:** Arjun Divecha (spec drafted 2026-08-28)
**Executor:** Claude Code, run from `/AAA Backup/A Working/ASADO/`

---

## Prime directive

You are extracting, not inventing. Every task you record must correspond to something that actually happened in a log. Every acceptance criterion you record must either be stated in the log, or be explicitly flagged as your inference.

If you cannot tell whether Arjun accepted a result, say so. Do not guess. A short list of well-grounded tasks is worth more than twenty confident fabrications.

---

## Inputs

Read these, in this order:

1. `llmchat.md` (~92KB) — main ASADO session log, primary source
2. `llmchat-session-2026-08-08-boundaries-tsm.md` — Boundaries-of-TSMOM session
3. `CLAUDE.md` — agent contract; tells you what conventions were already in force
4. `AGENTS.md` (~43KB) — extended agent instructions
5. `DATA_DICTIONARY.md` and `ASADO_DATABASE_MAP.md` — schema ground truth for validating column and table references
6. `ASADO_DATA_AUDIT.md` and `ASADO_LEAKAGE_AUDIT.md` — existing quality and leakage checks; reuse these rather than reinventing them
7. `.asado_findings.json` — structured record of prior findings; cross-reference against tasks you extract

Do not read the `venv/`, `build/`, `__pycache__/`, or `.git/` directories.

---

## PASS 1 — Extraction (no judgement)

Walk the session logs and identify every **completed research task**. A completed research task has all four of:

- a question or instruction from Arjun
- work performed in response (a query, a script, an analysis)
- a result returned
- some signal of what happened next

Record each one as a YAML block with these fields:

```yaml
- id: T001
  source_file: llmchat.md
  source_location: "<line range or distinctive quoted anchor>"
  date: <if determinable, else null>
  request: "<what Arjun asked, in his words where possible>"
  work_performed: "<what was actually run — query, script, method>"
  artifacts: "<tables touched, files written, columns produced>"
  result: "<what came back — numbers, panels, findings>"
  disposition: accepted | rejected | revised | unclear
  disposition_evidence: "<the words in the log that show this, verbatim>"
  arjun_stated_criteria: "<any explicit standard he named — verbatim, else null>"
```

Rules for Pass 1:

- `disposition` must be supported by `disposition_evidence`. If you cannot quote evidence, the disposition is `unclear`.
- Silence is not acceptance. If Arjun moved on without comment, that is `unclear`, not `accepted`.
- `arjun_stated_criteria` is verbatim only. Do not paraphrase, do not generalise, do not fill it from your own knowledge of good practice.
- Include rejected tasks. Failure cases are as valuable as successes for reward design.
- Do not deduplicate aggressively. Near-identical tasks that were run twice with different parameters are two tasks.

Write Pass 1 output to `TASK-EXTRACTION-PASS1.md`. Include a count and a short note on coverage — which parts of the logs were dense with tasks and which were not.

---

## PASS 2 — Draft checks (judgement, explicitly labelled)

Select the 20 strongest tasks from Pass 1. Strength means, in priority order:

1. `disposition` is `accepted` or `rejected` with clear evidence
2. the result is mechanically verifiable — a number, a panel shape, a pass/fail
3. `arjun_stated_criteria` is non-null
4. the task is representative of work that recurs, not a one-off

For each selected task, draft a check specification:

```yaml
- id: T001
  task_summary: "<one line>"
  check_layers:
    execution:
      description: "<does the query or script run without error>"
      basis: stated | inferred
    schema:
      description: "<expected columns, dtypes, row count, date range, null policy>"
      basis: stated | inferred
    statistical:
      description: "<the actual research gate — IC threshold, significance, sign>"
      basis: stated | inferred
    robustness:
      description: "<overfitting / stability check where applicable>"
      basis: stated | inferred
  inference_flags:
    - "<every place you supplied a criterion Arjun did not state, and what you assumed>"
  open_questions:
    - "<what Arjun must decide before this check can be written as code>"
```

Rules for Pass 2:

- `basis: stated` requires a verbatim quote in `arjun_stated_criteria` from Pass 1. Everything else is `inferred`.
- **Every `inferred` entry must also appear in `inference_flags`.** This is the most important rule in the spec. The value of this document is knowing exactly where the machine guessed.
- Prefer thresholds that already exist in `ASADO_DATA_AUDIT.md` or `ASADO_LEAKAGE_AUDIT.md` over inventing new ones. Cite which file and section.
- Do not write executable code. This pass produces specifications only.
- If a task cannot be checked mechanically, say so and explain what would be needed. Do not force it.

Write Pass 2 output to `TASK-EXTRACTION-PASS2.md`.

---

## Deliverables

Three files, all in `/AAA Backup/A Working/ASADO/`:

1. `TASK-EXTRACTION-PASS1.md` — full extraction
2. `TASK-EXTRACTION-PASS2.md` — 20 check specifications
3. `TASK-EXTRACTION-REVIEW.md` — a review queue for Arjun: every `inference_flag` and `open_question` from Pass 2, consolidated into a single ordered list, most consequential first

The review file is the actual product. Pass 1 and 2 are working papers. What matters is a short, ordered list of decisions only Arjun can make.

---

## Explicit non-goals

- Do not write the fine-tuning dataset. That comes after review.
- Do not write reward functions. Same reason.
- Do not propose new research ideas. Extract what exists.
- Do not run any query against DuckDB or Neo4j. This is a documentation pass.
- Do not modify any existing file in the ASADO folder.

---

## Failure modes to avoid

**Confabulating acceptance.** The strongest temptation is to read approval into silence. Resist it. An honest pile of `unclear` dispositions is a useful signal about the logs.

**Smuggling in standard practice.** You know what good quant hygiene looks like. That knowledge belongs in `inference_flags`, not in `basis: stated`.

**Over-selecting the easy tasks.** The twenty strongest should not all be schema validations because those are simplest to check. Aim for spread across query construction, panel building, statistical testing, and backtest evaluation.

**Producing volume instead of clarity.** If the honest answer is that only nine tasks meet the bar, deliver nine and say why.
