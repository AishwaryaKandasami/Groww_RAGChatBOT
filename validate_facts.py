import json

with open('extracted_facts.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'Total documents: {len(data)}')
total_facts = sum(len(d['facts']) for d in data)
print(f'Total facts: {total_facts}')

# Coverage matrix
schemes = ['SBI Large Cap', 'SBI Flexi Cap', 'SBI ELSS', 'General']
topics = ['expense_ratio', 'exit_load', 'min_sip', 'lock_in', 'riskometer', 'benchmark', 'statement_download']

print('\n=== COVERAGE MATRIX ===')
for s in schemes:
    facts_for_scheme = [f for d in data if d['scheme'] == s for f in d['facts']]
    covered = set(f['topic'] for f in facts_for_scheme)
    missing = [t for t in topics if t not in covered]
    print(f'{s}: {sorted(covered)} ({len(facts_for_scheme)} facts)')
    if missing:
        applicable = missing
        if s != 'SBI ELSS':
            applicable = [m for m in missing if m != 'lock_in']
        if s == 'General':
            applicable = [m for m in missing if m not in ['min_sip', 'benchmark']]
        if applicable:
            print(f'  POTENTIALLY MISSING: {applicable}')

# Snippet length check
print('\n=== SNIPPET LENGTH CHECK ===')
violations = 0
for d in data:
    for f in d['facts']:
        words = len(f['verbatim_snippet'].split())
        if words > 30:
            violations += 1
            print(f'  OVER 30 WORDS ({words}): {d["scheme"]} / {f["topic"]}')
print(f'Violations: {violations}')

print('\n=== VALID JSON: YES ===')
print(f'\nSummary: {len(data)} docs, {total_facts} facts, {violations} snippet violations')
