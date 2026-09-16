import json
from pathlib import Path

gold = json.loads(Path('data/answer_goldenset_multiturn.json').read_text(encoding='utf-8'))
targets = ['C-005', 'C-009', 'C-010', 'C-011', 'C-012', 'C-014', 'C-016', 'C-017', 'C-018', 'C-019', 'C-023', 'C-024', 'C-025', 'C-027', 'C-029', 'C-034']

for c in gold['conversations']:
    cid = c['conv_id']
    if cid in targets:
        q = next(t for t in c['turns'] if t['role'] == 'customer')
        a = next(t for t in c['turns'] if 'expect' in t)
        exp = a['expect']
        print(f"=== {cid} ({c['route']}) ===")
        print("질문:", q['text'])
        print("기대 Action:", exp.get('action'))
        print("기대 Tools:", exp.get('tools'))
        print("기대 Must:", exp.get('must'))
        print("기대 Forbid:", exp.get('forbid'))
        print("참조 답변:", exp.get('reference'))
        print()
