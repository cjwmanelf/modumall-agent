# 🛍️ 모두몰 고객응대 AI 에이전트 (ModuMall CS Agent)

고객 문의 한 줄을 받아 **의도를 분류하고 → 어드민 전산 DB에서 조회하고 → 업무 매뉴얼에 근거해 검증된 답변을 제공하는** 실시간 고객 상담 AI 에이전트 시스템입니다.

---

## 🎯 프로젝트가 지향하는 5가지 핵심 원칙 (Architecture)

```
[고객 입력] ──► [① 카테고리 판정] ──(확신도 미달)──► [② 안전 최우선 넘기기 (상담원 이관)]
                       │ (정상 판정)
                       ▼
              [③ 카테고리별 근거 조립] (매뉴얼 발췌 + 어드민 DB 조회)
                       │
                       ▼
              [④ 근거만으로 절제된 답변] (지레짐작 / 환각 차단)
                       │
                       ▼
              [⑤ 기계적 수치 검증 (가드레일)] ──(위반 시 재생성 / 이관)
```

1. **정확한 카테고리 판정 (Precision Routing)**:  
   고객 문의의 핵심 의도를 5개 분과(`ORDER_PLACE`, `PRODUCT_INFO`, `SHIPPING`, `RETURN_REFUND`, `OTHER`)로 엄밀하게 분류합니다.
2. **안전 최우선 상담원 이관 ("모르겠으면 넘기기")**:  
   의도가 모호하거나 확신도(`confidence`)가 기준치(0.5) 미만인 경우, 지레짐작으로 답하지 않고 인간 전문 상담사에게 즉시 이관(`ESCALATE`)합니다.
3. **카테고리별 동적 근거 조립 (Dynamic Context Assembly)**:  
   방대한 매뉴얼 전문을 몽땅 주입하지 않고, 판정된 카테고리에 꼭 필요한 매뉴얼 조항과 어드민 DB 전산 데이터만 선별하여 프롬프트에 조립합니다.
4. **철저한 근거 기반 답변 (Grounded & Controlled Answer)**:  
   실제 조회된 DB 전산 수치와 매뉴얼 규정에만 근거하여 답변하며, 규격화된 표현(금액 아라비아 숫자, 필수 표준어)을 준수합니다.
5. **기계적 수치 검증 가드레일 (Strict Numerical Guardrail)**:  
   답변 속 모든 금액 및 수치를 역추적하여, DB나 매뉴얼에 없는 출처 불명의 숫자가 섞여 나오면 고객에게 노출되기 전에 즉시 차단합니다.

---

## 📋 5가지 필수 구현 요구사항 및 반영 명세

