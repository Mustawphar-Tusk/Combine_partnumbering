import json

d = json.load(open(r'docs\evidence\F120\FYBROC_REV03_CONFIGURATION_STRUCTURE.json', encoding='utf-8'))
print('=== Authoritative Field Order (from Rev0.3 Constraints sheet) ===')
for i, row in enumerate(d['combination_matrix']['rows'], 1):
    print(f'  {i:>2}. {row["field"]}')
