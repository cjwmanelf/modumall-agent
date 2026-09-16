# -*- coding: utf-8 -*-
"""여러 모듈이 함께 쓰는 잡동사니."""
from concurrent.futures import ThreadPoolExecutor

from config import WORKERS

LABELS4 = ["ORDER_PLACE", "PRODUCT_INFO", "SHIPPING", "RETURN_REFUND"]


def pmap(fn, items, workers=12):
    """여러 건을 동시에 호출한다. 결과 순서는 입력 순서와 같다.

    LLM 호출은 대부분 응답을 기다리는 시간이라 동시에 보내면 거의 그 배수만큼 빨라진다.
    workers 를 너무 올리면 요청 한도(rate limit)에 걸린다. 12 정도가 무난하다.
    """
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))


def show_graph(compiled):
    """그래프 구조를 mermaid 로 출력한다."""
    print(compiled.get_graph().draw_mermaid())
