# 모두몰 고객 응대 AI 에이전트 구축 통합 가이드

본 문서는 가상 온라인 쇼핑몰 '모두몰'의 고객 문의를 자동으로 분류하고, 어드민 DB 조회 및 업무 매뉴얼에 엄격히 근거하여 정확하고 안전하게 답변하는 **고객 응대 AI 에이전트(Customer Service AI Agent)**의 전체 설계, 구현, 평가 및 가드레일 파이프라인을 다룹니다.

---

## 1. 시스템 개요 및 전체 파이프라인 (Overview & Architecture)

### 1.1 핵심 구축 목표 및 3단계 처리 원칙
쇼핑몰 고객 문의는 "배송비 얼마예요?", "반품하고 싶어요", "이 세트 단품 구매 가능한가요?"와 같이 겉으로는 한 줄짜리 유사한 질문처럼 보이지만, 실제 수행해야 하는 업무 프로세스는 완전히 다릅니다. 본 에이전트는 **판단, 조회, 규정 준수**라는 3단계 프로세스를 엄격히 분리하여 수행합니다.

1. **분류 (판단 - Classification & Routing)**: 고객 문의의 실제 의도를 파악하여 5가지 라우트 중 하나로 배정합니다.
2. **조회 (Information Retrieval & Tool Usage)**: 매뉴얼에서 필요한 장만 선별하여 컨텍스트를 구성하고, 어드민 DB(목 데이터) 조회 도구를 호출합니다.
3. **근거 기반 답변 생성 및 가드레일 (Grounded Generation & Guardrail)**: 조회된 데이터와 해당 매뉴얼 정책에만 근거하여 답변을 작성하며, 답변 속 수치의 출처를 기계적으로 역추적 검사합니다.

### 1.2 단일 거대 프롬프트 처리 방식의 문제점
모든 매뉴얼과 전체 조회 로직을 하나의 거대한 프롬프트로 처리할 경우 다음과 같은 치명적 문제가 발생합니다.
- **비용 및 지연 시간 증가**: 매 문의마다 전체 매뉴얼(1만 3천 자 이상)이 입력되어 토큰 비용이 급증하고 응답 속도가 느려집니다.
- **무관한 정책에 의한 오답 유도**: 배송비 문의에 반품 배송비 5,000원 정책이 프롬프트에 포함되어 있으면, 모델이 엉뚱하게 반품 배송비를 안내하는 할루시네이션이 발생합니다.
- **근거 없는 수치 지어내기(Hallucination)**: DB 조회 없이 모델 내부 지식으로 "무료배송 기준은 40,000원입니다"와 같이 거짓된 정보를 완벽하게 자연스러운 문장으로 생성합니다.

### 1.3 LangGraph 기반 상태 그래프(StateGraph) 구조
전체 시스템은 분기 판단 및 도구 호출 루프를 제어하기 위해 **LangGraph의 `StateGraph`**를 기반으로 오케스트레이션됩니다.

```
[고객 문의 입력]
       │
       ▼
[라우터 (Router)] ── (확신도 미달 / 범위 밖) ──► [상담원 이관 / 범위 밖 안내 종료]
       │
 (route 확정)
       ▼
[매뉴얼 컨텍스트 조립] (라우트별 관련 장만 발췌)
       │
       ▼
[조회 계획 수립 및 도구 호출 (Agent ⇄ Tools Loop)]
       │
  (식별자 미흡 시) ──► [되묻기(ASK) 및 종료]
       │
  (조회 성공 시)
       ▼
[LLM 답변 생성] (매뉴얼 + DB 조회 결과만 사용)
       │
       ▼
[수치 검증 가드레일 (Guardrail)]
  ├── (출처 확인됨) ──────────► [고객에게 최종 답변 전달]
  └── (출처 불분명 / 위반) ──► [재생성 1회 시도] ── (재위반 시) ──► [상담원 이관]
```

---

## 2. 데이터 체계 및 라벨링 규정 (Data & Labeling Policy)

