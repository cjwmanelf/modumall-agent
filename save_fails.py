import json
from pathlib import Path

gold = json.loads(Path('data/answer_goldenset_multiturn.json').read_text(encoding='utf-8'))
targets = ['C-005', 'C-009', 'C-010', 'C-011', 'C-012', 'C-014', 'C-016', 'C-017', 'C-018', 'C-019', 'C-023', 'C-024', 'C-025', 'C-027', 'C-029', 'C-034']
res = []
for c in gold['conversations']:
    cid = c['conv_id']
    if cid in targets:
        q = next(t for t in c['turns'] if t['role'] == 'customer')
        a = next(t for t in c['turns'] if 'expect' in t)
        exp = a['expect']
        res.append({
            'cid': cid,
            'route': c['route'],
            'q': q['text'],
            'action': exp.get('action'),
            'tools': exp.get('tools'),
            'must': exp.get('must'),
            'forbid': exp.get('forbid'),
            'ref': exp.get('reference'),
            'rubric': exp.get('rubric')
        })
Path('fails_detail.json').write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
print('saved fails_detail.json')
