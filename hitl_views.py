# -*- coding: utf-8 -*-
"""HITL 전용 HTML 뷰 및 컴포넌트 렌더링 모듈 (CS 자동 답변 발송)

교재 4강의 '승인 화면과 응답 설계하기' (좋은 화면 5대 요소)와
3강의 '멈춤 기준 검증하기' (비교표) HTML 시각화
"""
import html
from typing import Any, Dict, List


def render_hitl_card_html(case: Dict[str, Any]) -> str:
    """좋은 승인 화면의 5대 필수 요소를 카드 형태로 렌더링 (CS 답변 발송 모드)."""
    if not case:
        return """
        <div style="padding: 30px; text-align: center; border: 2px dashed #cbd5e1; border-radius: 12px; background: #f8fafc; color: #64748b;">
            <div style="font-size: 32px; margin-bottom: 8px;">📬</div>
            <div style="font-size: 16px; font-weight: bold;">대기 중인 고객 문의 답변 건을 선택하세요.</div>
            <div style="font-size: 13px; margin-top: 4px;">상단 대기 목록에서 클릭하면 10초 내 판단을 위한 5대 핵심 정보가 표시됩니다.</div>
        </div>
        """

    req_id = html.escape(str(case.get("req_id", "-")))
    customer = html.escape(str(case.get("customer", "고객")))
    question = html.escape(str(case.get("question", "-")))
    category = html.escape(str(case.get("category", "OTHER")))
    conf = case.get("confidence", 0.0)
    conf_str = f"{conf:.2f}"
    ai_draft = html.escape(str(case.get("ai_draft", "답변 초안이 생성되지 않았습니다.")))
    cited_policy = html.escape(str(case.get("cited_policy", "공식 규정 미인용 (확인 필요)")))
    stop_reason = html.escape(str(case.get("stop_reason", "발송 안전 기준 검토 필요")))
    impact = html.escape(str(case.get("impact", f"고객({customer}님)의 카카오톡으로 해당 답변이 즉시 발송됩니다.")))

    conf_color = "#16a34a" if conf >= 0.70 else "#dc2626"

    return f"""
    <div style="background: white; border: 2px solid #e2e8f0; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <!-- 상단 헤더 -->
        <div style="background: linear-gradient(135deg, #0f172a, #1e293b); color: white; padding: 14px 20px; display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="background: #ef4444; color: white; padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 800; letter-spacing: 0.5px;">발송 직전 승인 대기</span>
                <span style="font-size: 16px; font-weight: 700;">문의 ID: {req_id}</span>
                <span style="color: #94a3b8; font-size: 13px;">(고객: {customer}님)</span>
            </div>
            <div style="background: rgba(255,255,255,0.15); padding: 4px 12px; border-radius: 20px; font-size: 13px;">
                ⏱️ 10초 내 신속 판단 심사대
            </div>
        </div>

        <div style="padding: 20px;">
            <!-- 1. 고객 요청 원문 -->
            <div style="margin-bottom: 14px; background: #f8fafc; border-left: 4px solid #3b82f6; padding: 12px 16px; border-radius: 0 8px 8px 0;">
                <div style="font-size: 12px; color: #64748b; font-weight: 700; margin-bottom: 4px;">① 고객 문의 원문</div>
                <div style="font-size: 15px; color: #1e293b; font-weight: 600; line-height: 1.5;">"{question}"</div>
            </div>

            <!-- 2. 의도 분류 및 확신도 & 멈춘 이유 (2단 그리드) -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px;">
                <!-- 분류 및 확신도 -->
                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px;">
                    <div style="font-size: 12px; color: #1e40af; font-weight: 600;">② 의도 분류 및 확신도</div>
                    <div style="font-size: 15px; color: #1e293b; font-weight: 700; margin-top: 2px;">
                        분과: <span style="color: #2563eb;">{category}</span> | 확신도: <span style="color: {conf_color}; font-weight: 800;">{conf_str}</span>
                        {"(⚠️ 기준 0.70 미달)" if conf < 0.70 else "(정상)"}
                    </div>
                </div>

                <!-- 멈춘 이유 -->
                <div style="background: #fff1f2; border: 1px solid #fecdd3; border-radius: 8px; padding: 12px;">
                    <div style="font-size: 12px; color: #9f1239; font-weight: 600;">④ 발송 직전 멈춘 이유</div>
                    <div style="font-size: 14px; color: #be123c; font-weight: 700; margin-top: 2px;">
                        ⚠️ {stop_reason}
                    </div>
                </div>
            </div>

            <!-- 3. AI 답변 초안 및 인용 규정 -->
            <div style="margin-bottom: 14px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px 16px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 12px; color: #166534; font-weight: 700;">③ AI 발송 답변 초안</span>
                    <span style="font-size: 11px; color: #475569; background: #dcfce7; padding: 2px 8px; border-radius: 4px;">
                        📜 <b>근거 규정:</b> {cited_policy if cited_policy else "<span style='color:red;'>미인용</span>"}
                    </span>
                </div>
                <div style="font-size: 14px; color: #14532d; font-weight: 600; line-height: 1.6; background: white; padding: 10px 12px; border-radius: 6px; border: 1px solid #dcfce7;">
                    {ai_draft}
                </div>
            </div>

            <!-- 5. 통과시키면 일어나는 일 (가장 중요) -->
            <div style="background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 12px 16px; display: flex; align-items: center; gap: 12px;">
                <div style="font-size: 24px;">🚨</div>
                <div>
                    <div style="font-size: 11px; color: #92400e; font-weight: 700; text-transform: uppercase;">
                        ⑤ 통과시키면 일어나는 일 (비가역적 외부 발송 영향)
                    </div>
                    <div style="font-size: 14px; color: #78350f; font-weight: 800; margin-top: 2px;">
                        "{impact}"
                    </div>
                </div>
            </div>
        </div>
    </div>
    """


