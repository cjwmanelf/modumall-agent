# -*- coding: utf-8 -*-
"""매뉴얼을 장 단위로 쪼개고, 라우트에 필요한 장만 골라 컨텍스트를 만든다.

전문을 넣지 않는 이유는 두 가지다. 입력이 길어 비용과 지연이 늘고, 관련 없는 정책이
오답을 유도한다(배송 문의에 반품 배송비가 섞여 들어가는 식).
"""
import re

from config import BASE

POLICY = BASE / "policy_modumall.md"   # 섹션 2에서 이미 받아 두었다


def split_sections(text):
    """'## ' 헤딩 단위로 매뉴얼을 쪼갠다. 키는 장 번호(문자열), 부록은 제외."""
    parts = re.split(r"^## ", text, flags=re.M)
    out = {"_header": parts[0].strip()}
    for p in parts[1:]:
        title = p.split("\n", 1)[0].strip()
        if title.startswith("부록"):        # 부록은 상담원용 요약·문구 모음
            continue
        m = re.match(r"(\d+)\.", title)
        key = m.group(1) if m else title
        out[key] = "## " + p.rstrip()
    return out


SECTION_MAP = {
    "ORDER_PLACE":   ["2"],          # 2장 주문·구매 문의
    "PRODUCT_INFO":  ["3"],          # 3장 상품 문의
    "SHIPPING":      ["4"],          # 4장 배송 문의
    "RETURN_REFUND": ["5", "6"],     # 5장 접수 + 6장 비용과 처리
    "OTHER":         [],
}


ALWAYS = ["이 매뉴얼을 쓰는 방법", "0", "1", "7", "8"]


def build_context(route, secs=None):
    """라우트에 필요한 매뉴얼 조각만 이어 붙여 프롬프트용 컨텍스트를 만든다."""
    secs = sections if secs is None else secs
    keys = [k for k in ALWAYS + SECTION_MAP.get(route, []) if k in secs]
    return "\n\n".join([secs["_header"]] + [secs[k] for k in keys])


FIXED_POLICY = {
    "base_shipping_fee": 2500,        # 4.1 기본 배송비
    "return_fee_full": 5000,          # 6.1 전체 반품(왕복)
    "return_fee_partial": 2500,       # 6.1 부분 반품(편도)
    "cutoff_hour": 11,                # 4.3 출고 마감
    "delivery_days_metro": [1, 2],    # 4.4 수도권
    "delivery_days_other": [3, 4],    # 4.4 수도권 외
    "delivery_days_std": [1, 3],      # 4.4 표준 안내
    "return_total_days": [3, 7],      # 6.2 전체 처리 기간
    "inspect_days": [2, 3],           # 6.2 입고 → 검품·승인
    "pickup_days": [1, 2],            # 6.2 접수 → 수거
    "designated_courier": "롯데택배",   # 5.3 지정 택배사
}


TOOL_NAMES = ["get_order_status", "get_product_detail", "get_product_options",
              "get_shipping_policy", "get_return_policy", "get_return_status",
              "get_restock_info", "escalate_to_agent"]


sections = split_sections((BASE / "policy_modumall.md").read_text(encoding="utf-8"))


def build_answer_prompt(question, route, tool_results=None):
    """답변 생성용 시스템 프롬프트를 조립한다."""
    import json
    from prompts import ANSWER_RULES
    ctx = build_context(route)
    tr = json.dumps(tool_results or {}, ensure_ascii=False, indent=1)
    return (f"{ANSWER_RULES}\n"
            f"===== 업무 매뉴얼 (라우트: {route}) =====\n{ctx}\n\n"
            f"===== 조회 결과 =====\n{tr}\n")
