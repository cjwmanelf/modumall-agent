# -*- coding: utf-8 -*-
"""어드민 조회 도구. 매뉴얼의 [어드민 조회] 표시에서 도출한 것들이다.

고칠 때 주의할 점 두 가지.
- 선택 인자는 반드시 `Optional[...]` 로 적는다. 타입이 int 인데 기본값이 None 이면
  모델이 '모름'의 뜻으로 None 을 보냈을 때 스키마 검증에서 거부당한다.
- docstring 첫 줄이 모델이 읽는 도구 설명이다. 여기를 고치면 도구 선택이 달라진다.
"""
import json
import re
from typing import Optional

from config import BASE
from context import FIXED_POLICY

MOCK = json.loads((BASE / "mockdata_modumall.json").read_text(encoding="utf-8"))

def clean(obj):
    """$ 로 시작하는 내부 주석 키를 재귀적으로 제거한다."""
    if isinstance(obj, dict):
        return {k: clean(v) for k, v in obj.items() if not k.startswith("$")}
    if isinstance(obj, list):
        return [clean(v) for v in obj]
    return obj


PRODUCTS = {p["product_id"]: p for p in MOCK["products"]}


ORDERS = {o["order_id"]: o for o in MOCK["orders"]}


RETURNS = {r["return_id"]: r for r in MOCK["returns"]}


RETURNS_BY_ORDER = {r["order_id"]: r for r in MOCK["returns"]}


RESTOCK = {r["product_id"]: r for r in MOCK["restock"]}


CATEGORIES = MOCK["categories"]


def search_product(query: str) -> dict:
    """상품명 일부로 상품을 찾는다. 상품 ID를 모를 때 가장 먼저 부르는 도구다.

    후보를 점수와 함께 돌려준다.
    """
    def toks(s):
        return [t for t in re.split(r"[\s·()]+", s) if t]

    STOPWORDS = {"세트", "상품", "하나", "단품", "구매", "판매", "추천"}
    raw_qt = toks(query)
    qt = [t for t in raw_qt if t not in STOPWORDS] or raw_qt
    if not qt:
        return {"query": query, "candidates": []}

    q_flat = "".join(qt)
    hits = []
    for pid, p in PRODUCTS.items():
        name = p["name"]
        flat = name.replace(" ", "")
        nt = toks(name)
        
        score = 0.0
        # 1) 전체 구문 포함
        if q_flat and q_flat in flat:
            score += 3.0
        elif flat and flat in q_flat:
            score += 2.5

        # 2) 토큰 일치
        token_matches = sum(1 for t in qt if t in flat or any(t == x for x in nt))
        score += (token_matches / len(qt)) * 2.0

        # 3) 부분 토큰 매칭
        for t in qt:
            for x in nt:
                if x != t and (x in t or t in x):
                    score += 0.3

        if score > 0.5:
            hits.append({"product_id": pid, "name": name, "category": p["category"],
                         "price": p["price"], "score": round(score, 2)})

    hits.sort(key=lambda h: -h["score"])
    top = [h for h in hits if abs(h["score"] - hits[0]["score"]) < 1e-4] if hits else []
    resolved = top[0]["product_id"] if top else None
    is_ambiguous = len(top) > 1 and top[0]["category"] != top[1]["category"]

    return {"query": query, "candidates": hits[:5],
            "resolved_product_id": resolved,
            "ambiguous": is_ambiguous,
            "note": ("후보가 여러 개입니다. 어느 상품인지 고객에게 확인하십시오."
                     if is_ambiguous else None)}



def get_order_status(order_id: str) -> dict:
    """주문번호로 주문의 현재 진행 단계와 배송 정보를 조회한다."""
    o = ORDERS.get(order_id)
    if not o:
        return {"error": "주문을 찾을 수 없습니다", "order_id": order_id}
    return clean({k: o[k] for k in ["order_id", "status", "status_detail", "is_external_channel",
                                    "items", "order_amount", "shipping_fee", "address_region",
                                    "courier", "tracking_no", "invoice_printed",
                                    "expected_ship_date"] if k in o})


def get_product_detail(product_id: str) -> dict:
    """상품 ID로 구성·소재·원산지·재고·보증서 동봉 여부를 조회한다."""
    p = PRODUCTS.get(product_id)
    if not p:
        return {"error": "상품을 찾을 수 없습니다", "product_id": product_id}
    out = {k: p[k] for k in ["product_id", "name", "category", "price", "stock", "components",
                             "material", "origin", "has_quality_cert", "made_to_order",
                             "size_chart"] if k in p}
    out["category_label"] = CATEGORIES[p["category"]]["label"]
    return clean(out)


def get_product_options(product_id: str) -> dict:
    """상품 ID로 개별(단품) 구매 가능 여부와 판매 옵션을 조회한다."""
    p = PRODUCTS.get(product_id)
    if not p:
        return {"error": "상품을 찾을 수 없습니다", "product_id": product_id}
    return clean({k: p[k] for k in ["product_id", "name", "is_set", "components", "options",
                                    "individual_purchase_allowed", "individual_purchase_note",
                                    "made_to_order"] if k in p})


CAPITAL = ("서울", "경기", "인천", "수도권")


def normalize_region(region):
    """고객이 말한 지역명을 목 데이터의 지역 키로 옮긴다."""
    if not region:
        return None
    if any(k in region for k in ("제주", "도서", "산간", "울릉")):
        return "제주도서산간"
    if any(k in region for k in CAPITAL):
        return "수도권"
    return "수도권외"


