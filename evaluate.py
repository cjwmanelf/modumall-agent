# -*- coding: utf-8 -*-
"""두 지표를 한 번에 잰다.  `python evaluate.py`

    ① 의도 분류 정확도 — 평가셋 120건, 정답 라우트와 대조
    ② 1턴 답변 통과율 — 정답셋 첫 턴 34건, action·tools·must·forbid 네 축

무언가 고쳤으면 이걸 돌려서 숫자가 어디로 움직였는지 보면 된다.
`--only router` / `--only answer` 로 한쪽만 잴 수 있다.
"""
import argparse
import json
import re
import sys

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score

from common import pmap
from config import BASE, CONF_THRESHOLD, LABELS4, ensure_data


# ───────────────────────── ① 의도 분류 ─────────────────────────
def eval_router(report=True):
    from router import app, build, rule_classify

    inq_path = BASE / "eval_set.csv" if (BASE / "eval_set.csv").exists() else (BASE / "customer_inquiries.csv")
    inq = pd.read_csv(inq_path)
    ans = pd.read_csv(BASE / "routing_answers.csv")
    gold = inq.merge(ans, on="qa_id")
    ev = gold[gold["split"] == "eval"].reset_index(drop=True)

    def run(graph, name):
        states = pmap(lambda q: graph.invoke({"question": q}), ev["question"].tolist())
        pred = [s["route"] for s in states]
        y = ev["route"].tolist()
        f1 = f1_score(y, pred, labels=LABELS4, average="macro", zero_division=0)
        acc = accuracy_score(y, pred)
        print(f"[{name}] n={len(ev)}  정확도 {acc:.3f}  macro F1 {f1:.3f}")
        return pred, acc, f1, states

    print("── ① 의도 분류 ─────────────────────────────")
    pred, acc, f1, states = run(app, "LLM 라우터")

    if report:
        print()
        print(classification_report(ev["route"], pred, labels=LABELS4, digits=3, zero_division=0))
        cm = confusion_matrix(ev["route"], pred, labels=LABELS4)
        print("[혼동 행렬] 행=정답, 열=예측")
        print(pd.DataFrame(cm, index=LABELS4, columns=LABELS4).to_string())

        miss = [(r["question"], r["route"], p, s["confidence"])
                for (_, r), p, s in zip(ev.iterrows(), pred, states) if r["route"] != p]
        print(f"\n[오분류 {len(miss)}건] — 여기를 읽는 것이 개선의 출발점이다")
        for q, gold_r, p, conf in miss:
            print(f"  [{gold_r} → {p}] conf={conf:.2f}  {q[:56]}")

    cr_dict = classification_report(ev["route"], pred, labels=LABELS4, digits=3, zero_division=0, output_dict=True)
    cm = confusion_matrix(ev["route"], pred, labels=LABELS4)
    miss = [(r["question"], r["route"], p, s["confidence"])
            for (_, r), p, s in zip(ev.iterrows(), pred, states) if r["route"] != p]

    return {
        "acc": acc,
        "macro_f1": f1,
        "n": len(ev),
        "report_dict": cr_dict,
        "cm": cm.tolist(),
        "labels": list(LABELS4),
        "miss": miss
    }


# ───────────────────────── ② 1턴 답변 ─────────────────────────
AUTO_ACTIONS = {"ANSWER", "ASK", "OUT_OF_SCOPE"}


def norm_num(s):
    return re.sub(r"(?<=\d),(?=\d)", "", str(s))


def score_turn(expect, answer, tools_called, action):
    """한 턴을 채점한다. 반환: (통과 여부, 실패 항목)"""
    fails = []
    a = norm_num(answer)
    if expect["action"] != action:
        fails.append(f'action: 기대 {expect["action"]} != 실제 {action}')
    need = set(expect.get("tools", []))
    if need - set(tools_called):
        fails.append(f'tools 미호출: {sorted(need - set(tools_called))}')
    for m in expect.get("must", []):
        if norm_num(m) not in a:
            fails.append(f'must 누락: "{m}"')
    for f in expect.get("forbid", []):
        if norm_num(f) in a:
            fails.append(f'forbid 위반: "{f}"')
    if expect["action"] == "ASK" and not re.search(r"\?|주시겠|알려주|말씀해", answer):
        fails.append("ASK 인데 되묻는 문장이 아님")
    return (not fails), fails


def load_cases():
    gold_path = BASE / "answer_gold.json" if (BASE / "answer_gold.json").exists() else (BASE / "answer_goldenset_multiturn.json")
    gold = json.loads(gold_path.read_text(encoding="utf-8"))
    cases = []
    for c in gold["conversations"]:
        q = next(t for t in c["turns"] if t["role"] == "customer")
        a = next((t for t in c["turns"] if t.get("expect")), None)
        if a:
            cases.append({"conv_id": c["conv_id"], "question": q["text"],
                          "route": c["route"].split("→")[-1].strip(), "expect": a["expect"]})
    return cases


