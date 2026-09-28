# -*- coding: utf-8 -*-
"""사람이 승인하는 고객 답변 발송 에이전트 (CS Auto-Reply HITL Agent)

주제: 고객 문의 자동 답변 발송 (고객에게 공식 답변을 내보내기 전 검수)
- 비가역적 액션: 고객에게 카카오 알림톡/SMS 공식 답변 발송 직전 위험 건에서 `interrupt()` 호출
- 4대 응답: 승인(원안 발송), 수정 후 승인(수정 발송), 반려(상담원 전화 이관), 다시 판정(AI 재작성)
- SqliteSaver 파일 체크포인터로 서버 재시작 후에도 대기 건 유지
"""
import sqlite3
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from config import BASE
from hitl_policy import check_stop_condition
from hitl_store import DB_PATH, get_case, resolve_case, save_or_update_case


class HITLState(TypedDict, total=False):
    """CS 답변 발송 HITL 파이프라인 State."""
    thread_id: str
    req_id: str
    customer: str
    category: str
    confidence: float
    question: str
    ai_draft: str
    cited_policy: str
    stop_reason: str
    impact: str
    status: str             # PENDING, APPROVED, MODIFIED, REJECTED, AUTO_PASSED, REJUDGE
    should_stop: bool
    manager_action: str     # approve, modify_approve, reject, rejudge
    manager_note: str
    final_answer: str
    execution_result: str
    rejudge_count: int
    logs: List[str]


def node_draft_answer(state: HITLState) -> HITLState:
    """① 초안 생성 및 위험도 분석 노드: 의도/답변 분석, 규정 매핑, 멈춤 조건 검사."""
    q = state.get("question", "")
    customer = state.get("customer", "고객")
    logs = list(state.get("logs", []))

    # 도메인 규칙 기반 초안 생성 및 규정 매핑
    if "배송비" in q or "캔버스화" in q:
        category = "SHIPPING"
        confidence = 0.95
        ai_draft = "캔버스화는 기본 배송비 3,000원이 부과되며, 30,000원 이상 구매 시 무료배송입니다. (배송규정 제2조 1항)"
        cited_policy = "배송규정 제2조 1항 (기본 배송비 3,000원, 3만원 이상 무료)"
    elif "단품" in q or "낱개" in q or "팬티" in q:
        category = "ORDER_PLACE"
        confidence = 0.92
        ai_draft = "요일팬티 7종 세트는 세트 기획 특가 상품으로 단품 개별 구매가 불가합니다. (상품판매규정 제5조 3항)"
        cited_policy = "상품판매규정 제5조 3항 (기획 세트 단품 분할 판매 불가)"
    elif "고민" in q or "취소할까" in q:
        category = "OTHER"
        confidence = 0.58  # 확신도 미달
        ai_draft = "주문 취소는 배송 준비 전에 가능할 수 있으니 마이페이지를 확인해 보세요."
        cited_policy = ""  # 규정 인용 누락
    elif "소비자원" in q or "고소" in q or "대표" in q:
        category = "SHIPPING"
        confidence = 0.89
        ai_draft = "배송 지연으로 불편을 드려 죄송합니다. 규정상 택배사 파업 지연 시 배송비 3,000원이 환불됩니다. (배송규정 제7조)"
        cited_policy = "배송규정 제7조 (택배사 지연 보상 기준)"
    elif "가죽" in q or "수제" in q or "왕복" in q:
        category = "RETURN_REFUND"
        confidence = 0.88
        ai_draft = "단순 변심 반품이시라면 왕복 배송비 6,000원은 고객님께서 부담하셔야 합니다."
        cited_policy = ""  # 규정 조항 누락
    else:
        category = state.get("category", "OTHER")
        confidence = state.get("confidence", 0.75)
        ai_draft = state.get("ai_draft", "문의하신 내용에 대해 확인 후 신속히 안내해 드리겠습니다.")
        cited_policy = state.get("cited_policy", "고객 상담 운영 기본 지침")

    case_info = {
        "confidence": confidence,
        "question": q,
        "cited_policy": cited_policy
    }
    stopped, reason = check_stop_condition(case_info, rule_type="rule_6")

    impact = f"고객({customer}님)의 카카오톡으로 해당 답변이 즉시 공식 발송됩니다."
    logs.append(f"AI 초안 생성 완료: 카테고리=[{category}], 확신도=[{confidence:.2f}], 멈춤여부=[{stopped}]")

    return {
        "category": category,
        "confidence": confidence,
        "ai_draft": ai_draft,
        "cited_policy": cited_policy,
        "stop_reason": reason,
        "impact": impact,
        "should_stop": stopped,
        "logs": logs
    }


