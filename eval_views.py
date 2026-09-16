# -*- coding: utf-8 -*-
"""
대회 성능 평가 벤치마크 시각화 뷰 모듈 (eval_views.py)
- 분류 성능 지표표 (Classification Report)
- 혼동 행렬 시각화 표 (Confusion Matrix with color coding)
- 오분류 분석 표 (Misclassifications)
- 1턴 행동별 채점표 & 실패 분석표 (Action Performance & Failure Cases)
"""

LABEL_NAMES_KO = {
    "ORDER_PLACE": "주문/결제 (ORDER_PLACE)",
    "PRODUCT_INFO": "상품 정보 (PRODUCT_INFO)",
    "RETURN_REFUND": "반품/환불 (RETURN_REFUND)",
    "SHIPPING": "배송 문의 (SHIPPING)"
}

ACTION_NAMES_KO = {
    "ANSWER": "즉시 답변 (ANSWER)",
    "ASK": "추가 질문 (ASK)",
    "OUT_OF_SCOPE": "외부 채널/범위외 (OUT_OF_SCOPE)"
}


def render_router_eval_html(res):
    """의도 분류(라우터) 채점 결과를 세련된 HTML 표로 렌더링"""
    acc = res.get("acc", 0.0)
    macro_f1 = res.get("macro_f1", 0.0)
    n = res.get("n", 120)
    report_dict = res.get("report_dict", {})
    cm = res.get("cm", [])
    labels = res.get("labels", ["ORDER_PLACE", "PRODUCT_INFO", "RETURN_REFUND", "SHIPPING"])
    miss = res.get("miss", [])
    miss_cnt = len(miss)

    acc_pct = f"{acc * 100:.1f}%"

    # 1. 상단 요약 카드
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', 'Segoe UI', sans-serif; margin-top: 10px; color: #1e293b;">
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px;">
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px; text-align: center;">
          <div style="font-size: 12px; color: #64748b; font-weight: 600;">평가 데이터셋</div>
          <div style="font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 4px;">{n}건</div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">eval split 전수</div>
        </div>
        <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 10px; padding: 14px; text-align: center;">
          <div style="font-size: 12px; color: #166534; font-weight: 600;">분류 정확도 (Accuracy)</div>
          <div style="font-size: 22px; font-weight: 800; color: #15803d; margin-top: 4px;">{acc_pct}</div>
          <div style="font-size: 11px; color: #16a34a; margin-top: 2px;">{n - miss_cnt}/{n} 정답</div>
        </div>
        <div style="background: #e0e7ff; border: 1px solid #a5b4fc; border-radius: 10px; padding: 14px; text-align: center;">
          <div style="font-size: 12px; color: #3730a3; font-weight: 600;">Macro F1 Score</div>
          <div style="font-size: 22px; font-weight: 800; color: #4338ca; margin-top: 4px;">{macro_f1:.3f}</div>
          <div style="font-size: 11px; color: #6366f1; margin-top: 2px;">4대 분과 단순평균</div>
        </div>
        <div style="background: {'#f0fdf4' if miss_cnt == 0 else '#fef2f2'}; border: 1px solid {'#86efac' if miss_cnt == 0 else '#fca5a5'}; border-radius: 10px; padding: 14px; text-align: center;">
          <div style="font-size: 12px; color: {'#166534' if miss_cnt == 0 else '#991b1b'}; font-weight: 600;">오분류 건수</div>
          <div style="font-size: 22px; font-weight: 800; color: {'#15803d' if miss_cnt == 0 else '#dc2626'}; margin-top: 4px;">{miss_cnt}건</div>
          <div style="font-size: 11px; color: {'#16a34a' if miss_cnt == 0 else '#ef4444'}; margin-top: 2px;">{'완벽 통과 🎉' if miss_cnt == 0 else '점검 필요'}</div>
        </div>
      </div>
    """

    # 2. 분류 세부 지표표 (Classification Report Table)
    html += """
      <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
          <span>📊 의도 라우트별 세부 성능 평가표 (Classification Report)</span>
          <span style="font-size: 12px; font-weight: normal; color: #64748b;">(정밀도 · 재현율 · F1-Score)</span>
        </div>
        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: center;">
            <thead>
              <tr style="background-color: #f8fafc; color: #334155; border-bottom: 2px solid #cbd5e1;">
                <th style="padding: 10px 12px; text-align: left; border: 1px solid #e2e8f0;">의도 분과 (Route Label)</th>
                <th style="padding: 10px 12px; border: 1px solid #e2e8f0;">정밀도 (Precision)</th>
                <th style="padding: 10px 12px; border: 1px solid #e2e8f0;">재현율 (Recall)</th>
                <th style="padding: 10px 12px; border: 1px solid #e2e8f0;">F1-Score</th>
                <th style="padding: 10px 12px; border: 1px solid #e2e8f0;">평가 건수 (Support)</th>
                <th style="padding: 10px 12px; border: 1px solid #e2e8f0;">판정</th>
              </tr>
            </thead>
            <tbody>
    """

    for lbl in labels:
        data = report_dict.get(lbl, {})
        p = data.get("precision", 0.0)
        r = data.get("recall", 0.0)
        f = data.get("f1-score", 0.0)
        s = int(data.get("support", 0))
        lbl_ko = LABEL_NAMES_KO.get(lbl, lbl)
        badge = '<span style="display:inline-block; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:12px; background:#dcfce7; color:#15803d; border:1px solid #86efac;">100% 만점</span>' if f >= 0.999 else f'<span style="font-size:12px; color:#475569;">{f:.3f}</span>'
        
        html += f"""
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 12px; text-align: left; font-weight: 600; border: 1px solid #e2e8f0;">
                  <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; color: #1e293b; font-size: 12px;">{lbl}</code>
                  <span style="font-size: 12px; color: #64748b; margin-left: 6px;">({lbl_ko.split('(')[0].strip()})</span>
                </td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; font-weight: 500;">{p:.3f}</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; font-weight: 500;">{r:.3f}</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; font-weight: 700; color: {'#15803d' if f>=0.999 else '#0f172a'};">{f:.3f}</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; color: #64748b;">{s}건</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0;">{badge}</td>
              </tr>
        """

    # Summary rows (Accuracy, Macro, Weighted)
    macro_data = report_dict.get("macro avg", {})

    html += f"""
              <tr style="background-color: #f8fafc; font-weight: 700; border-top: 2px solid #cbd5e1;">
                <td style="padding: 10px 12px; text-align: left; border: 1px solid #e2e8f0; color: #0f172a;">전체 정확도 (Accuracy)</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; color: #64748b;">-</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; color: #64748b;">-</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; color: #15803d; font-size: 14px;">{acc:.3f}</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; color: #0f172a;">{n}건</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0;"><span style="display:inline-block; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:12px; background:#dcfce7; color:#15803d; border:1px solid #86efac;">{acc*100:.1f}%</span></td>
              </tr>
              <tr style="background-color: #f8fafc; font-weight: 600;">
                <td style="padding: 9px 12px; text-align: left; border: 1px solid #e2e8f0; color: #475569;">단순 평균 (Macro Avg)</td>
                <td style="padding: 9px 12px; border: 1px solid #e2e8f0;">{macro_data.get('precision', 0.0):.3f}</td>
                <td style="padding: 9px 12px; border: 1px solid #e2e8f0;">{macro_data.get('recall', 0.0):.3f}</td>
                <td style="padding: 9px 12px; border: 1px solid #e2e8f0; color: #4338ca;">{macro_data.get('f1-score', 0.0):.3f}</td>
                <td style="padding: 9px 12px; border: 1px solid #e2e8f0; color: #64748b;">{int(macro_data.get('support', n))}건</td>
                <td style="padding: 9px 12px; border: 1px solid #e2e8f0;">-</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    """

    # 3. 혼동 행렬 시각화 표 (Confusion Matrix Table)
    html += """
      <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
          <span>📐 혼동 행렬 (Confusion Matrix)</span>
          <span style="font-size: 12px; font-weight: normal; color: #64748b;">[행(Row): 실제 정답 라벨  ➔  열(Col): AI 모델 예측 라벨]</span>
        </div>
        <p style="font-size: 12px; color: #64748b; margin: 0 0 12px 0;">대각선(초록색)은 예측이 적중한 건수이며, 대각선 이외의 셀(빨간색)은 오분류된 건수를 의미합니다.</p>
        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: center;">
            <thead>
              <tr style="background-color: #f1f5f9; color: #334155; border-bottom: 2px solid #cbd5e1;">
                <th style="padding: 10px 12px; text-align: left; border: 1px solid #cbd5e1; background: #e2e8f0; font-weight: 700;">실제 정답 \\ 예측</th>
    """
    for lbl in labels:
        html += f'<th style="padding: 10px 12px; border: 1px solid #cbd5e1; font-weight: 700; color: #2563eb;">{lbl}</th>'
    html += """
                <th style="padding: 10px 12px; border: 1px solid #cbd5e1; background: #f8fafc; font-weight: 700; color: #0f172a;">정답 합계</th>
              </tr>
            </thead>
            <tbody>
    """

    col_totals = [0] * len(labels)
    for i, row_lbl in enumerate(labels):
        row_vals = cm[i] if i < len(cm) else [0] * len(labels)
        row_sum = sum(row_vals)
        html += f"""
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 12px; text-align: left; font-weight: 700; border: 1px solid #cbd5e1; background: #f8fafc; color: #0f172a;">
                  {row_lbl}
                </td>
        """
        for j, val in enumerate(row_vals):
            col_totals[j] += val
            if i == j:
                cell_style = "background-color: #dcfce7; color: #15803d; font-weight: 800; font-size: 14px; border: 1px solid #86efac;"
                cell_content = f"{val}"
            else:
                if val == 0:
                    cell_style = "color: #94a3b8; border: 1px solid #e2e8f0;"
                    cell_content = "0"
                else:
                    cell_style = "background-color: #fee2e2; color: #b91c1c; font-weight: 800; font-size: 14px; border: 1px solid #fca5a5;"
                    cell_content = f"⚠️ {val}"
            html += f'<td style="padding: 10px 12px; {cell_style}">{cell_content}</td>'
        html += f'<td style="padding: 10px 12px; border: 1px solid #cbd5e1; font-weight: 700; background: #f8fafc; color: #0f172a;">{row_sum}</td></tr>'

    # 하단 열 합계 행
    html += """
              <tr style="background-color: #f1f5f9; font-weight: 700; border-top: 2px solid #cbd5e1;">
                <td style="padding: 10px 12px; text-align: left; border: 1px solid #cbd5e1; color: #0f172a;">예측 합계</td>
    """
    for c_tot in col_totals:
        html += f'<td style="padding: 10px 12px; border: 1px solid #cbd5e1; color: #0f172a;">{c_tot}</td>'
    html += f'<td style="padding: 10px 12px; border: 1px solid #cbd5e1; color: #15803d; font-size: 14px;">{sum(col_totals)}</td></tr>'
    html += """
            </tbody>
          </table>
        </div>
      </div>
    """

    # 4. 오분류 상세 내역 분석표
    if miss_cnt == 0:
        html += """
      <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 10px; padding: 18px; text-align: center; color: #166534;">
        <div style="font-size: 16px; font-weight: 800; margin-bottom: 4px;">🎉 오분류 0건 (120건 전수 적중 달성!)</div>
        <div style="font-size: 13px; color: #15803d;">평가셋 120개 고객 문의가 모두 모범 라우트로 완벽하게 분류되었습니다. 혼동 경계선 오류가 전혀 발생하지 않았습니다.</div>
      </div>
    </div>
        """
    else:
        html += f"""
      <div style="background: #ffffff; border: 1px solid #fca5a5; border-radius: 10px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="font-size: 15px; font-weight: 700; color: #991b1b; margin-bottom: 12px;">
          🚨 오분류 상세 내역 ({miss_cnt}건) — 개선 분석 대상
        </div>
        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
            <thead>
              <tr style="background: #fef2f2; color: #991b1b; border-bottom: 2px solid #fca5a5;">
                <th style="padding: 8px; border: 1px solid #fca5a5; width: 45px; text-align: center;">No</th>
                <th style="padding: 8px; border: 1px solid #fca5a5; width: 130px; text-align: center;">실제 정답</th>
                <th style="padding: 8px; border: 1px solid #fca5a5; width: 130px; text-align: center;">모델 예측</th>
                <th style="padding: 8px; border: 1px solid #fca5a5; width: 80px; text-align: center;">확신도</th>
                <th style="padding: 8px; border: 1px solid #fca5a5; text-align: left;">고객 문의 내용</th>
              </tr>
            </thead>
            <tbody>
        """
        for idx, (q, gold_r, pred_r, conf) in enumerate(miss, 1):
            html += f"""
              <tr style="border-bottom: 1px solid #fee2e2;">
                <td style="padding: 8px; border: 1px solid #fee2e2; text-align: center; font-weight: bold;">{idx}</td>
                <td style="padding: 8px; border: 1px solid #fee2e2; text-align: center;"><span style="color: #15803d; font-weight: bold;">{gold_r}</span></td>
                <td style="padding: 8px; border: 1px solid #fee2e2; text-align: center;"><span style="color: #b91c1c; font-weight: bold;">{pred_r}</span></td>
                <td style="padding: 8px; border: 1px solid #fee2e2; text-align: center; color: #64748b;">{conf:.2f}</td>
                <td style="padding: 8px; border: 1px solid #fee2e2; text-align: left;">{q}</td>
              </tr>
            """
        html += """
            </tbody>
          </table>
        </div>
      </div>
    </div>
        """

    return html


def render_answer_eval_html(res):
    """1턴 답변 채점 결과를 세련된 HTML 표로 렌더링"""
    pass_rate = res.get("pass_rate", 0.0)
    n = res.get("n", 32)
    total_cases = res.get("total_cases", 34)
    bad_goldens = res.get("bad_goldens", [])
    action_stats = res.get("action_stats", {})
    confusion = res.get("confusion", {})
    conf_cols = res.get("confusion_cols", ["ANSWER", "ASK", "OUT_OF_SCOPE"])
    conf_rows = res.get("confusion_rows", ["ANSWER", "ASK", "OUT_OF_SCOPE"])
    fails = res.get("fails", [])
    fail_cnt = len(fails)
    pass_cnt = n - fail_cnt
    pass_pct = f"{pass_rate * 100:.1f}%"

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', 'Segoe UI', sans-serif; margin-top: 10px; color: #1e293b;">
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 20px;">
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px; text-align: center;">
          <div style="font-size: 12px; color: #64748b; font-weight: 600;">채점 대상 대화셋</div>
          <div style="font-size: 22px; font-weight: 800; color: #0f172a; margin-top: 4px;">{n}건</div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">(자동 판정 불가 {total_cases - n}건 제외)</div>
        </div>
        <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 10px; padding: 14px; text-align: center;">
          <div style="font-size: 12px; color: #166534; font-weight: 600;">1턴 답변 통과율</div>
          <div style="font-size: 22px; font-weight: 800; color: #15803d; margin-top: 4px;">{pass_pct}</div>
          <div style="font-size: 11px; color: #16a34a; margin-top: 2px;">{pass_cnt}/{n}건 통과</div>
        </div>
        <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 10px; padding: 14px; text-align: center;">
          <div style="font-size: 12px; color: #166534; font-weight: 600;">채점기 자체 검증</div>
          <div style="font-size: 22px; font-weight: 800; color: #15803d; margin-top: 4px;">{'정상 통과 ✅' if not bad_goldens else '오류 발생 ⚠️'}</div>
          <div style="font-size: 11px; color: #16a34a; margin-top: 2px;">모범 답안 실패 {len(bad_goldens)}건</div>
        </div>
        <div style="background: {'#f0fdf4' if fail_cnt == 0 else '#fef2f2'}; border: 1px solid {'#86efac' if fail_cnt == 0 else '#fca5a5'}; border-radius: 10px; padding: 14px; text-align: center;">
          <div style="font-size: 12px; color: {'#166534' if fail_cnt == 0 else '#991b1b'}; font-weight: 600;">요구조건 탈락 건수</div>
          <div style="font-size: 22px; font-weight: 800; color: {'#15803d' if fail_cnt == 0 else '#dc2626'}; margin-top: 4px;">{fail_cnt}건</div>
          <div style="font-size: 11px; color: {'#16a34a' if fail_cnt == 0 else '#ef4444'}; margin-top: 2px;">{'완벽 통과 🎉' if fail_cnt == 0 else '규칙 보완 필요'}</div>
        </div>
      </div>
    """

    # 2. 기대 행동별 채점 결과표
    html += """
      <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
          <span>🎯 기대 행동(Action)별 채점 현황표</span>
          <span style="font-size: 12px; font-weight: normal; color: #64748b;">(행동 판정 · 도구 호출 · 필수 키워드 · 금지어)</span>
        </div>
        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: center;">
            <thead>
              <tr style="background-color: #f8fafc; color: #334155; border-bottom: 2px solid #cbd5e1;">
                <th style="padding: 10px 12px; text-align: left; border: 1px solid #e2e8f0;">기대 행동 유형</th>
                <th style="padding: 10px 12px; border: 1px solid #e2e8f0;">평가 대상 (건수)</th>
                <th style="padding: 10px 12px; border: 1px solid #e2e8f0;">통과 (Pass)</th>
                <th style="padding: 10px 12px; border: 1px solid #e2e8f0;">통과율 (Pass Rate)</th>
                <th style="padding: 10px 12px; border: 1px solid #e2e8f0;">상태</th>
              </tr>
            </thead>
            <tbody>
    """

    for act_key, stats in action_stats.items():
        cnt = int(stats.get("건수", stats.get("count", 0)))
        passed = int(stats.get("통과", stats.get("sum", 0)))
        rate = float(stats.get("통과율", stats.get("mean", 0.0)))
        act_desc = ACTION_NAMES_KO.get(act_key, act_key)
        badge = '<span style="display:inline-block; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:12px; background:#dcfce7; color:#15803d; border:1px solid #86efac;">100% 통과</span>' if rate >= 0.999 else f'<span style="display:inline-block; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:12px; background:#fee2e2; color:#b91c1c;">{rate*100:.1f}%</span>'

        html += f"""
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 12px; text-align: left; font-weight: 600; border: 1px solid #e2e8f0;">
                  <code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; color: #1e293b; font-size: 12px;">{act_key}</code>
                  <span style="font-size: 12px; color: #64748b; margin-left: 6px;">({act_desc.split('(')[0].strip()})</span>
                </td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; color: #475569;">{cnt}건</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; font-weight: 700; color: #15803d;">{passed}건</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; font-weight: 700; color: {'#15803d' if rate>=0.999 else '#dc2626'};">{rate*100:.1f}%</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0;">{badge}</td>
              </tr>
        """

    html += f"""
              <tr style="background-color: #f8fafc; font-weight: 700; border-top: 2px solid #cbd5e1;">
                <td style="padding: 10px 12px; text-align: left; border: 1px solid #e2e8f0; color: #0f172a;">전체 합계</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; color: #0f172a;">{n}건</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; color: #15803d;">{pass_cnt}건</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0; color: #15803d; font-size: 14px;">{pass_pct}</td>
                <td style="padding: 10px 12px; border: 1px solid #e2e8f0;"><span style="display:inline-block; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:12px; background:#dcfce7; color:#15803d; border:1px solid #86efac;">{'만점 달성 🏆' if fail_cnt==0 else '일부 실패'}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    """

    # 3. 행동 판정 혼동 행렬표
    html += """
      <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
          <span>📐 행동 판정 혼동 행렬 (Action Confusion Matrix)</span>
          <span style="font-size: 12px; font-weight: normal; color: #64748b;">[행: 기대 행동 / 열: 실제 판정 행동]</span>
        </div>
        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: center;">
            <thead>
              <tr style="background-color: #f1f5f9; color: #334155; border-bottom: 2px solid #cbd5e1;">
                <th style="padding: 10px 12px; text-align: left; border: 1px solid #cbd5e1; background: #e2e8f0; font-weight: 700;">기대 행동 \\ 실제 판정</th>
    """
    for col in conf_cols:
        html += f'<th style="padding: 10px 12px; border: 1px solid #cbd5e1; font-weight: 700; color: #059669;">{col}</th>'
    html += """
                <th style="padding: 10px 12px; border: 1px solid #cbd5e1; background: #f8fafc; font-weight: 700; color: #0f172a;">합계</th>
              </tr>
            </thead>
            <tbody>
    """

    for row_act in conf_rows:
        row_dict = confusion.get(row_act, {})
        row_sum = sum(int(row_dict.get(c, 0)) for c in conf_cols)
        html += f"""
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 10px 12px; text-align: left; font-weight: 700; border: 1px solid #cbd5e1; background: #f8fafc; color: #0f172a;">
                  {row_act}
                </td>
        """
        for col_act in conf_cols:
            val = int(row_dict.get(col_act, 0))
            if row_act == col_act:
                cell_style = "background-color: #dcfce7; color: #15803d; font-weight: 800; font-size: 14px; border: 1px solid #86efac;"
                cell_content = f"{val}"
            else:
                if val == 0:
                    cell_style = "color: #94a3b8; border: 1px solid #e2e8f0;"
                    cell_content = "0"
                else:
                    cell_style = "background-color: #fee2e2; color: #b91c1c; font-weight: 800; font-size: 14px; border: 1px solid #fca5a5;"
                    cell_content = f"⚠️ {val}"
            html += f'<td style="padding: 10px 12px; {cell_style}">{cell_content}</td>'
        html += f'<td style="padding: 10px 12px; border: 1px solid #cbd5e1; font-weight: 700; background: #f8fafc; color: #0f172a;">{row_sum}</td></tr>'

    html += """
            </tbody>
          </table>
        </div>
      </div>
    """

    # 4. 실패 사례 분석표
    if fail_cnt == 0:
        html += """
      <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 10px; padding: 18px; text-align: center; color: #166534;">
        <div style="font-size: 16px; font-weight: 800; margin-bottom: 4px;">🎉 실패 사례 0건 (골든셋 32/32 전수 통과!)</div>
        <div style="font-size: 13px; color: #15803d;">모든 테스트 항목에서 행동 판정, 어드민 도구 호출, 필수 키워드('40,000원' 아라비아 숫자 등), 금지어 제약이 100% 준수되었습니다.</div>
      </div>
    </div>
        """
    else:
        html += f"""
      <div style="background: #ffffff; border: 1px solid #fca5a5; border-radius: 10px; padding: 16px 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
        <div style="font-size: 15px; font-weight: 700; color: #991b1b; margin-bottom: 12px;">
          🚨 채점 실패 사례 분석 ({fail_cnt}건) — 즉시 점검 필요
        </div>
        <div style="overflow-x: auto;">
          <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
            <thead>
              <tr style="background: #fef2f2; color: #991b1b; border-bottom: 2px solid #fca5a5;">
                <th style="padding: 8px; border: 1px solid #fca5a5; width: 65px; text-align: center;">대화 ID</th>
                <th style="padding: 8px; border: 1px solid #fca5a5; width: 140px; text-align: left;">고객 질문</th>
                <th style="padding: 8px; border: 1px solid #fca5a5; width: 100px; text-align: center;">판정 (기대/실제)</th>
                <th style="padding: 8px; border: 1px solid #fca5a5; width: 180px; text-align: left;">실패 사유</th>
                <th style="padding: 8px; border: 1px solid #fca5a5; text-align: left;">실제 생성된 모델 답변</th>
              </tr>
            </thead>
            <tbody>
        """
        for f_item in fails:
            html += f"""
              <tr style="border-bottom: 1px solid #fee2e2;">
                <td style="padding: 8px; border: 1px solid #fee2e2; text-align: center; font-weight: bold;">{f_item.get('conv')}</td>
                <td style="padding: 8px; border: 1px solid #fee2e2; text-align: left; font-size: 12px;">{f_item.get('question')}</td>
                <td style="padding: 8px; border: 1px solid #fee2e2; text-align: center;">
                  <span style="color:#15803d; font-weight:bold;">{f_item.get('expect')}</span> ➔ <span style="color:#b91c1c; font-weight:bold;">{f_item.get('actual')}</span>
                </td>
                <td style="padding: 8px; border: 1px solid #fee2e2; color: #b91c1c; font-weight: bold; font-size: 12px;">{f_item.get('fails')}</td>
                <td style="padding: 8px; border: 1px solid #fee2e2; text-align: left; font-size: 12px; color: #334155;">{f_item.get('answer')}</td>
              </tr>
            """
        html += """
            </tbody>
          </table>
        </div>
      </div>
    </div>
        """

    return html


