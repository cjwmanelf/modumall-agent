from tools import search_product, PRODUCTS
for q in ['가죽 벨트', '요일팬티', '레깅스', '스니커즈', '가죽 자켓', '브라·팬티 세트']:
    res = search_product(q)
    print(q, '-> resolved:', res.get('resolved_product_id'), 'ambiguous:', res.get('ambiguous'))
    for c in res['candidates']:
        print('  ', c['product_id'], c['name'], c['score'])
