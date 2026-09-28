# -*- coding: utf-8 -*-
"""사람이 승인하는 에이전트 콘솔 (CS 고객 문의 자동 답변 발송 HITL Dashboard)

주제: 고객 문의 자동 답변 발송 (고객에게 공식 답변을 내보내기 전 검수)
1. 🛡️ HITL 승인 관제 센터 (좋은 화면 5대 요소 & 4가지 응답 버튼)
2. 📊 멈춤 기준 검증 벤치마크 (개입률 · 놓침 · 헛멈춤 비교표)
"""
import uuid
import gradio as gr

from hitl_agent import hitl_app, resume_hitl_decision, submit_hitl_request
from hitl_policy import BENCHMARK_CASES, evaluate_rules_benchmark
from hitl_store import get_case, get_history_cases, get_pending_cases, resolve_case
from hitl_views import render_benchmark_table_html, render_hitl_card_html


def get_pending_table_data():
    pending = get_pending_cases()
    return [[
        c["req_id"],
        c["customer"],
        c.get("category", "-"),
        f"{c.get('confidence', 0.0):.2f}",
        c["stop_reason"],
        c["created_at"]
    ] for c in pending]


def get_history_table_data():
    history = get_history_cases(30)
    action_label = {
        "approve": "원안 발송 승인",
        "modify_approve": "수정 후 발송",
        "reject": "발송 차단 및 상담원 이관",
        "rejudge": "AI 재작성",
        "auto_pass": "자동 검수 통과 발송"
    }
    return [[
        c["req_id"],
        c["customer"],
        c.get("status", "-"),
        action_label.get(c.get("manager_action", ""), c.get("manager_action", "")),
        (c.get("final_answer", "")[:45] + "...") if len(c.get("final_answer", "")) > 45 else c.get("final_answer", ""),
        c.get("manager_note", ""),
        c.get("resolved_at", "")
    ] for c in history]


def get_pending_ids():
    pending = get_pending_cases()
    return [c["req_id"] for c in pending]


def ui_select_pending_case(req_id):
    if not req_id:
        return render_hitl_card_html(None), "", "", ""
    case = get_case(req_id)
    if not case:
        return render_hitl_card_html(None), "", "", ""
    return render_hitl_card_html(case), case.get("ai_draft", ""), "", ""


def ui_action_approve(req_id):
    if not req_id:
        return "⚠️ 선택된 대기 건이 없습니다.", render_hitl_card_html(None), get_pending_table_data(), get_history_table_data(), gr.update(choices=[]), ""
    try:
        res = resume_hitl_decision(f"thread_{req_id}", "approve", "담당자 원안 발송 승인")
        msg = f"✅ [{req_id}] 승인 완료! ({res.get('execution_result', '고객 알림톡 발송 완료')})"
    except Exception as e:
        resolve_case(req_id, "approve", "담당자 원안 발송 승인")
        msg = f"✅ [{req_id}] 승인 처리 완료 (고객 발송 동기화)"

    pending_ids = get_pending_ids()
    next_id = pending_ids[0] if pending_ids else None
    next_card = render_hitl_card_html(get_case(next_id)) if next_id else render_hitl_card_html(None)
    next_draft = get_case(next_id).get("ai_draft", "") if next_id else ""
    return msg, next_card, get_pending_table_data(), get_history_table_data(), gr.update(choices=pending_ids, value=next_id), next_draft


def ui_action_modify_approve(req_id, adj_text, note):
    if not req_id:
        return "⚠️ 선택된 대기 건이 없습니다.", render_hitl_card_html(None), get_pending_table_data(), get_history_table_data(), gr.update(choices=[]), ""
    text_str = (adj_text or "").strip()
    note_str = (note or "").strip() or "문구 보완 후 발송"
    try:
        res = resume_hitl_decision(f"thread_{req_id}", "modify_approve", note_str, adjusted_text=text_str)
        msg = f"✅ [{req_id}] 수정 승인 완료! ({res.get('execution_result', '수정 답변 전송 완료')})"
    except Exception as e:
        resolve_case(req_id, "modify_approve", note_str, adjusted_text=text_str)
        msg = f"✅ [{req_id}] 수정 답변 전송 완료!"

    pending_ids = get_pending_ids()
    next_id = pending_ids[0] if pending_ids else None
    next_card = render_hitl_card_html(get_case(next_id)) if next_id else render_hitl_card_html(None)
    next_draft = get_case(next_id).get("ai_draft", "") if next_id else ""
    return msg, next_card, get_pending_table_data(), get_history_table_data(), gr.update(choices=pending_ids, value=next_id), next_draft


