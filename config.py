# -*- coding: utf-8 -*-
"""한곳에 모아 둔 설정. 여기 값만 바꿔도 동작이 달라진다.

- LLM_PROVIDER : 모델 제공자 ("openai", "anthropic", "google_genai", "ollama")
- MODEL        : 라우팅용. 출력이 짧고 호출이 많아 비용 최적화 등급이면 충분하다.
- ANSWER_MODEL : 답변 생성용. 매뉴얼 컨텍스트가 붙어 입력이 길고 지켜야 할 조건이 많다.
- CONF_THRESHOLD: 이 값 미만이면 사람에게 넘긴다. 올리면 안전해지고 자동화율이 떨어진다.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).parent / ".env")

BASE = Path(__file__).parent / "data"
DATA_URL = "https://raw.githubusercontent.com/88chacha/modumall-agent-data/main/data/"
DATA_FILES = ("customer_inquiries.csv", "routing_answers.csv", "policy_modumall.md",
              "hard_cases.csv", "mockdata_modumall.json", "answer_goldenset_multiturn.json")

# 다중 LLM 제공자 기본 권장 모델 매핑
PROVIDER_PRESETS = {
    "openai": {
        "label": "OpenAI",
        "router": "gpt-4o-mini",
        "answer": "gpt-4o",
        "env_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "router": "claude-3-5-haiku-20241022",
        "answer": "claude-3-7-sonnet-20250219",
        "env_key": "ANTHROPIC_API_KEY",
    },
    "google_genai": {
        "label": "Google (Gemini)",
        "router": "gemini-2.5-flash",
        "answer": "gemini-2.5-pro",
        "env_key": "GEMINI_API_KEY",
    },
    "ollama": {
        "label": "로컬 LLM (Ollama)",
        "router": "llama3.1",
        "answer": "llama3.1",
        "env_key": "OLLAMA_BASE_URL",
    },
}

LLM_PROVIDER = os.environ.get("MODU_LLM_PROVIDER", "openai").lower()
if LLM_PROVIDER not in PROVIDER_PRESETS:
    LLM_PROVIDER = "openai"

# 사용자가 지정하지 않은 경우 제공자 기본 모델 적용
default_router = PROVIDER_PRESETS[LLM_PROVIDER]["router"]
default_answer = PROVIDER_PRESETS[LLM_PROVIDER]["answer"]

MODEL = os.environ.get("MODU_MODEL", default_router)
ANSWER_MODEL = os.environ.get("MODU_ANSWER_MODEL", default_answer)

CONF_THRESHOLD = 0.5          # 라우팅 확신도 임계값
MAX_TOOL_TURNS = 3            # 도구 호출 루프 상한
GUARDRAIL_RETRY = 1           # 가드레일 위반 시 재생성 횟수
WORKERS = 12                  # 동시 호출 수. 요청 한도에 걸리면 낮춘다

ROUTES = ["ORDER_PLACE", "PRODUCT_INFO", "SHIPPING", "RETURN_REFUND", "OTHER"]
LABELS4 = ["ORDER_PLACE", "PRODUCT_INFO", "SHIPPING", "RETURN_REFUND"]


def create_chat_model(role: str = "router", provider: str = None, model_name: str = None,
                      temperature: float = 0, timeout: int = 60, max_retries: int = 2, **kwargs):
    """지정된 공급자 및 역할(router/answer)에 맞추어 LangChain ChatModel을 생성한다."""
    from langchain.chat_models import init_chat_model

    p = (provider or os.environ.get("MODU_LLM_PROVIDER", LLM_PROVIDER)).lower()
    if p not in PROVIDER_PRESETS:
        p = "openai"

    if not model_name:
        if role == "router":
            model_name = os.environ.get("MODU_MODEL", PROVIDER_PRESETS[p]["router"])
        else:
            model_name = os.environ.get("MODU_ANSWER_MODEL", PROVIDER_PRESETS[p]["answer"])

    call_kwargs = {
        "temperature": temperature,
        "timeout": timeout,
        "max_retries": max_retries,
    }
    call_kwargs.update(kwargs)

    if p == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        # o1, o3, gpt-5 등 특정 모델 reasoning_effort 처리
        if role == "answer" and not any(x in model_name for x in ["o1", "o3", "o4"]):
            call_kwargs["reasoning_effort"] = "none"
        return init_chat_model(model_name, model_provider="openai", api_key=api_key, **call_kwargs)

    elif p == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        return init_chat_model(model_name, model_provider="anthropic", api_key=api_key, **call_kwargs)

    elif p == "google_genai":
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        return init_chat_model(model_name, model_provider="google_genai", api_key=api_key, **call_kwargs)

    elif p == "ollama":
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        return init_chat_model(model_name, model_provider="ollama", base_url=base_url, **call_kwargs)

    else:
        return init_chat_model(model_name, **call_kwargs)


def ensure_data():
    """데이터가 없으면 공개 저장소에서 받아 온다."""
    import urllib.request
    BASE.mkdir(parents=True, exist_ok=True)
    for f in DATA_FILES:
        if not (BASE / f).exists():
            urllib.request.urlretrieve(DATA_URL + f, BASE / f)
            print("받음:", f)


