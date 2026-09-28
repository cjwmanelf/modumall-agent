# -*- coding: utf-8 -*-
"""멈춤 기준 정의 및 검증 모듈 (HITL Criteria & Validation)

주제: 고객 문의 자동 답변 발송 (고객에게 공식 답변을 내보내기 전)
※ 안내 지침 준수: 실습에서 다룬 단순 환불 승인 주제 제외, '고객 문의 자동 답변'으로 설계

1. 멈춤 기준 규칙 (Policy):
   - 기준 1: 분류 확신도(confidence) < 0.70 (오분류 및 엉뚱한 부서 규정 오안내 방지)
   - 기준 2: 공식 매뉴얼 규정 조항 인용 누락 (근거 없는 자의적 할루시네이션 답변 차단)
   - 기준 3: 민감/분쟁성 키워드 포함 (소비자원, 고소, 피해 등 법적/CS 분쟁 위험 예방)
2. 5대 검증 케이스 (CS1 ~ CS5)
3. 기준별 비교 지표 (개입률, 놓침, 헛멈춤) 자동 계산 엔진
"""
from typing import Any, Dict, List, Tuple

# 1. 5대 대표 고객 문의 및 자동 답변 검증 데이터셋
BENCHMARK_CASES = [
    {
        "id": "CS1",
        "customer": "김철수",
        "category": "SHIPPING",
        "confidence": 0.95,
        "question": "캔버스화 배송비 얼마예요?",
        "ai_draft": "캔버스화는 기본 배송비 3,000원이 부과되며, 30,000원 이상 구매 시 무료배송입니다. (배송규정 제2조 1항)",
        "cited_policy": "배송규정 제2조 1항 (기본 배송비 3,000원, 3만원 이상 무료)",
        "human_needed": False,  # 사람 검수 불필요 (확신도 0.95, 규정 인용 명확)
        "why_not_needed": "높은 확신도(0.95)와 명확한 매뉴얼 조항 인용으로 자동 발송 안전"
    },
    {
        "id": "CS2",
        "customer": "이영희",
        "category": "ORDER_PLACE",
        "confidence": 0.92,
        "question": "요일팬티 세트에서 하나만 살 수 있어요?",
        "ai_draft": "요일팬티 7종 세트는 세트 기획 특가 상품으로 단품 개별 구매가 불가합니다. (상품판매규정 제5조 3항)",
        "cited_policy": "상품판매규정 제5조 3항 (기획 세트 단품 분할 판매 불가)",
        "human_needed": False,  # 사람 검수 불필요 (확신도 0.92, 규정 인용 명확)
        "why_not_needed": "단품 구매 불가 규정이 정확히 인용되어 고객 분쟁 소지 없음"
    },
    {
        "id": "CS3",
        "customer": "박민수",
        "category": "OTHER",
        "confidence": 0.58,  # 확신도 0.70 미만!
        "question": "주문했는데 어제 취소할까 말까 고민중인데 어떻게 되나요?",
        "ai_draft": "주문 취소는 배송 준비 전에 가능할 수 있으니 마이페이지를 확인해 보세요.",
        "cited_policy": "",  # 규정 인용 누락
        "human_needed": True,   # 사람 검수 필수 (확신도 0.58 미달 + 모호한 의도)
        "why_needed": "의도가 불분명하여 AI가 출고 여부를 확인하지 않고 애매하게 답변할 위험"
    },
    {
        "id": "CS4",
        "customer": "정다은",
        "category": "SHIPPING",
        "confidence": 0.89,
        "question": "배송 지연으로 중요한 행사를 망쳤으니 전액 배상하고 소비자원에 고소하기 전에 대표랑 통화하게 해주세요.",
        "ai_draft": "배송 지연으로 불편을 드려 죄송합니다. 택배사 파업으로 지연되었으며 규정상 배송비 3,000원이 환불됩니다. (배송규정 제7조)",
        "cited_policy": "배송규정 제7조 (택배사 지연 보상 기준)",
        "human_needed": True,   # 사람 검수 필수 (민감 분쟁 키워드: 소비자원, 고소, 대표)
        "why_needed": "강한 고객 불만 및 법적 분쟁 위험 건으로 기계적 답변 발송 시 분쟁 격화 위험"
    },
    {
        "id": "CS5",
        "customer": "최재훈",
        "category": "RETURN_REFUND",
        "confidence": 0.88,
        "question": "수제 가죽가방 반품하고 싶은데 왕복 배송비는 제가 내나요?",
        "ai_draft": "고객님 단순 변심 반품이시라면 왕복 배송비 6,000원은 고객님께서 부담하셔야 합니다.",
        "cited_policy": "",  # 규정 조항(제N조) 공식 인용 누락!
        "human_needed": True,   # 사람 검수 필수 (수제 제작 상품 반품 불가 여부 확인 누락 및 규정 미인용)
        "why_needed": "주문 제작(수제) 상품 여부 확인이 누락되었고 공식 약관 조항 인용이 빠져 오안내 위험"
    }
]

# 민감/분쟁 키워드 목록
DISPUTE_KEYWORDS = ["소비자원", "고소", "신고", "대표", "손해배상", "피해", "언론", "고발", "폭언"]


