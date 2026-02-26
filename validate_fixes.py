import json

with open('extracted_facts.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

total = sum(len(d['facts']) for d in data)
print(f"Total docs: {len(data)}")
print(f"Total facts: {total}")

# Check no empty facts arrays
empty = [d['source_url'].split('/')[-1] for d in data if len(d['facts']) == 0]
print(f"Empty docs: {empty if empty else 'NONE'}")

# Count by topic
from collections import Counter
topics = Counter(f['topic'] for d in data for f in d['facts'])
for t, c in sorted(topics.items()):
    print(f"  {t}: {c}")

# Check fetch_method on riskometer
for d in data:
    if 'risk-o-meter' in d['source_url']:
        print(f"\nAMFI riskometer fetch_method: {d.get('fetch_method', 'MISSING')}")
        print(f"  Facts count: {len(d['facts'])}")

# Check scheme_category exists
sc = [f for d in data for f in d['facts'] if f['topic'] == 'scheme_category']
print(f"\nscheme_category facts: {len(sc)}")
for f in sc:
    print(f"  {f['verbatim_snippet'][:60]}...")

# CAMS facts count
for d in data:
    if 'camsonline' in d['source_url']:
        print(f"\nCAMS facts: {len(d['facts'])}")
        for f in d['facts']:
            print(f"  - {f['topic']}: {f['fact'][:80]}...")