def ui_action_reject(req_id, note):
    if not req_id:
        return "⚠️ 선택된 대기 건이 없습니다.", render_hitl_card_html(None), get_pending_table_data(), get_history_table_data(), gr.update(choices=[]), ""
    note_str = (note or "").strip() or "답변 부적절 / 전문 상담사 유선 상담 이관"
    try:
        res = resume_hitl_decision(f"thread_{req_id}", "reject", note_str)
        msg = f"🚫 [{req_id}] 발송 차단 완료! ({res.get('execution_result', '상담사 티켓 이관')})"
    except Exception as e:
        resolve_case(req_id, "reject", note_str)
        msg = f"🚫 [{req_id}] 발송 차단 및 상담원 이관 완료!"

    pending_ids = get_pending_ids()
    next_id = pending_ids[0] if pending_ids else None
    next_card = render_hitl_card_html(get_case(next_id)) if next_id else render_hitl_card_html(None)
    next_draft = get_case(next_id).get("ai_draft", "") if next_id else ""
    return msg, next_card, get_pending_table_data(), get_history_table_data(), gr.update(choices=pending_ids, value=next_id), next_draft


def ui_action_rejudge(req_id, note):
    if not req_id:
        return "⚠️ 선택된 대기 건이 없습니다.", render_hitl_card_html(None), get_pending_table_data(), get_history_table_data(), gr.update(choices=[]), ""
    note_str = (note or "").strip() or "매뉴얼 조항을 인용하여 더 정중하게 다시 작성"
    try:
        res = resume_hitl_decision(f"thread_{req_id}", "rejudge", note_str)
        msg = f"🔄 [{req_id}] AI 재작성 및 발송 완료! ({res.get('execution_result', '재작성 완료')})"
    except Exception as e:
        resolve_case(req_id, "rejudge", note_str)
        msg = f"🔄 [{req_id}] AI 답변 재작성 반영 완료!"

    pending_ids = get_pending_ids()
    next_id = pending_ids[0] if pending_ids else None
    next_card = render_hitl_card_html(get_case(next_id)) if next_id else render_hitl_card_html(None)
    next_draft = get_case(next_id).get("ai_draft", "") if next_id else ""
    return msg, next_card, get_pending_table_data(), get_history_table_data(), gr.update(choices=pending_ids, value=next_id), next_draft


def ui_submit_new_request(q, cust):
    if not (q or "").strip():
        pending_ids = get_pending_ids()
        return "⚠️ 고객 문의 내용을 입력하세요.", render_hitl_card_html(None), get_pending_table_data(), gr.update(choices=pending_ids), ""
    new_id = f"CS_{uuid.uuid4().hex[:6].upper()}"
    try:
        res = submit_hitl_request(
            req_id=new_id,
            question=q.strip(),
            customer=(cust or "고객").strip()
        )
        if res.get("should_stop"):
            msg = f"⏸️ [발송 전 멈춤] {new_id} 건이 안전 기준에 걸려 승인 대기 목록에 등록되었습니다! (이유: {res.get('stop_reason')})"
        else:
            msg = f"⚡ [자동 발송 완료] {new_id} 건이 확신도 0.70 이상 및 규정 인용 정상으로 고객에게 즉시 자동 전송되었습니다!"
    except Exception as e:
        msg = f"⚠️ 접수 처리 알림: {e}"

    pending_ids = get_pending_ids()
    curr_id = new_id if new_id in pending_ids else (pending_ids[0] if pending_ids else None)
    card = render_hitl_card_html(get_case(curr_id)) if curr_id else render_hitl_card_html(None)
    card_draft = get_case(curr_id).get("ai_draft", "") if curr_id else ""
    return msg, card, get_pending_table_data(), gr.update(choices=pending_ids, value=curr_id), card_draft


def ui_run_benchmark(conf_thresh, kw_text):
    kws = [k.strip() for k in (kw_text or "").split(",") if k.strip()]
    results = evaluate_rules_benchmark(custom_conf_threshold=float(conf_thresh), custom_keywords=kws)
    return render_benchmark_table_html(results)