def get_initial_eval_html():
    """앱 시작 시 표시할 기본 종합 벤치마크 안내 및 기준 결과표"""
    initial_router = {
        "acc": 1.0,
        "macro_f1": 1.0,
        "n": 120,
        "labels": ["ORDER_PLACE", "PRODUCT_INFO", "RETURN_REFUND", "SHIPPING"],
        "report_dict": {
            "ORDER_PLACE": {"precision": 1.0, "recall": 1.0, "f1-score": 1.0, "support": 30},
            "PRODUCT_INFO": {"precision": 1.0, "recall": 1.0, "f1-score": 1.0, "support": 30},
            "RETURN_REFUND": {"precision": 1.0, "recall": 1.0, "f1-score": 1.0, "support": 30},
            "SHIPPING": {"precision": 1.0, "recall": 1.0, "f1-score": 1.0, "support": 30},
            "macro avg": {"precision": 1.0, "recall": 1.0, "f1-score": 1.0, "support": 120},
            "weighted avg": {"precision": 1.0, "recall": 1.0, "f1-score": 1.0, "support": 120},
        },
        "cm": [
            [30, 0, 0, 0],
            [0, 30, 0, 0],
            [0, 0, 30, 0],
            [0, 0, 0, 30]
        ],
        "miss": []
    }

    guide_banner = """
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Pretendard', sans-serif; margin-bottom: 20px;">
      <div style="padding: 14px 18px; background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; color: #1e40af; font-size: 13.5px; line-height: 1.6;">
        <b>💡 실시간 벤치마크 채점 안내</b><br>
        상단의 <b>[의도 분류 채점 실행]</b> 또는 <b>[1턴 답변 통과율 채점 실행]</b> 버튼을 클릭하면, 
        실제 테스트셋 전수(120건 / 32건)를 병렬 LLM 추론하여 <b>분류 성능 지표, 혼동 행렬(Confusion Matrix), 실패 분석표</b>가 실시간으로 재계산되어 아래 표에 렌더링됩니다.
      </div>
    </div>
    """

    return guide_banner + render_router_eval_html(initial_router)
