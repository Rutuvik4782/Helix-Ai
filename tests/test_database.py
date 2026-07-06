import os
import pytest
from core.config import settings
from core.database import (
    init_db,
    get_migration_rules,
    save_migration_rule,
    save_knowledge_base_example,
    search_knowledge_base,
    save_run,
    get_run,
    list_runs
)
from agents.search_agent import SearchAgent

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    # Override settings.DATABASE_PATH to use a temp db for tests
    old_db_path = settings.DATABASE_PATH
    test_db = str(tmp_path / "test_helix.db")
    settings.DATABASE_PATH = test_db
    init_db()
    yield
    settings.DATABASE_PATH = old_db_path

def test_db_seeding():
    rules = get_migration_rules()
    assert len(rules) > 0
    # check standard rule
    rule_ids = [r["id"] for r in rules]
    assert "print_statement" in rule_ids

def test_custom_rule():
    save_migration_rule({
        "id": "test_rule",
        "pattern": r"\bfoo\b",
        "source_hint": "Legacy Test",
        "message": "Found legacy foo.",
        "replacement": "bar",
        "risk": "LOW"
    })
    rules = get_migration_rules()
    rule_ids = [r["id"] for r in rules]
    assert "test_rule" in rule_ids

def test_knowledge_base_few_shot():
    save_knowledge_base_example("xrange_usage", "xrange(10)", "range(10)", "LOW")
    save_knowledge_base_example("print_statement", "print 'hi'", "print('hi')", "LOW")
    
    results = search_knowledge_base(["xrange_usage", "print_statement"], limit=2)
    assert len(results) == 2
    assert results[0]["pattern_id"] in ("xrange_usage", "print_statement")

@pytest.mark.anyio
async def test_search_agent():
    save_knowledge_base_example("has_key_usage", "d.has_key(k)", "k in d", "MEDIUM")
    agent = SearchAgent()
    examples = await agent.process(["has_key_usage"])
    assert len(examples) == 1
    assert examples[0]["input_code"] == "d.has_key(k)"
    assert examples[0]["output_code"] == "k in d"

def test_run_history():
    run_payload = {
        "run_id": "test_run_123",
        "probable_source_version": "Python 2.x",
        "risk_score": "LOW",
        "legacy_issue_count": 2,
        "validation_success": True,
        "applied_transformations": ["upgrade_print_statement"],
        "original_code": "print 'hi'",
        "diff": "-print 'hi'\n+print('hi')",
        "report": "# Legacy Python Modernization Report\n"
    }
    save_run(run_payload)
    
    run = get_run("test_run_123")
    assert run is not None
    assert run["risk_score"] == "LOW"
    assert run["validation_success"] is True
    assert "upgrade_print_statement" in run["applied_transformations"]
    
    runs = list_runs(limit=10)
    assert len(runs) >= 1
    assert runs[0]["run_id"] == "test_run_123"