### 2.1 사용 데이터셋 구성
- **`customer_inquiries.csv` (193건)**: 실제 의류 쇼핑몰 상담 기록 기반 질의응답 데이터. (18개 세부 인텐트, 9개 대분류)
- **`policy_modumall.md`**: 모두몰 CS 운영팀의 상담원 업무 매뉴얼 v2.0 (라우트, 답변, 조회 경계의 기준 문서)
- **`mockdata_modumall.json`**: 어드민 시스템을 대치하는 목 데이터 (상품 20종, 주문 11건, 반품 5건 등)
- **`routing_answers.csv`**: 문의 193건 전체에 대한 정답 라우트 라벨
- **`hard_cases.csv` (72건)**: 이관 및 경계 판단 훈련용 난이도 높은 고난도 케이스
- **`answer_goldenset_multiturn.json` (34개 대화, 112턴)**: 답변 채점용 대화 정답셋

### 2.2 5개 라우트 경로 정의 (매뉴얼 §1 및 §7.1 근거)

| 매뉴얼 유형 | 코드 라우트 식별자 | 담당 파트 및 정의 |
| :--- | :--- | :--- |
| **주문·구매** | `ORDER_PLACE` | 구매·주문 접수, 구매 가능 여부, 수량/옵션 변경 요청 |
| **상품 문의** | `PRODUCT_INFO` | 상품 구성, 소재, 실측, 재고, 품절 상품 재입고 문의 |
| **배송** | `SHIPPING` | 배송비, 배송 기간, 배송 상태 조회, 무료배송 기준 |
| **교환·반품·환불** | `RETURN_REFUND` | 교환/반품/환불 신청 조건, 진행 상태 및 처리 비용 |
| **응대 범위 밖** | `OTHER` | 오프라인 매장, 웹사이트 이용, 행사, 타 채널 주문, 제조사 A/S 등 (매뉴얼 §7.1) |

> **분류 원칙 (매뉴얼 §1.1)**: "고객이 쓴 단어가 아니라, **고객이 원하는 결과**로 판단한다."  
> 예: "낱개로도 구매 가능한가요?" ➔ 어휘는 '구매 가능'이 들어가나, 상품 구성 정보를 묻는 것이므로 `PRODUCT_INFO`로 분류.

---

## 3. 평가셋(Evaluation Set) 구축 및 평가 지표 (Evaluation Framework)

### 3.1 데이터 분할 및 데이터 누수(Data Leakage) 방지
학습/프롬프트에 사용한 데이터로 평가하면 성능이 과대평가되므로 strict separation을 적용합니다.
- **`eval` (120건)**: 성능 측정용 평가 데이터. 4개 핵심 라우트(`ORDER_PLACE`, `PRODUCT_INFO`, `SHIPPING`, `RETURN_REFUND`)에 각 30건씩 균등 배치하여 소수 클래스 성적이 묻히지 않도록 설계.
- **`fewshot` (40건)**: LLM 프롬프트 예시(Few-shot) 전용으로 격리.
- **`outscope` (33건)**: 범위 밖(`OTHER`) 문의 전용 평가셋.

### 3.2 주요 성능 평가 지표
1. **Macro F1 Score**: 클래스별 F1-score의 단순 평균. 데이터 불균형 환경에서 소수 라우트의 분류 실패를 감추지 않고 평가하기 위한 주 지표.
2. **Confusion Matrix (혼동 행렬)**: 라우터가 어느 라우트로 오분류했는지 구체적 지점 파악. (`ORDER_PLACE` ↔ `PRODUCT_INFO` 혼동이 가장 빈번함)
3. **자동화율(Automation Rate) vs 처리건 정확도(Accuracy)**:
   $$\text{자동화율} = \frac{\text{상담원 이관 없이 자동 처리된 건수}}{\text{전체 문의 건수}}$$
   확신도 임계값을 올리면 오답은 줄어들지만 이관율이 높아져 자동화율이 떨어지는 교환 관계(Trade-off)가 존재함.