def region_info(region):
    """지역별 당일배송 제공 여부와 도서산간 추가 배송비를 돌려준다."""
    key = normalize_region(region)
    sd = clean(MOCK["same_day_delivery"].get(key, {}))
    return {"region_input": region, "region": key,
            "same_day_available": sd.get("available", False),
            "same_day_fee": sd.get("fee"),
            "extra_shipping_fee": sd.get("extra_fee"),     # 도서산간 추가 배송비
            "region_note": sd.get("note")}


def get_shipping_policy(product_id: Optional[str] = None, category: Optional[str] = None,
                        order_amount: Optional[int] = None,
                        region: Optional[str] = None) -> dict:
    """무료배송 기준액과 배송비를 조회한다. 금액을 주면 부족액까지 계산한다.

    상품 ID 로도, 카테고리로도 조회할 수 있다. 지역만 궁금한 문의(도서산간 추가비 등)는
    상품 없이 region 만 줘도 된다. region 을 주면 당일배송 제공 여부도 함께 돌려준다.
    """
    p = PRODUCTS.get(product_id) if product_id else None
    if product_id and not p:
        return {"error": "상품을 찾을 수 없습니다", "product_id": product_id}
    cat_key = p["category"] if p else category
    if cat_key is None:                      # 상품도 카테고리도 없다 — 지역 정보만 돌려준다
        out = {"base_shipping_fee": FIXED_POLICY["base_shipping_fee"],
               "note": "무료배송 기준은 카테고리마다 다릅니다. 상품 또는 카테고리를 지정해 주세요."}
        if region:
            out.update(region_info(region))
        return clean(out)
    if cat_key not in CATEGORIES:
        return {"error": "카테고리를 찾을 수 없습니다", "category": cat_key}
    cat = CATEGORIES[cat_key]
    base = FIXED_POLICY["base_shipping_fee"]
    th = cat["free_shipping_threshold"]

    out = {"product_id": product_id, "name": p["name"] if p else None, "category": cat_key,
           "category_label": cat["label"], "price": p["price"] if p else None,
           "base_shipping_fee": base, "free_shipping_threshold": th}
    if th is None:
        out["free_shipping_available"] = False
        out["note"] = cat.get("free_shipping_note", "무료배송 대상이 아닙니다.")
    else:
        out["free_shipping_available"] = True

    if order_amount is not None:
        out["order_amount"] = order_amount
        if th is None:
            out["free_shipping_applied"] = False
            out["shipping_fee"] = base
        elif order_amount >= th:
            out["free_shipping_applied"] = True
            out["shipping_fee"] = 0
        else:
            out["free_shipping_applied"] = False
            out["shipping_fee"] = base
            out["shortfall"] = th - order_amount        # 부족액은 코드가 계산한다

    if region:
        out.update(region_info(region))
    return clean(out)


def get_return_policy(product_id: Optional[str] = None, order_id: Optional[str] = None) -> dict:
    """상품 또는 주문의 반품 가능 기간과 조건을 조회한다."""
    if order_id:
        o = ORDERS.get(order_id)
        if not o:
            return {"error": "주문을 찾을 수 없습니다", "order_id": order_id}
        product_id = o["items"][0]["product_id"]
    p = PRODUCTS.get(product_id)
    if not p:
        return {"error": "상품을 찾을 수 없습니다", "product_id": product_id}
    cat = CATEGORIES[p["category"]]
    return clean({
        "product_id": product_id, "name": p["name"], "category": p["category"],
        "category_label": cat["label"],
        "return_window_days": cat["return_window_days"],
        "return_window_basis": cat["return_window_basis"],
        "requires_unopened": cat["requires_unopened"],
        "made_to_order": p.get("made_to_order", False),
        "return_blocked": bool(p.get("made_to_order")),
        "return_blocked_reason": "주문 제작 상품은 교환·반품이 불가합니다." if p.get("made_to_order") else None,
    })


def get_return_status(order_id: Optional[str] = None, return_id: Optional[str] = None) -> dict:
    """반품·교환의 현재 처리 단계를 조회한다. 검품 전에는 귀책이 확정되지 않는다."""
    r = RETURNS.get(return_id) if return_id else RETURNS_BY_ORDER.get(order_id)
    if not r:
        return {"error": "반품 접수 내역을 찾을 수 없습니다",
                "order_id": order_id, "return_id": return_id}
    return clean(r)


def get_restock_info(product_id: str) -> dict:
    """품절 상품의 재입고 확정 여부와 예정일을 조회한다."""
    r = RESTOCK.get(product_id)
    if not r:
        p = PRODUCTS.get(product_id)
        if p and p.get("stock"):
            return {"product_id": product_id, "is_soldout": False,
                    "stock": p["stock"], "note": "재고가 있어 재입고 대기 상품이 아닙니다."}
        return {"error": "재입고 정보를 찾을 수 없습니다", "product_id": product_id}
    return clean(r)


def escalate_to_agent(reason: str, context: Optional[dict] = None) -> dict:
    """상담원에게 이관한다. 매뉴얼 7.2의 이관 기준에 해당할 때 호출한다."""
    return {"escalated": True, "reason": reason, "context": context or {},
            "message": "정확한 확인을 위해 상담원에게 연결해 드리겠습니다."}


TOOLS = {f.__name__: f for f in [search_product,
                                 get_order_status, get_product_detail, get_product_options,
                                 get_shipping_policy, get_return_policy, get_return_status,
                                 get_restock_info, escalate_to_agent]}


PRODUCT_ALIAS = {p["name"]: pid for pid, p in PRODUCTS.items()}


def find_product_id(text):
    """발화에서 상품 ID 또는 카탈로그 상품명을 찾는다. 없으면 None."""
    m = re.search(r"P\d{4}", text)
    if m:
        return m.group(0)
    for name, pid in PRODUCT_ALIAS.items():
        if name.replace(" ", "") in text.replace(" ", ""):
            return pid
    return None