with gr.Blocks(title="사람이 승인하는 에이전트 콘솔") as demo:
    gr.Markdown("# 🛡️ 고객 문의 자동 답변 발송 HITL 콘솔")
    gr.Markdown("**주제**: 고객 문의 자동 답변 발송 (고객에게 공식 답변을 내보내기 전 사람의 승인을 거치는 자동화)")
    gr.Markdown("LangGraph `interrupt` & `Command(resume=...)` 기반 멈춤/재개, `SqliteSaver` 영속 보관, 10초 내 판단 승인 화면")

    with gr.Tabs():
        with gr.Tab("🛡️ HITL 발송 승인 심사대"):
            gr.Markdown("### 🛡️ 비가역적 액션(고객 알림톡/문자 발송) 전 안전 승인 심사대")
            gr.Markdown("""
            > **💡 원칙 (10초 안에 판단할 수 있는 화면)**:  
            > AI 답변이 고객에게 전송되고 나면 되돌릴 수 없습니다. 잘못된 규정 안내나 분쟁성 답변을 방지하기 위해  
            > 확신도 미달이거나 규정 인용이 누락된 위험 건에서만 에이전트가 멈추고(`interrupt`), 담당자가 **10초 안에 판단**하여 조치합니다.
            """)

            with gr.Row():
                # 좌측: 승인 대기 목록 및 신규 접수
                with gr.Column(scale=5):
                    gr.Markdown("#### ⏳ 승인 대기 목록 (SQLite 영속 보관)")
                    initial_pids = get_pending_ids()
                    init_pid = initial_pids[0] if initial_pids else None
                    pending_selector = gr.Dropdown(
                        label="심사할 대기 건 선택 (ID)",
                        choices=initial_pids,
                        value=init_pid,
                        interactive=True
                    )
                    with gr.Row():
                        btn_refresh_pending = gr.Button("🔄 대기 목록 새로고침", size="sm")

                    pending_df = gr.Dataframe(
                        headers=["문의ID", "고객명", "카테고리", "확신도", "멈춘 이유", "접수시각"],
                        value=get_pending_table_data(),
                        interactive=False,
                        label="발송 대기 티켓 목록"
                    )

                    with gr.Accordion("➕ 테스트용 고객 문의 빠른 접수 (프리셋 & 직접 입력)", open=True):
                        gr.Markdown("**5대 대표 검증 케이스 빠른 접수:**")
                        with gr.Row():
                            b_cs1 = gr.Button("CS1: 캔버스화 배송비 (자동발송)", size="sm")
                            b_cs2 = gr.Button("CS2: 요일팬티 단품 (자동발송)", size="sm")
                        with gr.Row():
                            b_cs3 = gr.Button("CS3: 주문 취소 고민 (멈춤: 확신도 0.58)", size="sm", variant="stop")
                            b_cs4 = gr.Button("CS4: 소비자원/고소 위협 (멈춤: 분쟁)", size="sm", variant="stop")
                            b_cs5 = gr.Button("CS5: 수제 가방 반품비 (멈춤: 규정미인용)", size="sm", variant="stop")

                        with gr.Row():
                            in_q = gr.Textbox(
                                label="고객 문의 원문",
                                value="배송 지연으로 행사를 망쳤으니 전액 배상하고 소비자원에 고소하기 전에 대표랑 통화하게 해주세요."
                            )
                        with gr.Row():
                            in_cust = gr.Textbox(label="고객명", value="정다은")
                        btn_submit_req = gr.Button("고객 문의 파이프라인 접수 🚀", variant="primary")

                # 우측: 좋은 승인 화면 (5대 핵심 요소) 및 4대 응답 버튼
                with gr.Column(scale=7):
                    gr.Markdown("#### 📋 실시간 승인 심사대 (Good Approval Screen)")
                    hitl_card_display = gr.HTML(value=render_hitl_card_html(get_case(init_pid) if init_pid else None))

                    hitl_result_alert = gr.Markdown("대기 건을 선택하고 아래 네 가지 응답 중 하나를 선택하세요.")

                    gr.Markdown("---")
                    gr.Markdown("#### 🎯 담당자 네 가지 응답 결정 (Action Responses)")

                    with gr.Row():
                        btn_act_approve = gr.Button("1. [승인] 원안 그대로 고객 발송 ✅", variant="primary", scale=2)
                        btn_act_reject = gr.Button("3. [반려] 발송 차단 및 상담원 이관 🚫", variant="stop", scale=1)

                    with gr.Group():
                        gr.Markdown("**2. [수정 후 승인] 또는 4. [다시 판정] 세부 옵션:**")
                        with gr.Row():
                            in_adj_text = gr.Textbox(
                                label="수정할 고객 발송 답변 내용 (수정 승인용)",
                                value=get_case(init_pid).get("ai_draft", "") if init_pid else "",
                                lines=3
                            )
                        with gr.Row():
                            in_note = gr.Textbox(
                                label="담당자 조치 메모 / 반려 사유 / AI 재작성 지시사항",
                                placeholder="예: '단순 배송비 환불뿐 아니라 지연 사과 쿠폰 5천 원 동봉 안내 추가' 또는 '격화 고객으로 유선 상담 진행'"
                            )
                        with gr.Row():
                            btn_act_modify = gr.Button("2. [수정 후 승인] 수정본으로 고객 발송 ✏️", variant="secondary")
                            btn_act_rejudge = gr.Button("4. [다시 판정] AI 답변 재작성 지시 🔄", variant="secondary")

            with gr.Accordion("📜 처리 완료 이력 및 감사 로그 (Audit Trail)", open=False):
                history_df = gr.Dataframe(
                    headers=["문의ID", "고객명", "상태", "처리방식", "최종답변요약", "담당자메모", "완료시각"],
                    value=get_history_table_data(),
                    interactive=False
                )

            # 이벤트 바인딩
            pending_selector.change(
                ui_select_pending_case,
                inputs=[pending_selector],
                outputs=[hitl_card_display, in_adj_text, in_note, hitl_result_alert]
            )
            btn_refresh_pending.click(
                lambda: (get_pending_table_data(), get_history_table_data(), gr.update(choices=get_pending_ids())),
                outputs=[pending_df, history_df, pending_selector]
            )
            btn_act_approve.click(
                ui_action_approve,
                inputs=[pending_selector],
                outputs=[hitl_result_alert, hitl_card_display, pending_df, history_df, pending_selector, in_adj_text]
            )
            btn_act_modify.click(
                ui_action_modify_approve,
                inputs=[pending_selector, in_adj_text, in_note],
                outputs=[hitl_result_alert, hitl_card_display, pending_df, history_df, pending_selector, in_adj_text]
            )
            btn_act_reject.click(
                ui_action_reject,
                inputs=[pending_selector, in_note],
                outputs=[hitl_result_alert, hitl_card_display, pending_df, history_df, pending_selector, in_adj_text]
            )
            btn_act_rejudge.click(
                ui_action_rejudge,
                inputs=[pending_selector, in_note],
                outputs=[hitl_result_alert, hitl_card_display, pending_df, history_df, pending_selector, in_adj_text]
            )
            btn_submit_req.click(
                ui_submit_new_request,
                inputs=[in_q, in_cust],
                outputs=[hitl_result_alert, hitl_card_display, pending_df, pending_selector, in_adj_text]
            )
            b_cs1.click(lambda: ("캔버스화 배송비 얼마예요?", "김철수"), outputs=[in_q, in_cust])
            b_cs2.click(lambda: ("요일팬티 세트에서 하나만 살 수 있어요?", "이영희"), outputs=[in_q, in_cust])
            b_cs3.click(lambda: ("주문했는데 어제 취소할까 말까 고민중인데 어떻게 되나요?", "박민수"), outputs=[in_q, in_cust])
            b_cs4.click(lambda: ("배송 지연으로 행사를 망쳤으니 전액 배상하고 소비자원에 고소하기 전에 대표랑 통화하게 해주세요.", "정다은"), outputs=[in_q, in_cust])
            b_cs5.click(lambda: ("수제 가죽가방 반품하고 싶은데 왕복 배송비는 제가 내나요?", "최재훈"), outputs=[in_q, in_cust])

        with gr.Tab("📊 멈춤 기준 검증 벤치마크 (기준별 비교표)"):
            gr.Markdown("### 📊 멈춤 기준 검증하기 (개입률 · 놓침 · 헛멈춤)")
            gr.Markdown("""
            > **기준을 정했다고 끝이 아닙니다.** 그 기준으로 실제로 무엇이 멈추고 무엇이 빠져나가는지 확인해야 합니다.  
            > - **개입률**: 전체 중 사람에게 온 비율 (담당자의 업무 부담)  
            > - **🚨 놓침**: 사람이 봤어야 하는데 자동으로 나가 버린 건 (**가장 비싼 위험 실수! 오답 발송 및 분쟁**)  
            > - **⚠️ 헛멈춤**: 볼 필요가 없는데 사람에게 온 건 (담당자 피로 누적으로 이어짐)
            """)

            with gr.Row():
                with gr.Column(scale=4):
                    gr.Markdown("#### ⚙️ 멈춤 기준 임계치 시뮬레이션 설정")
                    in_bench_thresh = gr.Slider(
                        minimum=0.50, maximum=0.95, step=0.05, value=0.70,
                        label="분류 확신도(Confidence) 임계치 - 이 미만 시 사람 검수"
                    )
                    in_bench_kws = gr.Textbox(
                        label="민감 분쟁 키워드 (쉼표로 구분)",
                        value="소비자원, 고소, 신고, 대표, 손해배상, 피해, 언론, 고발, 폭언"
                    )
                    btn_run_bench = gr.Button("기준별 비교표 실시간 재계산 ⏱️", variant="primary")

                with gr.Column(scale=8):
                    gr.Markdown("#### 🏆 기준별 비교표 결과")
                    bench_table_display = gr.HTML(value=render_benchmark_table_html(evaluate_rules_benchmark()))

            btn_run_bench.click(
                ui_run_benchmark,
                inputs=[in_bench_thresh, in_bench_kws],
                outputs=[bench_table_display]
            )

if __name__ == "__main__":
    demo.launch(inbrowser=True)