---

## 4. 라우터 그래프 구현 (Router Graph Implementation)

### 4.1 규칙 기반 라우터 (Rule-based Router)
키워드 정규표현식 매칭을 통해 빠른 1차 분류를 수행합니다.

```python
import re
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, START, END

class RouterState(TypedDict):
    question: str
    route: str
    confidence: float
    reason: str
    action: str
    message: Optional[str]

RULES = [
    (r"환불|반품|교환|취소|반송|수거|검품", "RETURN_REFUND"),
    (r"배송비|택배비|무료\s?배송|배송|택배|출고|도착|언제\s?(오|와)|어디쯤", "SHIPPING"),
    (r"주문할|구매할게|살게요|사고\s?싶|결제|주문\s?가능|구매\s?가능|낱개|단품", "ORDER_PLACE"),
    (r"구성|포함|소재|재질|사이즈|치수|재고|정품|색상|품질|몇\s?(장|개)", "PRODUCT_INFO"),
    (r"매장|오프라인|지점|영업\s?시간|주차", "OTHER"),
]

CONF_THRESHOLD = 0.5

def classify_rule(state: RouterState) -> RouterState:
    q = state["question"]
    for pattern, route in RULES:
        if re.search(pattern, q):
            return {"route": route, "confidence": 0.8, "reason": "키워드 규칙 매치"}
    return {"route": "OTHER", "confidence": 0.3, "reason": "매치되는 규칙 없음"}

def gate(state: RouterState) -> RouterState:
    if state["confidence"] < CONF_THRESHOLD:
        return {"action": "ESCALATE", "message": "정확한 확인을 위해 상담원에게 연결해 드리겠습니다."}
    if state["route"] == "OTHER":
        return {"action": "OUT_OF_SCOPE", "message": "해당 내용은 주문하신 사이트의 고객센터를 통해 문의해 주세요."}
    return {"action": "HANDLE", "message": None}
```

### 4.2 LLM 기반 라우터 (Structured Output 적용)
복잡한 어휘나 표현 손상이 있는 문의 처리를 위해 Pydantic 기반 구조화 출력을 강제합니다.

```python
from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

class RouteDecision(BaseModel):
    route: Literal["ORDER_PLACE", "PRODUCT_INFO", "SHIPPING", "RETURN_REFUND", "OTHER"] = Field(
        description="문의를 배정할 라우트"
    )
    confidence: float = Field(
        ge=0.0, le=1.0,
        description="판단의 확신도. 두 라우트 사이에서 애매하면 0.5 미만으로 낮춤"
    )
    reason: str = Field(description="판단 근거 한 문장 요약")

ROUTE_GUIDE = """너는 온라인 쇼핑몰 '모두몰'의 고객상담 라우터다.
[분류 원칙 - 매뉴얼 §1.1]
고객이 쓴 단어가 아니라, 고객이 원하는 결과로 판단한다.
ORDER_PLACE와 PRODUCT_INFO는 어휘가 유사하나, 바로 구매를 진행할 의사가 보이면 ORDER_PLACE, 살지 말지 판단하려고 정보를 묻는 것이면 PRODUCT_INFO다.

[범위 밖 판단 - 매뉴얼 §7.1]
오프라인 매장, 영업시간, 주차, 타 채널 주문, 제조사 A/S 문의는 모두 OTHER다.

[확신도 지침]
두 라우트 사이에서 결정하기 어려우면 confidence를 0.5 미만으로 낮춰라."""
```

---

## 5. 매뉴얼 분할, 동적 컨텍스트 조립 및 어드민 조회 도구 (Context Assembly & Tools)

### 5.1 매뉴얼 분할 및 라우트별 동적 컨텍스트 조립
전체 매뉴얼(`policy_modumall.md`)을 `##` 장 단위로 분할한 뒤, 해당 라우트에 꼭 필요한 장만 프롬프트에 결합합니다.

