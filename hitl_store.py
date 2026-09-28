# -*- coding: utf-8 -*-
"""고객 문의 자동 답변 발송 HITL 대기 건 영속 관리 (SQLite Storage)

- 고객 문의 접수 -> AI 답변 초안 생성 -> 발송 직전 위험 건 멈춤(`PENDING`)
- SQLite 데이터베이스(`data/hitl_cases.db`)에 안전하게 영속 보관
- 담당자의 4대 조치(승인 / 수정 후 승인 / 반려 / 다시 판정) 이력 및 감사 로그(Audit)
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import BASE

DB_PATH = BASE / "data" / "hitl_cases.db"


def init_hitl_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        # 기존 스키마에 category 컬럼이 없으면 테이블 재생성
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(hitl_cases)")
        cols = [r[1] for r in cur.fetchall()]
        if cols and "category" not in cols:
            conn.execute("DROP TABLE hitl_cases")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS hitl_cases (
                req_id TEXT PRIMARY KEY,
                thread_id TEXT UNIQUE,
                customer TEXT,
                category TEXT,
                confidence REAL,
                question TEXT,
                ai_draft TEXT,
                cited_policy TEXT,
                stop_reason TEXT,
                impact TEXT,
                status TEXT, -- PENDING, APPROVED, MODIFIED, REJECTED, AUTO_PASSED, REJUDGE
                manager_action TEXT,
                manager_note TEXT,
                final_answer TEXT,
                created_at TEXT,
                resolved_at TEXT,
                extra_json TEXT
            )
        """)
        conn.commit()


def save_or_update_case(case_data: Dict[str, Any]):
    init_hitl_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO hitl_cases (
                req_id, thread_id, customer, category, confidence,
                question, ai_draft, cited_policy, stop_reason, impact,
                status, manager_action, manager_note, final_answer,
                created_at, resolved_at, extra_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(req_id) DO UPDATE SET
                thread_id = excluded.thread_id,
                customer = excluded.customer,
                category = excluded.category,
                confidence = excluded.confidence,
                question = excluded.question,
                ai_draft = excluded.ai_draft,
                cited_policy = excluded.cited_policy,
                stop_reason = excluded.stop_reason,
                impact = excluded.impact,
                status = excluded.status,
                manager_action = excluded.manager_action,
                manager_note = excluded.manager_note,
                final_answer = excluded.final_answer,
                resolved_at = excluded.resolved_at,
                extra_json = excluded.extra_json
        """, (
            case_data.get("req_id"),
            case_data.get("thread_id"),
            case_data.get("customer", "고객"),
            case_data.get("category", "OTHER"),
            case_data.get("confidence", 0.0),
            case_data.get("question", ""),
            case_data.get("ai_draft", ""),
            case_data.get("cited_policy", ""),
            case_data.get("stop_reason", ""),
            case_data.get("impact", "승인 시 고객에게 카카오 알림톡으로 발송됩니다."),
            case_data.get("status", "PENDING"),
            case_data.get("manager_action", ""),
            case_data.get("manager_note", ""),
            case_data.get("final_answer", case_data.get("ai_draft", "")),
            case_data.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            case_data.get("resolved_at", ""),
            json.dumps(case_data.get("extra", {}), ensure_ascii=False)
        ))
        conn.commit()


def get_case(req_id: str) -> Optional[Dict[str, Any]]:
    init_hitl_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM hitl_cases WHERE req_id = ? OR thread_id = ?", (req_id, req_id))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("extra_json"):
            try:
                d["extra"] = json.loads(d["extra_json"])
            except Exception:
                d["extra"] = {}
        return d


def get_pending_cases() -> List[Dict[str, Any]]:
    init_hitl_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM hitl_cases WHERE status = 'PENDING' ORDER BY created_at DESC")
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_history_cases(limit: int = 50) -> List[Dict[str, Any]]:
    init_hitl_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM hitl_cases WHERE status != 'PENDING' ORDER BY resolved_at DESC LIMIT ?", (limit,))
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def resolve_case(req_id: str, action: str, note: str = "",
                 adjusted_text: Optional[str] = None) -> Optional[Dict[str, Any]]:
    case = get_case(req_id)
    if not case:
        return None

    status_map = {
        "approve": "APPROVED",
        "modify_approve": "MODIFIED",
        "reject": "REJECTED",
        "rejudge": "REJUDGE"
    }
    new_status = status_map.get(action, "APPROVED")
    final_ans = adjusted_text if (action == "modify_approve" and adjusted_text) else case.get("ai_draft", "")

    case["status"] = new_status
    case["manager_action"] = action
    case["manager_note"] = note
    case["final_answer"] = final_ans
    case["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_or_update_case(case)
    return case


def reset_and_seed_cs_cases():
    """CS 자동 답변 발송 5대 케이스 시딩 (기존 환불 테이블 마이그레이션)"""
    init_hitl_db()
    from hitl_policy import BENCHMARK_CASES, check_stop_condition

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM hitl_cases")
        conn.commit()

    for item in BENCHMARK_CASES:
        stopped, reason = check_stop_condition(item, rule_type="rule_6")
        status = "PENDING" if stopped else "AUTO_PASSED"
        case_data = {
            "req_id": item["id"],
            "thread_id": f"thread_{item['id']}",
            "customer": item["customer"],
            "category": item["category"],
            "confidence": item["confidence"],
            "question": item["question"],
            "ai_draft": item["ai_draft"],
            "cited_policy": item.get("cited_policy", ""),
            "stop_reason": reason if stopped else "안전 발송 기준 충족",
            "impact": f"고객({item['customer']}님)의 카카오톡으로 해당 답변이 즉시 발송됩니다." if stopped else "자동 검수 통과 즉시 발송 완료",
            "status": status,
            "manager_action": "auto_pass" if not stopped else "",
            "manager_note": "기준 충족 자동 발송" if not stopped else "",
            "final_answer": item["ai_draft"],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S") if not stopped else ""
        }
        save_or_update_case(case_data)


# 초기화 및 시딩
init_hitl_db()
reset_and_seed_cs_cases()
