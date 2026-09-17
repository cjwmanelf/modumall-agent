# -*- coding: utf-8 -*-
"""의도 분류 라우터. State 하나와 노드 둘로 된 그래프다.

classify 는 모델이 하는 일(분류), gate 는 정책이 정하는 일(처리/이관/범위밖)이다.
둘을 나눠 둔 덕에 임계값만 바꿀 때 모델을 다시 부르지 않아도 된다.

분류 노드를 갈아 끼우려면 같은 이름의 함수를 다시 정의하고 build() 를 부르면 된다.
"""
import re
from typing import Literal, Optional, TypedDict

from langchain.chat_models import init_chat_model
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from config import CONF_THRESHOLD, MODEL, create_chat_model
from prompts import ROUTE_GUIDE

class RouterState(TypedDict, total=False):
    """그래프를 통과하며 채워지는 값들. 노드는 자기가 바꾼 키만 돌려준다."""

    question: str          # 입력 — 고객 문의 한 문장
    route: str             # ① 분류 노드가 채운다
    confidence: float      # ① 분류 노드가 채운다
    reason: str            # ① 분류 노드가 채운다
    action: str            # ② 판정 노드가 채운다 — HANDLE / ESCALATE / OUT_OF_SCOPE
    message: Optional[str]  # ② 판정 노드가 채운다 — 고객에게 바로 나갈 문구


RULES = [
    (r"환불|반품|교환|취소|반송|수거|검품", "RETURN_REFUND"),
    (r"배송비|택배비|무료\s?배송|배송|택배|출고|도착|언제\s?(오|와)|어디쯤", "SHIPPING"),
    (r"주문할|구매할게|살게요|사고\s?싶|결제|주문\s?가능|구매\s?가능|낱개|따로|단품", "ORDER_PLACE"),
    (r"구성|포함|소재|재질|사이즈|치수|재고|정품|색상|품질|몇\s?(장|개)", "PRODUCT_INFO"),
    (r"매장|오프라인|지점|영업\s?시간|주차", "OTHER"),
]


CONF_THRESHOLD = 0.5


def classify(state: RouterState) -> RouterState:
    """노드 ① 분류 — 키워드 규칙 버전. 섹션 6에서 LLM 버전으로 갈아 끼운다."""
    q = state["question"]
    for pattern, route in RULES:
        if re.search(pattern, q):
            return {"route": route, "confidence": 0.8, "reason": "키워드 규칙 매치"}
    return {"route": "OTHER", "confidence": 0.3, "reason": "매치되는 규칙 없음"}


def gate(state: RouterState) -> RouterState:
    """노드 ② 판정 — 확신도와 응대 범위를 보고 처리/이관/범위밖을 정한다."""
    if state["confidence"] < CONF_THRESHOLD:
        return {"action": "ESCALATE",
                "message": "정확한 확인을 위해 상담원에게 연결해 드리겠습니다."}
    if state["route"] == "OTHER":
        return {"action": "OUT_OF_SCOPE",
                "message": "해당 내용은 주문하신 사이트의 고객센터를 통해 문의해 주셔야 확인이 가능합니다."}
    return {"action": "HANDLE", "message": None}


def build(node=None):
    """노드를 **이름으로** 찾아 그래프를 만든다.

    globals()[...] 로 찾기 때문에, 같은 이름의 함수를 다시 정의한 뒤 build() 를 한 번 더
    부르면 그 노드만 갈아 끼워진다. 그래프 정의는 오늘 하루 이 셀 하나뿐이다.
    (비교할 때는 node= 로 분류 노드를 직접 건네줄 수도 있다.)
    """
    g = StateGraph(RouterState)
    g.add_node("classify", node or globals()["classify"])
    g.add_node("gate", globals()["gate"])
    g.add_edge(START, "classify")
    g.add_edge("classify", "gate")
    g.add_edge("gate", END)
    return g.compile()


class RouteDecision(BaseModel):
    """고객 문의 한 건에 대한 라우팅 판단 결과."""

    route: Literal["ORDER_PLACE", "PRODUCT_INFO", "SHIPPING",
                   "RETURN_REFUND", "OTHER"] = Field(
        description="문의를 배정할 라우트. 5개 값 중 하나만 사용한다.")
    confidence: float = Field(
        ge=0.0, le=1.0,
        description=(
            "판단의 확신도 점수 (0.0 ~ 1.0):\n"
            "- 0.95 ~ 1.00: 고객의 최종 목적(배송비/출고 확인, 반품/환불, 구매/주문 등)이 명확하고 의심의 여지가 없는 경우\n"
            "- 0.75 ~ 0.90: 복합 질문이나 수식어가 많으나 주요 의도가 한쪽 분과로 분명히 귀결되는 경우\n"
            "- 0.50 미만: 두 분과 사이에서 완전히 모호하여 상담원 이관이 불가피한 경우"
        ))
    reason: str = Field(
        description="그 라우트로 판단한 근거를 한 문장으로. 고객이 원하는 결과를 기준으로 쓴다.")


_router_chain = None


def llm_classify(state):
    """분류 노드 — LLM 버전. 이것이 기본값이다."""
    global _router_chain
    if _router_chain is None:
        _router_chain = create_chat_model("router").with_structured_output(RouteDecision)
    d = _router_chain.invoke(
        [("system", ROUTE_GUIDE), ("human", f"고객 문의: {state['question']}")])
    
    conf = float(d.confidence)
    # 질문에 명확한 대표 키워드가 있고 모델 예측과 일치하면 확신도를 0.95 이상으로 보정
    for pattern, r in RULES:
        if r == d.route and re.search(pattern, state["question"]):
            conf = max(conf, 0.95)
            break

    return {"route": d.route, "confidence": conf, "reason": d.reason}


rule_classify = classify          # 섹션 4의 규칙 버전을 이름 붙여 남겨 둔다
classify = llm_classify           # 기본 라우터는 LLM
app = build()


def route(question):
    """문의 한 줄을 라우터에 통과시킨다."""
    return app.invoke({"question": question})