def route_after_draft(state: HITLState) -> str:
    return "conditional_stop" if state.get("should_stop", False) else "execute"


def node_conditional_stop(state: HITLState) -> HITLState:
    """
    ② 멈춤 단계 (interrupt):
    [원칙] 결과를 바깥으로 내보내기(알림톡 발송) 바로 직전에 멈추고 담당자에게 검수를 요청한다.
    외부 발송 동작을 절대 수행하지 않고 interrupt 페이로드만 반환한다.
    """
    req_id = state.get("req_id", "CS_UNKNOWN")
    thread_id = state.get("thread_id", f"thread_{req_id}")

    save_or_update_case({
        "req_id": req_id,
        "thread_id": thread_id,
        "customer": state.get("customer", "고객"),
        "category": state.get("category", "OTHER"),
        "confidence": state.get("confidence", 0.0),
        "question": state.get("question", ""),
        "ai_draft": state.get("ai_draft", ""),
        "cited_policy": state.get("cited_policy", ""),
        "stop_reason": state.get("stop_reason", ""),
        "impact": state.get("impact", ""),
        "status": "PENDING"
    })

    # 10초 판단을 위한 5대 핵심 정보 전달
    human_response = interrupt({
        "req_id": req_id,
        "customer": state.get("customer", "고객"),
        "question": state.get("question", ""),
        "category": state.get("category", "OTHER"),
        "confidence": state.get("confidence", 0.0),
        "ai_draft": state.get("ai_draft", ""),
        "cited_policy": state.get("cited_policy", ""),
        "stop_reason": state.get("stop_reason", ""),
        "impact": state.get("impact", ""),
        "thread_id": thread_id
    })

    # resume(Command) 수신
    action = human_response.get("action", "approve")
    note = human_response.get("note", "")
    adjusted_text = human_response.get("adjusted_text") or state.get("ai_draft", "")

    logs = list(state.get("logs", []))
    logs.append(f"담당자 결정 수신: 조치={action}, 메모='{note}'")

    return {
        "manager_action": action,
        "manager_note": note,
        "final_answer": adjusted_text if action == "modify_approve" else state.get("ai_draft", ""),
        "logs": logs
    }


def route_after_stop(state: HITLState) -> str:
    action = state.get("manager_action", "approve")
    if action == "rejudge":
        return "rejudge"
    return "execute"


def node_rejudge(state: HITLState) -> HITLState:
    """③ 다시 판정 노드: 담당자의 지시를 받아 AI가 답변을 재작성."""
    note = state.get("manager_note", "")
    logs = list(state.get("logs", []))
    rejudge_count = state.get("rejudge_count", 0) + 1

    logs.append(f"AI 답변 재작성 수행 (담당자 지시: '{note}') [시도 #{rejudge_count}]")
    new_draft = f"{state.get('ai_draft', '')}\n[추가 안내]: 담당자 지침 반영 - {note}"
    new_policy = f"{state.get('cited_policy', '')} (담당자 피드백 반영)"

    return {
        "ai_draft": new_draft,
        "final_answer": new_draft,
        "cited_policy": new_policy,
        "rejudge_count": rejudge_count,
        "logs": logs
    }