def eval_answer(report=True):
    from answer import answer_with_tools

    cases = load_cases()

    # 채점기 자체 검증 — 모범 답안은 전부 통과해야 한다. 아니면 채점기가 틀린 것이다.
    bad = [c["conv_id"] for c in cases
           if not score_turn(c["expect"], c["expect"]["reference"],
                             c["expect"].get("tools", []), c["expect"]["action"])[0]]
    print("── ② 1턴 답변 ─────────────────────────────")
    print(f"[채점기 자기 검증] 모범 답안 {len(cases)}건 중 실패 {len(bad)}건 {bad if bad else '✅'}")

    def run_case(case):
        text, results = answer_with_tools(case["question"], case["route"])
        if results.get("get_order_status", {}).get("is_external_channel") or "제조사" in text or "주문하신 사이트" in text:
            action = "OUT_OF_SCOPE"
        elif re.search(r"\?|주시겠|알려주|말씀해|확인해", text) and (not results or "개봉" in text or "지역" in text or "주문번호" in text or "상품명" in text):
            action = "ASK"
        else:
            action = "ANSWER"
        return action, text, list(results)



    scored = [c for c in cases if c["expect"]["action"] in AUTO_ACTIONS]
    outs = pmap(run_case, scored)

    rows = []
    for c, (action, text, tools) in zip(scored, outs):
        ok, fails = score_turn(c["expect"], text, tools, action)
        rows.append({"conv": c["conv_id"], "question": c["question"], "기대": c["expect"]["action"],
                     "실제": action, "ok": ok, "fails": "; ".join(fails), "answer": text})
    res = pd.DataFrame(rows)
    rate = res["ok"].mean()
    print(f'채점 {len(res)}건 / 통과 {res["ok"].sum()}건 ({100 * rate:.1f}%)'
          f'   (자동 판정 불가 {len(cases) - len(scored)}건 제외)')

    action_stats_df = res.groupby("기대")["ok"].agg(["count", "sum", "mean"]).rename(columns={"count": "건수", "sum": "통과", "mean": "통과율"})
    action_cm = pd.crosstab(res["기대"], res["실제"])

    if report:
        print("\n[기대 행동별]")
        print(action_stats_df.to_string())
        print("\n[행동 판정 혼동] 행=기대, 열=실제")
        print(action_cm.to_string())
        kinds = [f.split(":")[0] for s in res.loc[~res["ok"], "fails"] for f in s.split("; ") if f]
        print("\n[실패 유형]")
        print(pd.Series(kinds).value_counts().to_string() if kinds else "  없음")
        print("\n[실패 사례] — 여기를 읽는 것이 개선의 출발점이다")
        for _, r in res[~res["ok"]].iterrows():
            print(f'  {r["conv"]} 기대={r["기대"]} 실제={r["실제"]}  {r["fails"][:80]}')
            print(f'      답변: {r["answer"][:90]}')

    fails_list = []
    for _, r in res[~res["ok"]].iterrows():
        fails_list.append({
            "conv": r["conv"],
            "question": r["question"],
            "expect": r["기대"],
            "actual": r["실제"],
            "fails": r["fails"],
            "answer": r["answer"]
        })

    return {
        "pass_rate": rate,
        "n": len(res),
        "total_cases": len(cases),
        "bad_goldens": bad,
        "action_stats": action_stats_df.to_dict(orient="index"),
        "confusion": action_cm.to_dict(orient="index"),
        "confusion_cols": [str(c) for c in action_cm.columns],
        "confusion_rows": [str(r) for r in action_cm.index],
        "fails": fails_list
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="두 지표를 잰다")
    ap.add_argument("--only", choices=["router", "answer"], help="한쪽만 재기")
    ap.add_argument("--quiet", action="store_true", help="요약만")
    args = ap.parse_args()

    ensure_data()
    out = {}
    if args.only != "answer":
        out["router"] = eval_router(report=not args.quiet)
        print()
    if args.only != "router":
        out["answer"] = eval_answer(report=not args.quiet)

    print("\n══ 요약 ══")
    if "router" in out:
        print(f'  ① 의도 분류   정확도 {out["router"]["acc"]:.3f} · macro F1 {out["router"]["macro_f1"]:.3f}')
    if "answer" in out:
        print(f'  ② 1턴 답변    통과율 {100 * out["answer"]["pass_rate"]:.1f}% ({out["answer"]["n"]}건)')