```python
SECTION_MAP = {
    "ORDER_PLACE": ["2"],       # 2장 주문·구매 문의
    "PRODUCT_INFO": ["3"],      # 3장 상품 문의
    "SHIPPING": ["4"],          # 4장 배송 문의
    "RETURN_REFUND": ["5", "6"], # 5장 접수 + 6장 비용 및 처리
    "OTHER": [],
}

ALWAYS_SECTIONS = ["0", "1", "7", "8"]

def build_context(route: str, sections_dict: dict) -> str:
    secs = ALWAYS_SECTIONS + SECTION_MAP.get(route, [])
    selected = [sections_dict[k] for k in secs if k in sections_dict]
    return "\n\n".join(selected)
```

### 5.2 어드민 DB 조회 도구 명세 (Admin Inquiry Tools)
매뉴얼 내 `[어드민 조회]` 표시 항목을 바탕으로 작성된 백엔드 조회 도구 목록입니다.

| 함수명 | 입력 인자 | 주요 반환 데이터 | 비고 |
| :--- | :--- | :--- | :--- |
| `search_product` | `query: str` | 상품 ID (`P0001` 등), 상품명, 카테고리, 점수 | 상품명 미확정 시 1차 호출 |
| `get_order_status` | `order_id: str` | 진행단계, 송장번호, 배송사, 결제금액 | 주문 상태 조회 |
| `get_product_detail` | `product_id: str` | 소재, 원산지, 재고, 사이즈표, 제작소요기간 | 상품 상세 정보 |
| `get_product_options` | `product_id: str` | 개별 구매 가능 여부, 옵션 목록 | 단품/옵션 구매 문의용 |
| `get_shipping_policy` | `product_id`, `order_amount`, `region` | 무료배송 기준액, 배송비, 부족액 | 산술 계산 포함 |
| `get_return_policy` | `product_id`, `order_id` | 반품가능기간, 개봉조건, 주문제작 여부 | 반품 조건 확인 |
| `get_return_status` | `order_id`, `return_id` | 수거/입고/검품/환불 단계, 귀책 주체 | `inspection_result` 검사 |
| `get_restock_info` | `product_id: str` | 재입고 확정 여부 (`is_confirmed`), 예정일 | 미확정 시 함부로 안내 금지 |
| `escalate_to_agent` | `reason: str`, `context: dict` | 이관 접수 상태 및 결과 | 상담원 이관 |

> **`null` (None) 데이터 처리 원칙**:  
> 반품 검품 결과(`inspection_result`)나 재입고 예정일(`is_confirmed`)이 `null`인 경우, "아직 확정되지 않았다"고 있는 그대로 안내해야 합니다. 임의로 자사 귀책이나 날짜를 지어내면 심각한 민원이 발생합니다.

---

## 6. 답변 생성기, 수치 검증 가드레일 및 채점 시스템 (Generator & Guardrail)

### 6.1 답변 생성기 프롬프트 및 수기 절차 강제
프롬프트 단순 금지 목록보다 **단계별 수행 절차**를 명시할 때 도구 호출 및 답변 완수율이 크게 향상됩니다.

1. **1단계**: 고객이 상품을 이름으로 말했으면 `search_product`를 부른다. (상품 ID를 알고 있을 때만 건너뜀)
2. **2단계**: `resolved_product_id`가 나오면 해당 ID로 필요한 세부 조회 도구를 부른다. (후보가 여럿이거나 비어있으면 되묻는다)
3. **3단계**: 주문·반품 문의는 주문번호(`0-0000`)로 관련 조회를 실행한다.
4. **4단계**: 조회를 마친 뒤 매뉴얼과 조회 결과에만 근거하여 1~3문장 간결한 존댓말로 답변을 작성한다.

### 6.2 기계적 수치 검증 가드레일 (Mechanical Guardrail)
LLM이 생성한 답변 문장 속 모든 숫자를 추출하여 **조회 결과** 및 **매뉴얼 고정값**과의 출처 일치 여부를 역추적 검사합니다.

