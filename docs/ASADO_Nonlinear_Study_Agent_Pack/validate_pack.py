#!/usr/bin/env python3
"""Validate the PRD handoff package, not ASADO data or experiment results.

Uses only the Python standard library. --require-registered intentionally fails
for the supplied draft, whose source and governance bindings remain unresolved.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


def load_json(path: Path) -> dict:
    with path.open(encoding='utf-8') as handle:
        obj = json.load(handle)
    if not isinstance(obj, dict):
        raise ValueError(f'{path.name} must contain a JSON object')
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--require-registered', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    errors: list[str] = []
    checks: list[str] = []
    try:
        cfg = load_json(root/'config/study.template.json')
        backlog = load_json(root/'implementation_backlog.json')
        catalogue = load_json(root/'acceptance_tests.json')
        load_json(root/'config/schemas/study.schema.json')
        load_json(root/'config/schemas/data_contracts.json')
        checks.append('All supplied JSON files parse.')
        md = (root/'ASADO_Nonlinear_Study_PRD.md').read_text(encoding='utf-8')
        page = (root/'ASADO_Nonlinear_Study_PRD.html').read_text(encoding='utf-8')
        manifest = (root/'config/feature_manifest.template.yaml').read_text(encoding='utf-8')
        (root/'AGENT_START_HERE.md').read_text(encoding='utf-8')
        features = re.findall(r'^\s*- id: (P\d{2})\s*$', manifest, flags=re.MULTILINE)
        expected_features = [f'P{i:02d}' for i in range(1, 25)]
        if features != expected_features or cfg['features']['primitive_ids'] != expected_features:
            errors.append('The two feature manifests must name P01-P24 exactly once in order.')
        else:
            checks.append('JSON and YAML declare the same 24 primitive IDs.')
        model_ids = set(cfg['models'])
        expected_models = {'B0','L_X','L_S','L_star','A_S','Q_S','N_S','N_X'}
        if model_ids != expected_models:
            errors.append('Expected eight forecast streams.')
        if sum(bool(m.get('tuned')) for m in cfg['models'].values()) != 6:
            errors.append('Expected six independently tuned learners.')
        if len(cfg['ridge_grid']['lambda']) != 12:
            errors.append('Expected 12 ridge penalties.')
        grid_size = 1
        for key in ['max_iter','leaf_fraction','l2_regularization']:
            grid_size *= len(cfg['tree_grid'][key])
        if grid_size != 12:
            errors.append('Expected 12 configurations per tree learner.')
        state = cfg['features']['state_weights']
        if len(state) != 16 or not all(set(weights) <= set(expected_features) for weights in state.values()):
            errors.append('State map must have 16 outputs referencing only P01-P24.')
        checks.append('Model inventory and bounded grid dimensions checked.')
        if cfg['target']['primary_horizon_local_sessions'] != 20:
            errors.append('Primary horizon must be 20 local sessions.')
        if cfg['tree_grid']['early_stopping'] is not False:
            errors.append('Automatic early stopping must be disabled.')
        for key in ['allow_live_orders','allow_source_database_writes','allow_automatic_alternative_primary']:
            if cfg['execution_permissions'][key] is not False:
                errors.append(f'{key} must remain false in this package.')
        if cfg['portfolio']['cost_or_turnover_kill_gate'] is not False:
            errors.append('Cost and turnover cannot be kill gates.')
        if cfg['prospective']['enabled'] or cfg['neural_extension']['enabled']:
            errors.append('Optional extensions must be disabled in the template.')
        checks.append('Core horizon and safety/scientific permission defaults checked.')
        tests = catalogue['tests']
        test_ids = {t['id'] for t in tests}
        if len(tests) != 60 or len(test_ids) != 60:
            errors.append('Expected 60 unique acceptance tests.')
        tasks = backlog['tasks']
        ids = {t['id'] for t in tasks}
        if len(tasks) != 56 or len(ids) != 56:
            errors.append('Expected 56 unique implementation tasks.')
        covered_tests: set[str] = set()
        for task in tasks:
            if not set(task['depends_on']) <= ids:
                errors.append(f"Unknown task dependency in {task['id']}")
            if not set(task['acceptance_test_ids']) <= test_ids:
                errors.append(f"Unknown acceptance test in {task['id']}")
            covered_tests.update(task['acceptance_test_ids'])
        if covered_tests != test_ids:
            errors.append('Every acceptance test must map to at least one backlog task: '+','.join(sorted(test_ids-covered_tests)))
        remaining = {t['id']: set(t['depends_on']) for t in tasks}
        done: set[str] = set()
        while remaining:
            ready = {key for key, deps in remaining.items() if deps <= done}
            if not ready:
                errors.append('Task dependency graph contains a cycle.')
                break
            done.update(ready)
            for key in ready:
                del remaining[key]
        checks.append('Task/test references, coverage, uniqueness and dependency graph checked.')
        for i in range(14):
            if f'P{i:02d}' not in md:
                errors.append(f'Missing phase P{i:02d} in PRD.')
        html_anchors = set(re.findall(r'id="(section-\d+)"', page))
        html_links = set(re.findall(r'href="#(section-\d+)"', page))
        if html_links != html_anchors:
            errors.append('HTML navigation has missing or unlinked section anchors.')
        checks.append('All 14 phases and HTML section navigation checked.')
        checksum_path = root/'MANIFEST.sha256'
        if checksum_path.exists():
            for line in checksum_path.read_text(encoding='utf-8').splitlines():
                expected_hash, relative = line.split('  ', 1)
                target = (root/relative).resolve()
                if not target.is_relative_to(root):
                    errors.append(f'Unsafe checksum path: {relative}')
                    continue
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
                if actual != expected_hash:
                    errors.append(f'Checksum mismatch: {relative}')
            checks.append('Delivered file checksums verified.')
        if args.require_registered:
            if cfg['status'] != 'REGISTERED':
                errors.append('Supplied configuration is DRAFT, not REGISTERED.')
            unresolved = [key for key,value in cfg['bindings'].items() if value is None or value is False or value == '']
            if unresolved:
                errors.append('Unresolved local bindings: '+', '.join(unresolved))
            if cfg['execution_permissions']['allow_real_outer_evaluation'] is not True:
                errors.append('Real outer evaluation is not authorized in the draft.')
            if 'binding_status: UNBOUND' in manifest:
                errors.append('Source selectors are deliberately UNBOUND pending local audit.')
        result = {'status':'FAIL' if errors else 'PASS','scope':'handoff_package_only',
                  'research_experiment_executed':False,'ASADO_data_validated':False,
                  'checks':checks,'errors':errors}
        print(json.dumps(result, indent=2))
        return 1 if errors else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status':'FAIL','scope':'handoff_package_only','error':str(exc)}, indent=2))
        return 2


if __name__ == '__main__':
    sys.exit(main())
