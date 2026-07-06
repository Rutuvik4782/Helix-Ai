import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.config import settings

def get_db_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(settings.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(settings.DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. knowledge_base
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS knowledge_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern_id TEXT NOT NULL,
        input_code TEXT NOT NULL,
        output_code TEXT NOT NULL,
        risk_level TEXT DEFAULT 'LOW',
        success BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 2. migration_rules
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS migration_rules (
        id TEXT PRIMARY KEY,
        pattern TEXT NOT NULL,
        source_hint TEXT NOT NULL,
        message TEXT NOT NULL,
        replacement TEXT NOT NULL,
        risk TEXT DEFAULT 'LOW',
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    # 3. run_history
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS run_history (
        run_id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        source_version TEXT,
        risk_score TEXT,
        legacy_issue_count INTEGER DEFAULT 0,
        validation_success BOOLEAN DEFAULT 0,
        transformations TEXT,
        input_hash TEXT,
        diff TEXT,
        report TEXT
    );
    """)
    
    # Seed initial rules if empty
    cursor.execute("SELECT COUNT(*) as count FROM migration_rules")
    if cursor.fetchone()["count"] == 0:
        initial_rules = [
            {
                "id": "backtick_repr",
                "pattern": r"`[^`\n]+`",
                "source_hint": "Python 1.x/2.x",
                "message": "Backtick repr syntax detected.",
                "replacement": "Replace `expr` with repr(expr).",
                "risk": "MEDIUM"
            },
            {
                "id": "apply_builtin",
                "pattern": r"\bapply\s*\(",
                "source_hint": "Python 1.x/2.x",
                "message": "Legacy apply(...) builtin detected.",
                "replacement": "Rewrite apply(fn, args[, kwargs]) as fn(*args[, **kwargs]).",
                "risk": "MEDIUM"
            },
            {
                "id": "print_statement",
                "pattern": r"^\s*print\s+[^(\n].*$",
                "source_hint": "Python 2.x",
                "message": "Legacy print statement detected.",
                "replacement": "Wrap values with print(...).",
                "risk": "LOW"
            },
            {
                "id": "xrange_usage",
                "pattern": r"\bxrange\s*\(",
                "source_hint": "Python 2.x",
                "message": "xrange is not available in modern Python.",
                "replacement": "Replace xrange(...) with range(...).",
                "risk": "LOW"
            },
            {
                "id": "raw_input_usage",
                "pattern": r"\braw_input\s*\(",
                "source_hint": "Python 2.x",
                "message": "raw_input was renamed in Python 3.",
                "replacement": "Replace raw_input(...) with input(...).",
                "risk": "LOW"
            },
            {
                "id": "except_comma",
                "pattern": r"^\s*except\s+[^:\n]+,\s*[A-Za-z_]\w*\s*:",
                "source_hint": "Python 2.x",
                "message": "Old exception binding syntax detected.",
                "replacement": "Convert except X, e: to except X as e:.",
                "risk": "LOW"
            },
            {
                "id": "not_equal_operator",
                "pattern": r"<>",
                "source_hint": "Python 2.x",
                "message": "Legacy not-equal operator detected.",
                "replacement": "Replace <> with !=.",
                "risk": "LOW"
            },
            {
                "id": "iteritems_usage",
                "pattern": r"\.iteritems\s*\(",
                "source_hint": "Python 2.x",
                "message": "iteritems returns a Python 2 iterator API.",
                "replacement": "Replace iteritems() with items().",
                "risk": "LOW"
            },
            {
                "id": "iterkeys_usage",
                "pattern": r"\.iterkeys\s*\(",
                "source_hint": "Python 2.x",
                "message": "iterkeys returns a Python 2 iterator API.",
                "replacement": "Replace iterkeys() with keys().",
                "risk": "LOW"
            },
            {
                "id": "itervalues_usage",
                "pattern": r"\.itervalues\s*\(",
                "source_hint": "Python 2.x",
                "message": "itervalues returns a Python 2 iterator API.",
                "replacement": "Replace itervalues() with values().",
                "risk": "LOW"
            },
            {
                "id": "has_key_usage",
                "pattern": r"\.has_key\s*\(",
                "source_hint": "Python 2.x",
                "message": "dict.has_key was removed.",
                "replacement": "Rewrite d.has_key(x) as x in d.",
                "risk": "MEDIUM"
            },
            {
                "id": "unicode_type",
                "pattern": r"\bunicode\b",
                "source_hint": "Python 2.x",
                "message": "unicode type detected.",
                "replacement": "Replace unicode with str where compatible.",
                "risk": "MEDIUM"
            },
            {
                "id": "basestring_type",
                "pattern": r"\bbasestring\b",
                "source_hint": "Python 2.x",
                "message": "basestring type detected.",
                "replacement": "Replace basestring with str.",
                "risk": "MEDIUM"
            },
            {
                "id": "long_type",
                "pattern": r"\blong\b",
                "source_hint": "Python 2.x",
                "message": "long type detected.",
                "replacement": "Replace long with int.",
                "risk": "LOW"
            },
            {
                "id": "exec_statement",
                "pattern": r"^\s*exec\s+[^(\n].*$",
                "source_hint": "Python 1.x/2.x",
                "message": "Legacy exec statement detected.",
                "replacement": "Convert exec statement syntax to exec(...).",
                "risk": "HIGH"
            }
        ]
        for rule in initial_rules:
            cursor.execute("""
            INSERT INTO migration_rules (id, pattern, source_hint, message, replacement, risk, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (rule["id"], rule["pattern"], rule["source_hint"], rule["message"], rule["replacement"], rule["risk"]))
            
    conn.commit()
    conn.close()

# Database Helper Functions

def save_migration_rule(rule_dict: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO migration_rules (id, pattern, source_hint, message, replacement, risk, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        rule_dict["id"],
        rule_dict["pattern"],
        rule_dict["source_hint"],
        rule_dict["message"],
        rule_dict["replacement"],
        rule_dict["risk"],
        rule_dict.get("is_active", 1)
    ))
    conn.commit()
    conn.close()

def get_migration_rules() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM migration_rules WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_knowledge_base_example(pattern_id: str, input_code: str, output_code: str, risk_level: str = "LOW"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO knowledge_base (pattern_id, input_code, output_code, risk_level, success)
    VALUES (?, ?, ?, ?, 1)
    """, (pattern_id, input_code, output_code, risk_level))
    conn.commit()
    conn.close()

def search_knowledge_base(pattern_ids: List[str], limit: int = 3) -> List[Dict[str, Any]]:
    if not pattern_ids:
        return []
    conn = get_db_connection()
    cursor = conn.cursor()
    # Build query with placeholders
    placeholders = ",".join(["?"] * len(pattern_ids))
    cursor.execute(f"""
    SELECT pattern_id, input_code, output_code, risk_level
    FROM knowledge_base
    WHERE pattern_id IN ({placeholders}) AND success = 1
    ORDER BY created_at DESC
    LIMIT ?
    """, (*pattern_ids, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def save_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    run_id = payload.get("run_id") or os.urandom(16).hex()
    created_at = payload.get("created_at") or datetime.utcnow().isoformat() + "Z"
    
    transformations = json.dumps(payload.get("applied_transformations", []))
    
    import hashlib
    input_code = payload.get("original_code", "")
    input_hash = hashlib.sha256(input_code.encode("utf-8")).hexdigest()
    
    cursor.execute("""
    INSERT OR REPLACE INTO run_history 
    (run_id, created_at, source_version, risk_score, legacy_issue_count, validation_success, transformations, input_hash, diff, report)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run_id,
        created_at,
        payload.get("probable_source_version"),
        payload.get("risk_score"),
        payload.get("legacy_issue_count", 0),
        1 if payload.get("validation_success") else 0,
        transformations,
        input_hash,
        payload.get("diff", ""),
        payload.get("report", "")
    ))
    conn.commit()
    conn.close()
    
    return {
        "run_id": run_id,
        "created_at": created_at,
        "probable_source_version": payload.get("probable_source_version"),
        "risk_score": payload.get("risk_score"),
        "legacy_issue_count": payload.get("legacy_issue_count", 0),
        "validation_success": payload.get("validation_success"),
        "applied_transformations": payload.get("applied_transformations", []),
        "diff": payload.get("diff", ""),
        "report": payload.get("report", "")
    }

def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM run_history WHERE run_id = ?", (run_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["validation_success"] = bool(d["validation_success"])
    d["applied_transformations"] = json.loads(d["transformations"])
    return d

def list_runs(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT run_id, created_at, source_version as probable_source_version, risk_score, legacy_issue_count, validation_success, transformations
    FROM run_history
    ORDER BY created_at DESC
    LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        d = dict(row)
        d["validation_success"] = bool(d["validation_success"])
        d["applied_transformations"] = json.loads(d["transformations"])
        results.append(d)
    return results