def node_execute(state: HITLState) -> HITLState:
    """
    ④ 최종 실행 노드:
    멈춤 단계 이후에 실제로 고객 알림톡/SMS 발송 및 상담 로그 시스템에 반영한다.
    """
    req_id = state.get("req_id", "CS_UNKNOWN")
    action = state.get("manager_action", "auto_pass")
    note = state.get("manager_note", "")
    final_ans = state.get("final_answer", state.get("ai_draft", ""))
    customer = state.get("customer", "고객")
    logs = list(state.get("logs", []))

    if action == "reject":
        status = "REJECTED"
        exec_msg = f"🚫 [답변 발송 차단 및 상담원 이관] 사유: '{note}' (고객 {customer}님께 '전문 상담사 유선 연결 예정' 안내 발송 및 상담원 티켓 생성)"
        logs.append(exec_msg)
    elif action == "modify_approve":
        status = "MODIFIED"
        exec_msg = f"✏️ [수정본 고객 발송 완료] 고객 {customer}님께 담당자 수정 답변 공식 알림톡 전송 완료!"
        logs.append(exec_msg)
    elif action == "rejudge":
        status = "APPROVED"
        exec_msg = f"🔄 [재작성본 고객 발송 완료] AI 재작성 답변을 고객 {customer}님께 공식 알림톡 전송 완료!"
        logs.append(exec_msg)
    elif action == "approve":
        status = "APPROVED"
        exec_msg = f"✅ [원안 고객 발송 완료] AI 초안을 고객 {customer}님께 공식 알림톡 전송 완료!"
        logs.append(exec_msg)
    else:  # auto_pass
        status = "AUTO_PASSED"
        exec_msg = f"⚡ [자동 검수 통과 즉시 발송] 안전 기준 충족(확신도 0.7 이상 & 규정 인용 완료)으로 고객 {customer}님께 자동 전송 완료!"
        logs.append(exec_msg)

    # SQLite DB에 결과 영속화
    resolve_case(
        req_id=req_id,
        action=action,
        note=note or exec_msg,
        adjusted_text=final_ans
    )

    return {
        "status": status,
        "final_answer": final_ans,
        "execution_result": exec_msg,
        "logs": logs
    }


def build_hitl_agent(checkpointer=None):
    g = StateGraph(HITLState)

    g.add_node("draft_answer", node_draft_answer)
    g.add_node("conditional_stop", node_conditional_stop)
    g.add_node("rejudge", node_rejudge)
    g.add_node("execute", node_execute)

    g.add_edge(START, "draft_answer")
    g.add_conditional_edges("draft_answer", route_after_draft, {
        "conditional_stop": "conditional_stop",
        "execute": "execute"
    })
    g.add_conditional_edges("conditional_stop", route_after_stop, {
        "execute": "execute",
        "rejudge": "rejudge"
    })
    g.add_edge("rejudge", "execute")
    g.add_edge("execute", END)

    return g.compile(checkpointer=checkpointer)


# SQLite 파일 기반 영속 체크포인터 설정
SQLITE_CHECKPOINT_PATH = BASE / "data" / "hitl_checkpoints.db"
SQLITE_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)

_conn = sqlite3.connect(str(SQLITE_CHECKPOINT_PATH), check_same_thread=False)
hitl_checkpointer = SqliteSaver(_conn)
hitl_checkpointer.setup()

hitl_app = build_hitl_agent(checkpointer=hitl_checkpointer)


def submit_hitl_request(req_id: str, question: str, customer: str = "고객",
                        category: str = "OTHER", confidence: float = 0.75,
                        ai_draft: str = "", cited_policy: str = "") -> Dict[str, Any]:
    """새로운 고객 문의를 답변 발송 파이프라인에 투입."""
    thread_id = f"thread_{req_id}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: HITLState = {
        "thread_id": thread_id,
        "req_id": req_id,
        "customer": customer,
        "question": question,
        "category": category,
        "confidence": confidence,
        "ai_draft": ai_draft,
        "cited_policy": cited_policy,
        "logs": [f"고객 문의 접수: {req_id} ({customer}님)"]
    }

    result = hitl_app.invoke(initial_state, config=config)
    return result


def resume_hitl_decision(thread_id: str, action: str, note: str = "",
                         adjusted_text: Optional[str] = None) -> Dict[str, Any]:
    """담당자의 4대 조치(승인 / 수정 승인 / 반려 / 다시 판정)를 전달하여 재개."""
    config = {"configurable": {"thread_id": thread_id}}
    command = Command(resume={
        "action": action,
        "note": note,
        "adjusted_text": adjusted_text
    })
    result = hitl_app.invoke(command, config=config)
    return result
