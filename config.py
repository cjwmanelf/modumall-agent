# -*- coding: utf-8 -*-
"""한곳에 모아 둔 설정. 여기 값만 바꿔도 동작이 달라진다.

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

MODEL = os.environ.get("MODU_MODEL", "gpt-5.6-luna")
ANSWER_MODEL = os.environ.get("MODU_ANSWER_MODEL", "gpt-5.6-terra")

CONF_THRESHOLD = 0.5          # 라우팅 확신도 임계값
MAX_TOOL_TURNS = 3            # 도구 호출 루프 상한
GUARDRAIL_RETRY = 1           # 가드레일 위반 시 재생성 횟수
WORKERS = 12                  # 동시 호출 수. 요청 한도에 걸리면 낮춘다

ROUTES = ["ORDER_PLACE", "PRODUCT_INFO", "SHIPPING", "RETURN_REFUND", "OTHER"]
LABELS4 = ["ORDER_PLACE", "PRODUCT_INFO", "SHIPPING", "RETURN_REFUND"]


def ensure_data():
    """데이터가 없으면 공개 저장소에서 받아 온다."""
    import urllib.request
    BASE.mkdir(parents=True, exist_ok=True)
    for f in DATA_FILES:
        if not (BASE / f).exists():
            urllib.request.urlretrieve(DATA_URL + f, BASE / f)
            print("받음:", f)