### 1. 카테고리를 정하고 문서와 연결하기
- **4+1 카테고리 구성**: 실제 쇼핑몰 CS 업무 분과 및 규정 구조에 맞추어 `ORDER_PLACE`(주문/구매), `PRODUCT_INFO`(상품스펙), `SHIPPING`(배송), `RETURN_REFUND`(반품/환불), 그리고 어디에도 속하지 않는 예외를 위한 `OTHER`를 정의했습니다.
- **문서 매핑표 ([`context.py`](file:///c:/Users/cjwma/OneDrive/바탕%20화면/modumall-agent/context.py))**: `SECTION_MAP`을 통해 각 카테고리가 매뉴얼 1~7장의 어느 조항을 참조해야 하는지 1:1 매핑표를 구축하고, 동적으로 프롬프트를 조합합니다.

### 2. 평가셋 만들기
- **균형 잡힌 골든셋 구축**: `answer_goldenset_multiturn.json`에 20건 이상(34건)의 다회차 문의 문항을 카테고리별로 고르게 배치했습니다.
- **문항별 3축 검증 요소**:
  - `tools`: 반드시 호출해야 하는 기대 전산 도구
  - `must`: 답변에 반드시 포함되어야 할 핵심 사실 (예: `"40,000"`, `"품절"`, `"주문 제작"`)
  - `forbid`: 문서를 제대로 읽지 않았을 때 나오기 쉬운 그럴듯한 오답 및 한글 금액 표기
- **이관 문항 및 예외 케이스 포함**: 외부 제휴몰 주문(`is_external_channel`)이나 제조사 A/S 등 '답변하지 않고 넘기는 것'이 정답인 문항(`OUT_OF_SCOPE`, `ESCALATE`)을 섞어 안전 경로를 평가합니다.
- **엄격한 데이터 분리**: 프롬프트 예시용 `fewshot`(40건)과 성능 측정용 `eval`(120건 / 34건)을 엄격히 분리하여 데이터 오염을 방지했습니다.

### 3. 파이프라인 구현
- **단일 LangGraph 파이프라인 ([`agent.py`](file:///c:/Users/cjwma/OneDrive/바탕%20화면/modumall-agent/agent.py))**: `판정(route) → 근거 조립 및 조회(answer) → 수치 검증(guard) → 답변 출력/이관`을 하나의 유기적인 상태 그래프로 연결했습니다.
- **분류(`classify`)와 게이트(`gate`)의 분리 ([`router.py`](file:///c:/Users/cjwma/OneDrive/바탕%20화면/modumall-agent/router.py))**: 카테고리를 예측하는 LLM 노드와, 확신도를 보고 이관 여부를 결정하는 정책 노드를 분리하여 유연한 임계값 튜닝을 지원합니다.
- **기계적 수치 검사기 ([`guardrail.py`](file:///c:/Users/cjwma/OneDrive/바탕%20화면/modumall-agent/guardrail.py))**: 정규식을 통해 답변 속 숫자를 추출하고 허용 집합(DB 결과 + 매뉴얼 고정값 + 산술 연산값)과 대조 검사합니다.

### 4. 측정 (Evaluation)
- **도구 호출 적절성**: 기대 도구와 실제 호출 도구 집합이 정확히 일치할 때만 점수를 부여합니다.
- **답변 적절성**: `must`는 모두 충족하고 `forbid`는 단 하나도 위반하지 않았는지를 채점합니다.
- **채점기 자기 검증 ([`evaluate.py`](file:///c:/Users/cjwma/OneDrive/바탕%20화면/modumall-agent/evaluate.py))**: 평가 시작 전 모범 답안(Reference)을 먼저 채점하여 채점기 자체의 무결성을 항상 보증합니다.
- **실패 사례 분석 및 기록**: 실패 문항의 원인을 `fails_detail.json` 및 GUI 대시보드에 기록하며, 한 번에 하나씩 변경하며 성능 추이를 추적했습니다.

### 5. 데모 만들기
- **Gradio 웹 대시보드 ([`app_gui.py`](file:///c:/Users/cjwma/OneDrive/바탕%20화면/modumall-agent/app_gui.py))**: 브라우저에서 직접 대화하고 원클릭 테스트 질문을 실행할 수 있는 대화형 웹 UI를 제공합니다.
- **투명한 내부 관제 패널**: 고객 답변뿐만 아니라 분류된 라우트, 확신도 점수, 판정 행동(`Action`), 호출된 도구 목록, 가드레일 검증 통과 여부, 어드민 DB 원본 JSON 데이터를 실시간으로 투명하게 공개합니다.
- **보안 격리**: API 키는 [`.env`](file:///c:/Users/cjwma/OneDrive/바탕%20화면/modumall-agent/.env) 파일에만 저장되며 [`.gitignore`](file:///c:/Users/cjwma/OneDrive/바탕%20화면/modumall-agent/.gitignore)를 통해 GitHub에 절대 유출되지 않습니다.

---

## ⚡ 멀티 LLM 지원 (Multi-Provider)

OpenAI 뿐만 아니라 다양한 LLM 공급자를 GUI 설정 화면에서 원클릭으로 전환하여 사용할 수 있습니다:
* **🟢 OpenAI**: `gpt-4o`, `gpt-4o-mini` 등
* **🟣 Anthropic (Claude)**: `claude-3-7-sonnet`, `claude-3-5-haiku` 등
* **🔵 Google (Gemini)**: `gemini-2.5-pro`, `gemini-2.5-flash` 등
* **🟠 로컬 LLM (Ollama)**: `llama3.1`, `qwen2.5` 등 (로컬 PC 오프라인 구동)

---

## 🚀 5분 만에 시작하기

### 1. 설치 및 환경 설정
```bash
pip install -r requirements.txt
cp .env.example .env        # .env 파일에 사용할 LLM API Key 입력
```

### 2. 실행 모드
```bash
# ① 웹 GUI 대시보드 실행 (app.py 또는 app_gui.py 둘 다 가능)
python app.py

# ② 콘솔 대화 모드
python chat.py

# ③ 성능 벤치마크 평가 측정
python evaluate.py
```

---

## 🗺️ 파일 지도 — 어디를 고치면 무엇이 움직이나

| 파일/디렉토리 | 무엇이 들어 있나 | 고치면 움직이는 것 |
| :--- | :--- | :--- |
| **`docs/`** | 공식 상담원 업무 매뉴얼 문서 (`policy_modumall.md`) | 답변 근거 및 정책 지침 원문 |
| **`data/`** | 라우팅 평가셋(`eval_set.csv`), 골든셋(`answer_gold.json`), 전산 DB | 평가 문항 및 채점 기준, 모의 DB |
| **`config.py`** | 멀티 LLM 제공자, 모델 사양, 임계값, 동시 호출 수 | 전체 시스템 엔진 및 비용/속도 |
| **`prompts.py`** | 라우팅 지침(`ROUTE_GUIDE`) · 답변 규칙(`ANSWER_RULES`) | **분류 정확도 & 답변 통과율 (가장 큰 영향)** |
| **`router.py`** | 의도 분류 그래프 (`classify` · `gate`) | ① 의도 분류 정확도 |
| **`tools.py`** | 쇼핑몰 어드민 전산 조회 도구 8개 (`search_product` 등) | ② 답변 — `tools 미호출`, 불용어 필터링 |
| **`context.py`** | 매뉴얼 분할 및 라우트별 동적 조립 (`SECTION_MAP`) | ② 답변 — 필요한 근거의 프롬프트 주입 여부 |
| **`answer.py`** | LangGraph 도구 호출 루프 (agent ↔ tools) | ② 답변 생성 및 도구 체이닝 |
| **`guardrail.py`** | 답변 속 숫자의 출처 역추적 검사기 | ② 답변 — `forbid` 위반 및 환각 차단 |
| **`agent.py`** | 전체 파이프라인 통합 그래프 | 전체 대화 흐름 (되묻기 `ASK`, 이관 `ESCALATE`) |
| **`evaluate.py`** | 2대 지표(분류 정확도, 답변 통과율) 측정 및 채점기 | 채점 기준 및 벤치마크 |
| **`app.py`** / **`app_gui.py`** | Gradio 웹 인터페이스 & 관제 대시보드 | 사용자 UI, 멀티 LLM 설정, 벤치마크 뷰어 |
| **`REPORT.md`** | 7대 핵심 항목 정리된 최종 기술 보고서 | 프로젝트 기술 설계 및 분석 일지 |
