import json
from pathlib import Path
from answer import answer_with_tools
from tools import search_product, PRODUCTS

gold = json.loads(Path('data/answer_goldenset_multiturn.json').read_text(encoding='utf-8'))
for cid in ['C-001', 'C-002', 'C-011', 'C-014', 'C-018', 'C-019', 'C-021', 'C-022', 'C-024', 'C-030']:
    c = next(x for x in gold['conversations'] if x['conv_id'] == cid)
    q = next(t for t in c['turns'] if t['role'] == 'customer')['text']
    ans, tools = answer_with_tools(q, c['route'])
    print(f'[{cid}] Q: {q}')
    print('Tools called:', list(tools.keys()))
    print('Ans:', ans[:100])
    print('-'*40)
