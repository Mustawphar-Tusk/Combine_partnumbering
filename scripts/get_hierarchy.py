import json

d = json.load(open(r'docs/evidence/F120/FYBROC_REV03_CONFIGURATION_STRUCTURE.json', encoding='utf-8'))

print('=== HORIZONTAL QUESTION ORDER (authoritative engineering hierarchy) ===')
for q in d['todo']['horizontal_questions']:
    print(f'  {q["seq"]:>2}. {q["question"]:<35} -> {q["field_code"] or ""}')

print()
print('=== VERTICAL QUESTION ORDER ===')
for q in d['todo']['vertical_questions']:
    print(f'  {q["seq"]:>2}. {q["question"]:<35} -> {q["field_code"] or ""}')