def check_stop_condition(case: Dict[str, Any], rule_type: str = "rule_6",
                         custom_conf_threshold: float = 0.70,
                         custom_keywords: List[str] = None) -> Tuple[bool, str]:
    """
    고객에게 답변을 발송하기 전 에이전트가 멈추고 사람에게 승인을 받아야 하는지 판정.
    """
    conf = case.get("confidence", 1.0)
    q = case.get("question", "")
    cited = (case.get("cited_policy") or "").strip()

    if custom_keywords is None:
        custom_keywords = DISPUTE_KEYWORDS

    if rule_type == "rule_1":
        # 기준 1: 전부 자동 발송 (사람 개입 없음)
        return False, "전부 자동 발송 정책"

    elif rule_type == "rule_2":
        # 기준 2: 확신도 0.90 미만 (너무 빡빡한 기준)
        if conf < 0.90:
            return True, f"확신도 0.90 미달 (현재 {conf:.2f})"
        return False, "확신도 0.90 이상"

    elif rule_type == "rule_3":
        # 기준 3: 민감 분쟁 키워드만 검사
        for kw in custom_keywords:
            if kw in q:
                return True, f"민감 분쟁 키워드 감지 ('{kw}')"
        return False, "분쟁 키워드 없음"

    elif rule_type == "rule_4":
        # 기준 4: 확신도 0.70 미만 단일 기준
        if conf < custom_conf_threshold:
            return True, f"분류 확신도 {custom_conf_threshold:.2f} 미달 ({conf:.2f})"
        return False, "확신도 기준 충족"

    elif rule_type == "rule_5":
        # 기준 5: 공식 규정 인용 누락 단일 기준
        if not cited or ("조" not in cited and "규정" not in cited):
            return True, "공식 매뉴얼 조항 인용 누락 (출처 불명 답변 위험)"
        return False, "규정 인용 완료"

    elif rule_type == "rule_6":
        # 기준 6: [골든 룰 - 복합 기준]
        # (확신도 < 0.70) OR (규정 인용 누락) OR (민감 분쟁 키워드 감지)
        reasons = []
        if conf < custom_conf_threshold:
            reasons.append(f"분류 확신도 {custom_conf_threshold:.2f} 미달 ({conf:.2f})")
        if not cited or ("조" not in cited and "규정" not in cited):
            reasons.append("공식 매뉴얼 조항 인용 누락")
        for kw in custom_keywords:
            if kw in q:
                reasons.append(f"민감 분쟁 키워드 감지 ('{kw}')")
                break
        if reasons:
            return True, " & ".join(reasons)
        return False, "자동 발송 통과 (확신도 충족 + 규정 인용 완료 + 정상 문의)"

    return False, "자동 발송 통과"


def evaluate_rules_benchmark(custom_conf_threshold: float = 0.70,
                             custom_keywords: List[str] = None) -> List[Dict[str, Any]]:
    """
    교재의 기준별 비교표(개입률, 놓침, 헛멈춤)를 고객 문의 자동 답변 발송 도메인으로 산출.
    - 개입률: 전체 중 사람에게 온 비율 (사람의 업무 부하)
    - 놓침: 사람이 봤어야 하는데(human_needed=True) 자동으로 나가버린 건 (치명적인 오안내/분쟁 사고)
    - 헛멈춤: 볼 필요 없는데(human_needed=False) 사람에게 온 건 (업무 피로도 증가)
    """
    total = len(BENCHMARK_CASES)
    rules_def = [
        ("rule_1", "기준 1: 전부 자동 발송", "검수 없이 AI 생성 답변 즉시 고객에게 발송"),
        ("rule_2", "기준 2: 확신도 0.90 미만", "확신도 0.90 미만 시 무조건 사람 검수 (과도한 멈춤)"),
        ("rule_3", "기준 3: 민감 분쟁 키워드만 검사", "단순 키워드(소비자원, 고소 등)만 검사"),
        ("rule_4", f"기준 4: 확신도 {custom_conf_threshold:.2f} 미만 단일 기준", "분류 확신도만 검사하고 답변 내용/규정은 무시"),
        ("rule_5", "기준 5: 규정 조항 미인용 단일 기준", "답변 속 공식 약관/매뉴얼 조항 인용 여부만 검사"),
        ("rule_6", f"기준 6: 복합 기준 (확신도<{custom_conf_threshold:.2f} + 규정미인용 + 분쟁키워드)", "3대 위험 요소를 모두 포괄하는 최적의 승인 정책 (골든 룰)"),
    ]

    results = []
    for r_id, r_name, r_desc in rules_def:
        stopped_count = 0
        missed_cases = []      # 놓침: 사람 검수 필요한데 자동 발송됨
        false_alarm_cases = [] # 헛멈춤: 자동 발송 가능한데 사람을 부름

        for case in BENCHMARK_CASES:
            stopped, _ = check_stop_condition(
                case, rule_type=r_id,
                custom_conf_threshold=custom_conf_threshold,
                custom_keywords=custom_keywords
            )
            if stopped:
                stopped_count += 1

            if case["human_needed"] and not stopped:
                missed_cases.append(case["id"])
            elif not case["human_needed"] and stopped:
                false_alarm_cases.append(case["id"])

        intervention_rate = round(stopped_count / total * 100, 1)
        missed_count = len(missed_cases)
        false_alarm_count = len(false_alarm_cases)

        results.append({
            "rule_id": r_id,
            "rule_name": r_name,
            "description": r_desc,
            "stopped_count": stopped_count,
            "total_count": total,
            "intervention_rate": f"{intervention_rate}% ({stopped_count}/{total})",
            "missed_count": missed_count,
            "missed_cases": ", ".join(missed_cases) if missed_cases else "-",
            "false_alarm_count": false_alarm_count,
            "false_alarm_cases": ", ".join(false_alarm_cases) if false_alarm_cases else "-",
            "is_best": (missed_count == 0 and false_alarm_count == 0)
        })

    return results