```python
import re
import json

FIXED_POLICY = {
    "base_shipping_fee": 2500,
    "return_fee_full": 5000,
    "return_fee_partial": 2500,
    "cutoff_hour": 11,
}

def extract_numbers(obj) -> set:
    text = json.dumps(obj, ensure_ascii=False) if isinstance(obj, (dict, list)) else str(obj)
    text = re.sub(r"(?<=\d),(?=\d)", "", text)
    return {int(m) for m in re.findall(r"\d+", text)}

def allowed_numbers(tool_results: dict) -> set:
    allowed = set(FIXED_POLICY.values())
    if tool_results:
        t_nums = extract_numbers(tool_results)
        allowed.update(t_nums)
        base = sorted(allowed)
        for a in base:
            for b in base:
                if a > b:
                    allowed.add(a - b)
                    allowed.add(a + b)
    return allowed

def guardrail_check(answer: str, tool_results: dict = None, min_check_val: int = 1000) -> dict:
    allowed = allowed_numbers(tool_results)
    ans_nums = extract_numbers(answer)
    
    suspicious = [n for n in ans_nums if n >= min_check_val and n not in allowed]
    
    if suspicious:
        return {
            "ok": False,
            "error": "UNGROUNDED_NUMBER",
            "details": f"출처 없는 수치 발견: {suspicious}"
        }
    return {"ok": True, "error": None}
```

### 6.3 정답셋 채점 및 이중 축 평가 지표 (Competency & Safety)
- **Competency (능력)**:
  - `tools`: 반드시 호출했어야 하는 조회 함수 목록 준수 여부
  - `must`: 답변에 반드시 포함되어야 하는 핵심 수치/문구 포함 여부
- **Safety (안전)**:
  - `forbid`: 답변에 절대로 나타나면 안 되는 금지 수치/확답 문구 포함 여부 (위반 건수 0건 목표)
  - `action`: `ANSWER`, `ASK`(되묻기), `ESCALATE`(이관), `OUT_OF_SCOPE` 행동 판정 정확도

---

## 7. 실전 배포 및 아키텍처 확장 가이드 (Deployment & Future Work)

### 7.1 멀티턴 대화 상태 관리 (LangGraph Checkpointer)
단발성 문의 외에 "그거 언제 와요?", "환불 진행은 어떻게 되고 있죠?"와 같은 문맥 의존적 발화를 처리하기 위해 `MemorySaver` 또는 외부 DB 기반 체크포인터를 적용합니다.

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

config = {"configurable": {"thread_id": "user_session_123"}}
response = app.invoke({"messages": [("user", "배송비 얼마예요?")]}, config=config)
```

### 7.2 엔티티 링크 (Entity Linking) 및 한계점 극복
- **현재 한계**: 단순 토큰 접해/문자열 완전 일치 방식으로 상품명을 탐색하므로, "요일팬티 세트" ➔ "브라-팬티 세트"와 같은 동의어나 유의어 탐색 시 미매칭 발생.
- **향후 개선**: 상품 카탈로그 임베딩 벡터 검색(Dense Retrieval) 및 N-gram 유사도 계산 알고리즘 결합.

### 7.3 FastAPI 서비스 엔드포인트 구성예시
```python
from fastapi import FastAPI, BaseModel

app = FastAPI(title="ModuMall CS Agent API")

class ChatRequest(BaseModel):
    conversation_id: str
    question: str

@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    config = {"configurable": {"thread_id": req.conversation_id}}
    result = agent_app.invoke({"question": req.question}, config=config)
    return {
        "action": result.get("action"),
        "answer": result.get("answer"),
        "route": result.get("route"),
        "guardrail_status": result.get("guardrail"),
    }
```

---
*본 가이드 문서는 안티그라비티(Antigravity) 및 AI 에이전트 개발 파이프라인 구축 시 단일 참조 표준으로 사용할 수 있도록 작성되었습니다.*
