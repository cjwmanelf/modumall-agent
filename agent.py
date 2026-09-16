# -*- coding: utf-8 -*-
"""라우터 · 조회 · 생성 · 가드레일을 하나의 그래프로 잇는다.

route → answer → guard → (END | answer 재시도 | escalate)
"""
import operator
from typing import Annotated, List, Optional, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from config import GUARDRAIL_RETRY
from answer import answer_with_tools
from guardrail import guardrail
from router import app as router_app
from tools import escalate_to_agent

class AgentState(TypedDict, total=False):
    """오늘 만든 파이프라인 전체가 통과하는 State."""

    question: str
    history: Annotated[list, operator.add]   # 리듀서가 붙어 있어 턴마다 덮이지 않고 쌓인다
    route: str
    confidence: float
    action: str                 # HANDLE / ASK / ANSWER / ESCALATE / OUT_OF_SCOPE
    tools: List[str]
    results: dict
    answer: str
    guardrail_ok: Optional[bool]
    attempts: int


def with_history(state: AgentState) -> str:
    """앞 턴의 발화를 앞에 붙인다. 대화가 없으면 이번 발화 그대로."""
    prior = state.get("history") or []
    return " ".join(prior + [state["question"]])


def node_answer(state: AgentState) -> AgentState:
    """② 조회 + ③ 생성 — 안에서 도구 호출 그래프가 한 바퀴 돈다."""
    text, results = answer_with_tools(with_history(state), state["route"])
    if results.get("get_order_status", {}).get("is_external_channel"):
        return {"action": "OUT_OF_SCOPE", "tools": list(results), "results": results}
    if not results:                       # 조회할 식별자가 없어 모델이 되물은 경우
        return {"action": "ASK", "tools": [], "results": {}, "answer": text,
                "history": [state["question"]]}
    return {"tools": list(results), "results": results, "answer": text,
            "history": [state["question"]],
            "attempts": state.get("attempts", 0) + 1}


def node_guard(state: AgentState) -> AgentState:
    """④ 가드레일 — 출처 없는 숫자가 있으면 되돌려 보낸다."""
    ok = guardrail(state["answer"], state["results"])["ok"]
    return {"guardrail_ok": ok, "action": "ANSWER" if ok else "RETRY"}


def node_escalate(state: AgentState) -> AgentState:
    reason = {"ESCALATE": "분류확신도미달", "OUT_OF_SCOPE": "응대범위밖"}.get(
        state["action"], "가드레일위반")
    msg = ("해당 내용은 주문하신 사이트의 고객센터를 통해 문의해 주셔야 확인이 가능합니다."
           if state["action"] == "OUT_OF_SCOPE"
           else escalate_to_agent(reason, {"q": state["question"]})["message"])
    return {"answer": msg, "guardrail_ok": state.get("guardrail_ok")}


def after_route(state: AgentState) -> str:
    return "answer" if state["action"] == "HANDLE" else "escalate"


def after_answer(state: AgentState) -> str:
    return END if state["action"] == "ASK" else ("escalate"
                                                 if state["action"] == "OUT_OF_SCOPE" else "guard")


def after_guard(state: AgentState) -> str:
    """통과하면 끝. 위반이면 한 번 더 생성해 보고, 그래도 안 되면 이관한다."""
    if state["guardrail_ok"]:
        return END
    return "answer" if state.get("attempts", 0) < 2 else "escalate"


def node_route(state):
    """① 분류 — 라우터 그래프를 그대로 부른다."""
    r = router_app.invoke({"question": with_history(state)})
    return {"route": r["route"], "confidence": r["confidence"], "action": r["action"]}


def build_agent(checkpointer=None):
    g = StateGraph(AgentState)
    g.add_node("route", node_route)
    g.add_node("answer", node_answer)
    g.add_node("guard", node_guard)
    g.add_node("escalate", node_escalate)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", after_route, {"answer": "answer", "escalate": "escalate"})
    g.add_conditional_edges("answer", after_answer,
                            {"guard": "guard", "escalate": "escalate", END: END})
    g.add_conditional_edges("guard", after_guard,
                            {"answer": "answer", "escalate": "escalate", END: END})
    g.add_edge("escalate", END)
    return g.compile(checkpointer=checkpointer)


agent_app = build_agent()
chat_app = build_agent(checkpointer=InMemorySaver())     # 대화용(맥락 유지)


def customer_agent(question):
    """문의 한 줄을 파이프라인에 통과시킨다."""
    out = agent_app.invoke({"question": question})
    if out["action"] == "RETRY":
        out["action"] = "ESCALATE"
    return {"question": question, **out}
