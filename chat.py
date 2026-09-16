# -*- coding: utf-8 -*-
"""직접 말을 걸어 본다.  `python chat.py`  또는  `python chat.py "배송비 얼마예요?"`

매 턴 아래에 route · 확신도 · 호출한 도구 · 가드레일 통과 여부가 함께 찍힌다.
틀린 답이 나오면 그 로그가 라우팅·조회·생성 셋 중 어디서 틀렸는지 알려 준다.
"""
import itertools
import sys

from config import ensure_data

_session = itertools.count(1)


def trace(out):
    conf = out.get("confidence")
    conf_s = f"{conf:.2f}" if conf is not None else "-"
    print(f'상담원 > {out["answer"]}')
    print(f'         ↳ route={out.get("route", "-")} conf={conf_s} action={out["action"]}'
          f' tools={out.get("tools", [])} guardrail={out.get("guardrail_ok")}\n')


def ask(question, thread_id="demo"):
    """한 턴만 물어본다. 같은 thread_id 로 다시 부르면 앞 턴이 이어진다."""
    from agent import chat_app
    out = chat_app.invoke({"question": question}, {"configurable": {"thread_id": thread_id}})
    print(f"고객   > {question}")
    trace(out)
    return out


def chat(thread_id=None):
    """대화를 연다. 빈 줄이나 '그만' 을 입력하면 끝난다."""
    from agent import chat_app
    tid = thread_id or f"you-{next(_session)}"
    cfg = {"configurable": {"thread_id": tid}}
    print(f"[대화 {tid}] 문의를 입력하세요. 끝내려면 빈 줄 또는 '그만'.\n")
    while True:
        try:
            q = input("고객   > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n끝냅니다.")
            return
        if not q or q in ("그만", "exit", "quit"):
            break
        trace(chat_app.invoke({"question": q}, cfg))
    said = chat_app.get_state(cfg).values.get("history") or []
    print(f"끝냅니다. 오간 문의 {len(said)}건: {said}")


if __name__ == "__main__":
    ensure_data()
    if len(sys.argv) > 1:
        ask(" ".join(sys.argv[1:]))
    else:
        chat()