def render_benchmark_table_html(results: List[Dict[str, Any]]) -> str:
    """교재 3강 기준별 비교표(개입률, 놓침, 헛멈춤) HTML 렌더링."""
    rows_html = ""
    for r in results:
        is_best = r.get("is_best", False)
        bg_style = "background-color: #f0fdf4;" if is_best else ""

        missed_count = r["missed_count"]
        if missed_count > 0:
            missed_html = f"<span style='color: #dc2626; font-weight: 800;'>{missed_count}건 ({r['missed_cases']}) ❌</span>"
        else:
            missed_html = "<span style='color: #16a34a; font-weight: 700;'>0건 (안전) ✨</span>"

        false_count = r["false_alarm_count"]
        if false_count > 0:
            false_html = f"<span style='color: #d97706; font-weight: 700;'>{false_count}건 ({r['false_alarm_cases']})</span>"
        else:
            false_html = "<span style='color: #16a34a; font-weight: 700;'>0건</span>"

        best_tag = "<span style='background: #15803d; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; margin-left: 6px;'>골든 룰 (추천)</span>" if is_best else ""

        rows_html += f"""
        <tr style="{bg_style}">
            <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: bold;">
                {r['rule_name']} {best_tag}
            </td>
            <td style="padding: 10px; border: 1px solid #cbd5e1; font-size: 12px; color: #475569;">
                {r['description']}
            </td>
            <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: center; font-weight: 600;">
                {r['intervention_rate']}
            </td>
            <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: center;">
                {missed_html}
            </td>
            <td style="padding: 10px; border: 1px solid #cbd5e1; text-align: center;">
                {false_html}
            </td>
        </tr>
        """

    return f"""
    <div style="overflow-x: auto; margin-top: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
            <thead>
                <tr style="background: #f1f5f9; color: #1e293b;">
                    <th style="padding: 10px; border: 1px solid #cbd5e1; width: 28%;">승인 기준 (Policy Rule)</th>
                    <th style="padding: 10px; border: 1px solid #cbd5e1; width: 26%;">기준 설명</th>
                    <th style="padding: 10px; border: 1px solid #cbd5e1; width: 14%; text-align: center;">개입률 (업무 부담)</th>
                    <th style="padding: 10px; border: 1px solid #cbd5e1; width: 18%; text-align: center; color: #b91c1c;">
                        🚨 놓침 (오안내 위험)
                    </th>
                    <th style="padding: 10px; border: 1px solid #cbd5e1; width: 14%; text-align: center; color: #b45309;">
                        ⚠️ 헛멈춤 (피로도)
                    </th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """
