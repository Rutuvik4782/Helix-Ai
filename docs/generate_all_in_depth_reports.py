from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
PDF_DIR = DOCS_DIR / "pdfs"


@dataclass
class Section:
    heading: str
    simple: str
    deep_points: list[str] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)
    equations: list[str] = field(default_factory=list)
    code_refs: list[str] = field(default_factory=list)


@dataclass
class ReportSpec:
    filename: str
    title: str
    subtitle: str
    objective: str
    kpis: list[tuple[str, str]]
    sections: list[Section]
    viva: list[tuple[str, str]]


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def count_nonempty_lines(path: Path) -> int:
    text = safe_read(path)
    return sum(1 for line in text.splitlines() if line.strip())


def count_ast_nodes(path: Path) -> tuple[int, int]:
    text = safe_read(path)
    if not text:
        return 0, 0
    try:
        tree = ast.parse(text)
    except Exception:
        return 0, 0
    fn_count = sum(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        for node in ast.walk(tree)
    )
    class_count = sum(isinstance(node, ast.ClassDef) for node in ast.walk(tree))
    return fn_count, class_count


def parse_unittest_summary(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    combined = (stdout or "") + "\n" + (stderr or "")
    ran_match = re.search(r"Ran\s+(\d+)\s+tests?", combined)
    failed_match = re.search(r"FAILED\s+\(([^)]+)\)", combined)
    ok_match = re.search(r"\nOK\b", combined)

    ran = int(ran_match.group(1)) if ran_match else 0
    status = "unknown"
    detail = ""
    if ok_match and returncode == 0:
        status = "pass"
    elif failed_match:
        status = "fail"
        detail = failed_match.group(1)
    elif returncode != 0:
        status = "fail"
        detail = "non-zero exit code"

    return {
        "status": status,
        "ran": ran,
        "detail": detail,
        "returncode": returncode,
        "tail": "\n".join(combined.strip().splitlines()[-20:]),
    }


def run_unittests() -> dict[str, Any]:
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=240,
        )
        return parse_unittest_summary(result.stdout, result.stderr, result.returncode)
    except Exception as exc:
        return {
            "status": "error",
            "ran": 0,
            "detail": str(exc),
            "returncode": 1,
            "tail": str(exc),
        }


def run_eval_benchmark() -> dict[str, Any]:
    command = [sys.executable, "ml/evaluate_modernizer.py"]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
            timeout=180,
        )
        payload = json.loads(result.stdout)
        return {
            "benchmark_size": int(payload.get("benchmark_size", 0)),
            "rule_pass": int(payload.get("rule_pass", 0)),
            "ml_pass": payload.get("ml_pass"),
            "details": payload.get("details", []),
        }
    except Exception as exc:
        return {
            "benchmark_size": 0,
            "rule_pass": 0,
            "ml_pass": None,
            "details": [],
            "error": str(exc),
        }


def collect_snapshot() -> dict[str, Any]:
    backend_files = [ROOT / "main.py"] + sorted((ROOT / "agents").glob("*.py")) + sorted((ROOT / "core").glob("*.py"))
    test_files = sorted((ROOT / "tests").glob("test_*.py"))
    frontend_files = [
        ROOT / "templates" / "index.html",
        ROOT / "templates" / "new.html",
        ROOT / "static" / "js" / "app.js",
        ROOT / "static" / "css" / "styles.css",
    ]

    backend_loc = sum(count_nonempty_lines(path) for path in backend_files if path.exists())
    frontend_loc = sum(count_nonempty_lines(path) for path in frontend_files if path.exists())
    test_loc = sum(count_nonempty_lines(path) for path in test_files if path.exists())

    fn_count = 0
    class_count = 0
    for path in backend_files + test_files:
        fns, classes = count_ast_nodes(path)
        fn_count += fns
        class_count += classes

    analyzer_src = safe_read(ROOT / "agents" / "analyzer.py")
    execution_src = safe_read(ROOT / "core" / "execution.py")
    main_src = safe_read(ROOT / "main.py")
    app_src = safe_read(ROOT / "static" / "js" / "app.js")

    legacy_block_match = re.search(
        r"LEGACY_RULES\s*=\s*\[(.*?)\]\s*\n\nHIGH_RISK_PATTERNS",
        analyzer_src,
        flags=re.DOTALL,
    )
    legacy_rule_count = (
        len(re.findall(r'"id"\s*:\s*"', legacy_block_match.group(1)))
        if legacy_block_match
        else 0
    )
    high_risk_count = len(re.findall(r'"risk"\s*:\s*"HIGH"', analyzer_src))
    transform_rule_count = len(re.findall(r'if\s+op\s*==\s*"[^"]+"', execution_src))
    endpoint_count = len(re.findall(r"@app\.(?:get|post|put|delete|patch)\(", main_src))
    sample_button_count = len(re.findall(r'class="sampleBtn', safe_read(ROOT / "templates" / "index.html")))
    ui_tab_count = len(re.findall(r'id="(?:reviewTab|diffTab|outputTab|reportTab)"', safe_read(ROOT / "templates" / "index.html")))
    js_function_count = len(re.findall(r"function\s+[A-Za-z_]\w*\(", app_src))
    test_case_count = 0
    for path in test_files:
        test_case_count += len(re.findall(r"def\s+test_[A-Za-z_0-9]+\(", safe_read(path)))

    run_history_path = ROOT / "data" / "modernization_runs.jsonl"
    run_history_count = 0
    if run_history_path.exists():
        run_history_count = sum(1 for line in safe_read(run_history_path).splitlines() if line.strip())

    return {
        "backend_files": len([p for p in backend_files if p.exists()]),
        "frontend_files": len([p for p in frontend_files if p.exists()]),
        "test_files": len([p for p in test_files if p.exists()]),
        "backend_loc": backend_loc,
        "frontend_loc": frontend_loc,
        "test_loc": test_loc,
        "function_count": fn_count,
        "class_count": class_count,
        "legacy_rule_count": legacy_rule_count,
        "high_risk_count": high_risk_count,
        "transform_rule_count": transform_rule_count,
        "endpoint_count": endpoint_count,
        "sample_button_count": sample_button_count,
        "ui_tab_count": ui_tab_count,
        "js_function_count": js_function_count,
        "test_case_count": test_case_count,
        "run_history_count": run_history_count,
    }


def maybe_page_count(path: Path) -> int:
    try:
        from pypdf import PdfReader  # type: ignore

        return len(PdfReader(str(path)).pages)
    except Exception:
        try:
            data = path.read_bytes()
            return len(re.findall(rb"/Type\s*/Page\b", data))
        except Exception:
            return 0


def build_styles():
    base = getSampleStyleSheet()

    title = ParagraphStyle(
        "TitleX",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=28,
        leading=33,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=10,
    )
    subtitle = ParagraphStyle(
        "SubtitleX",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=12,
        leading=17,
        textColor=colors.HexColor("#334155"),
        spaceAfter=10,
    )
    h1 = ParagraphStyle(
        "H1X",
        parent=base["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=21,
        textColor=colors.HexColor("#0b1f4d"),
        spaceBefore=6,
        spaceAfter=6,
    )
    h2 = ParagraphStyle(
        "H2X",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=17,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=4,
        spaceAfter=3,
    )
    body = ParagraphStyle(
        "BodyX",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15.5,
        textColor=colors.HexColor("#111827"),
        spaceAfter=4,
    )
    label = ParagraphStyle(
        "LabelX",
        parent=base["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=6,
        spaceAfter=2,
        uppercase=True,
    )
    bullet = ParagraphStyle(
        "BulletX",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        leftIndent=12,
        firstLineIndent=0,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=2,
    )
    mono = ParagraphStyle(
        "MonoX",
        parent=base["Code"],
        fontName="Courier",
        fontSize=8.8,
        leading=11.5,
        textColor=colors.HexColor("#0f172a"),
    )
    mono_small = ParagraphStyle(
        "MonoSmallX",
        parent=base["Code"],
        fontName="Courier",
        fontSize=8.1,
        leading=10.4,
        textColor=colors.HexColor("#0f172a"),
    )
    return {
        "title": title,
        "subtitle": subtitle,
        "h1": h1,
        "h2": h2,
        "body": body,
        "label": label,
        "bullet": bullet,
        "mono": mono,
        "mono_small": mono_small,
    }


def p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def add_bullets(story: list[Any], bullets: list[str], styles: dict[str, ParagraphStyle]) -> None:
    for line in bullets:
        story.append(Paragraph(escape(f"- {line}"), styles["bullet"]))


def report_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(1.8 * cm, 1.2 * cm, "Helix AI In-Depth Documentation Pack")
    canvas.drawRightString(A4[0] - 1.8 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.restoreState()


def topic_key(spec: ReportSpec) -> str:
    filename = spec.filename.upper()
    if "IDEA_AND_PROBLEM" in filename:
        return "idea"
    if "AGENTIC_ARCHITECTURE" in filename:
        return "agentic"
    if "BACKEND_CODE" in filename:
        return "backend"
    if "FRONTEND_UI" in filename:
        return "frontend"
    if "MATHEMATICAL_MODEL" in filename:
        return "math"
    if "TESTING_EVALUATION" in filename:
        return "testing"
    if "COMPETITIVE_POSITIONING" in filename:
        return "positioning"
    return "general"


def topic_seed_points(topic: str) -> list[str]:
    seeds = {
        "idea": [
            "legacy migration pain points",
            "why modernization breaks at runtime",
            "scope definition and boundary setting",
            "why deterministic systems build trust",
            "how diff-first review reduces risk",
            "what success metrics should look like",
            "how students can deliver practical systems",
            "how architecture supports future scaling",
            "how to communicate limits honestly",
            "how to prioritize roadmap tasks",
            "how to explain hybrid ML + rules",
            "how to defend project value in viva",
        ],
        "agentic": [
            "agent role isolation",
            "contract-first stage outputs",
            "risk-aware orchestration order",
            "planner and critic interaction",
            "execution authority and validation authority",
            "status visibility and observability",
            "run history and traceability",
            "model-assisted side channel design",
            "blocked mode and restricted mode handling",
            "schema evolution strategy",
            "future queue-based scaling path",
            "agentic governance and safety policy",
        ],
        "backend": [
            "FastAPI structure and route boundaries",
            "request and response model consistency",
            "analysis endpoint behavior",
            "refactor endpoint behavior",
            "execution transform implementation style",
            "validation gate design",
            "report generation structure",
            "run persistence and retrieval",
            "config and environment management",
            "error handling conventions",
            "testability and module boundaries",
            "backend roadmap with measurable milestones",
        ],
        "frontend": [
            "single-page workflow rationale",
            "information hierarchy and layout",
            "editor and results dual-panel strategy",
            "primary action button state model",
            "tab rendering and result transparency",
            "run history interaction pattern",
            "keyboard shortcuts and speed",
            "hover and motion behavior",
            "responsiveness and mobile fallback",
            "error feedback and user trust",
            "accessibility improvements roadmap",
            "frontend instrumentation roadmap",
        ],
        "math": [
            "scoring model explainability",
            "complexity proxy model meaning",
            "critic base score and penalties",
            "planner ranking formula",
            "deterministic sorting behavior",
            "validation boolean acceptance model",
            "benchmark pass-rate interpretation",
            "error-rate analysis",
            "confidence calibration basics",
            "threshold policy by transform type",
            "data mixture weighting implications",
            "measurement discipline for claims",
        ],
        "testing": [
            "test pyramid for this project",
            "pipeline functional test strategy",
            "API contract test strategy",
            "dataset and evaluator checks",
            "failure-path test importance",
            "benchmark interpretation limits",
            "regression prevention workflow",
            "quality gate setup",
            "traceability of test evidence",
            "report regeneration discipline",
            "coverage expansion roadmap",
            "CI-focused delivery hardening",
        ],
        "positioning": [
            "specialization versus generality",
            "criteria selection fairness",
            "weighting model transparency",
            "where Helix is stronger",
            "where general tools are stronger",
            "how to present balanced comparisons",
            "adoption path in real teams",
            "evidence-driven messaging",
            "risk-aware value proposition",
            "roadmap credibility signals",
            "market-fit articulation",
            "defensible strategic narrative",
        ],
    }
    return seeds.get(topic, seeds["idea"])


def topic_labs(topic: str) -> list[tuple[str, str, list[str]]]:
    base = [
        (
            "Lab 1: Baseline Input Audit",
            "Start from a legacy snippet and identify exactly what will break on modern Python.",
            [
                "Collect one legacy input sample.",
                "Run /analyze and record issue ids.",
                "Classify each issue as syntax or semantic risk.",
                "Write one paragraph on expected modernization output.",
            ],
        ),
        (
            "Lab 2: Analyze Output Interpretation",
            "Understand how analysis payload maps to later planner and execution actions.",
            [
                "Inspect probable_source_version and mode.",
                "Read legacy_issues list line by line.",
                "Map each issue id to a suggestion id.",
                "Explain why some items should become warning.",
            ],
        ),
        (
            "Lab 3: Critic + Planner Trace",
            "Trace how safety score and priority become selected_plans.",
            [
                "Run analyze output through critique logic.",
                "Compute final score manually for two suggestions.",
                "Verify execution order in planner output.",
                "Compare manual and program outputs.",
            ],
        ),
        (
            "Lab 4: Execution and Diff Review",
            "Run modernization and inspect unified diff before applying changes.",
            [
                "Execute /refactor on sample input.",
                "Inspect added and removed lines.",
                "Confirm each line links to a planned transform.",
                "Document one risky change for manual review.",
            ],
        ),
        (
            "Lab 5: Validation Failure Drill",
            "Learn fail-closed behavior by forcing a leftover-legacy construct.",
            [
                "Create code where one legacy construct remains.",
                "Run validation and capture failure stage.",
                "Explain rollback behavior and user impact.",
                "Fix rule and rerun to green state.",
            ],
        ),
        (
            "Lab 6: Run History and Reproducibility",
            "Use run history to prove the pipeline is auditable and repeatable.",
            [
                "Generate at least two runs with different inputs.",
                "Use /runs and /runs/{id} endpoints.",
                "Re-open one run in UI and inspect report tab.",
                "Write traceability summary notes.",
            ],
        ),
        (
            "Lab 7: Topic-Specific Deep Task",
            f"Perform a deeper exercise related to {topic} concerns and document engineering tradeoffs.",
            [
                "Choose one module strongly tied to this topic.",
                "Read code and summarize control flow.",
                "List strengths, risks, and missing checks.",
                "Propose one measurable improvement.",
            ],
        ),
        (
            "Lab 8: Evaluation and Evidence Pack",
            "Prepare evidence artifacts you can use in submission and viva.",
            [
                "Run tests and benchmark script.",
                "Capture summary metrics and limitations.",
                "Align report claims with actual metrics.",
                "Store outputs in a clean docs folder.",
            ],
        ),
        (
            "Lab 9: Explain to Beginner",
            "Re-explain one complex part in simple words without losing correctness.",
            [
                "Pick one algorithmic decision.",
                "Write a beginner explanation in 8 lines.",
                "Write an expert explanation in 8 lines.",
                "Ensure both versions match same truth.",
            ],
        ),
        (
            "Lab 10: Full Demo Rehearsal",
            "Do complete end-to-end dry run as if in final presentation.",
            [
                "Start server and open UI.",
                "Run one safe case and one warning case.",
                "Show diff, report, and run history.",
                "Conclude with roadmap and limitations.",
            ],
        ),
    ]
    return base


def topic_troubleshooting(topic: str) -> list[tuple[str, str, str]]:
    topic_note = {
        "idea": "scope definitions and positioning statements",
        "agentic": "stage contracts and ordering logic",
        "backend": "endpoint flow and transformation handlers",
        "frontend": "state rendering and UI action flow",
        "math": "scoring formula and thresholds",
        "testing": "test fixtures and assertions",
        "positioning": "comparison criteria and evidence narration",
    }.get(topic, "core workflow")
    return [
        ("Analysis returns no issues unexpectedly", "Input pattern not covered by rules", "Add/adjust analyzer rule and unit test."),
        ("Planner selects zero actions", "Suggestions became NOOP or filtered by status", "Inspect suggestion ids, critique map, and planner filters."),
        ("Validation fails after execution", "Legacy leftovers or syntax problems remain", "Inspect failure stage and patch transform logic."),
        ("Diff looks confusing to users", "Output formatting or context lines are unclear", "Improve diff rendering and report hints."),
        ("Run history missing expected data", "RunStore payload fields not persisted", "Verify run payload contract in save_run call."),
        ("ML shows unavailable", "Adapter path missing or model disabled", "Check env flags and adapter directory path."),
        ("UI button state feels wrong", "State machine and action label out of sync", "Trace state.primaryAction transitions."),
        ("Performance slows on large input", "Heavy rendering or repeated processing", "Paginate rendering and profile hot paths."),
        ("Benchmarks look too optimistic", "Benchmark set too small or narrow", "Expand dataset and stratify by pattern type."),
        ("Viva answers feel weak", "No concrete evidence references", "Quote tests, benchmark numbers, and code paths."),
        (f"Topic-specific confusion in {topic_note}", "Concept not tied to concrete file and flow", "Add diagram plus file-level walkthrough."),
        ("Claims sound exaggerated", "Scope and limitations not stated", "Add explicit limitations and roadmap stages."),
    ]


def topic_glossary(topic: str) -> list[tuple[str, str]]:
    common = [
        ("Legacy Pattern", "An old syntax or API usage from earlier Python versions."),
        ("Modernization", "Converting legacy code to current Python-compatible code."),
        ("Deterministic", "Same input always gives same output."),
        ("Semantic Risk", "Code may still run but behavior could change."),
        ("Validation Gate", "Final checks that decide pass or rollback."),
        ("Diff-First Review", "Inspect exact changes before applying to editor."),
        ("Analyzer", "Stage that detects issues and risk indicators."),
        ("Suggester", "Stage that maps detected issues to upgrades."),
        ("Critic", "Stage that assigns safety scores and warnings."),
        ("Planner", "Stage that chooses execution order."),
        ("Execution Core", "Stage that applies selected transforms."),
        ("RunStore", "Persistence layer for run history records."),
        ("LOCA (LOC)", "Lines of code metric for rough project size."),
        ("Benchmark", "Set of test cases used to measure pass rate."),
        ("Smoke Test", "Small test set for quick health verification."),
        ("Rollback", "Revert to original code when validation fails."),
        ("Adapter", "LoRA fine-tuned parameter delta for base model."),
        ("Base Model", "Original pretrained model used before fine-tuning."),
        ("Confidence", "Estimated reliability signal for a suggestion."),
        ("Traceability", "Ability to explain what changed and why."),
    ]
    topic_specific = {
        "idea": [
            ("Problem Framing", "How the project problem is defined and bounded."),
            ("Scope Boundary", "What the current version supports and excludes."),
            ("Roadmap", "Planned future increments with measurable outcomes."),
            ("Value Proposition", "Main benefit the project offers to users."),
            ("Feasibility", "Whether project goals match available resources."),
        ],
        "agentic": [
            ("Agent Contract", "Structured input/output schema between stages."),
            ("Orchestration", "Coordinating stage execution in correct order."),
            ("Mode SAFE/RESTRICTED/BLOCKED", "Risk-level operating states from analyzer."),
            ("Candidate Plan", "Potential transform item before final selection."),
            ("Authority Model", "Who decides final output acceptance."),
        ],
        "backend": [
            ("Endpoint Contract", "Expected request and response fields for API."),
            ("Idempotent", "Operation that can repeat without new side effects."),
            ("Schema Stability", "Keeping response shape consistent across updates."),
            ("Guard Clause", "Early return for invalid or unsafe state."),
            ("Service Layer", "Modules that hold business logic outside routes."),
        ],
        "frontend": [
            ("State Store", "Central object holding UI workflow data."),
            ("Render Function", "Function that converts state into visible UI."),
            ("Primary Action", "Main CTA button behavior by workflow phase."),
            ("Progressive Disclosure", "Show details only when user needs them."),
            ("Interaction Latency", "Delay felt between action and UI response."),
        ],
        "math": [
            ("Score Function", "Formula used to rank migration actions."),
            ("Penalty Term", "Value subtracted for risk conditions."),
            ("Threshold", "Minimum value needed to auto-apply safely."),
            ("Calibration", "Adjusting confidence to match real error rates."),
            ("Error Rate", "Fraction of cases that fail expected checks."),
        ],
        "testing": [
            ("Fixture", "Controlled sample input used in tests."),
            ("Assertion", "Condition that test expects to be true."),
            ("Regression", "Previously fixed behavior breaking again."),
            ("Coverage Gap", "Important behavior not yet tested."),
            ("Quality Gate", "Required checks before release."),
        ],
        "positioning": [
            ("Competitive Axis", "Criterion used to compare tools."),
            ("Weighted Score", "Composite metric based on criterion weights."),
            ("Scope Honesty", "Accurate claims aligned with actual capability."),
            ("Adoption Path", "How teams can onboard tool progressively."),
            ("Differentiator", "Capability that makes product distinct."),
        ],
    }
    return common + topic_specific.get(topic, [])


def topic_extended_qa(topic: str) -> list[tuple[str, str]]:
    common = [
        ("What is the core goal of this report?", "To explain this topic from beginner level to implementation depth with real project evidence."),
        ("How should I present this in viva?", "Start with simple explanation, then show one concrete code path, then show one metric and one limitation."),
        ("How do I avoid vague answers?", "Always tie statements to file paths, endpoints, tests, or measured outputs."),
        ("What if evaluator asks about limitations?", "Answer directly and show roadmap with near-term measurable upgrades."),
        ("How do I show project credibility?", "Use deterministic workflow, validation behavior, and test/benchmark evidence."),
        ("Why use simple language in technical docs?", "It improves clarity and comprehension without reducing technical correctness."),
        ("How should I practice this topic?", "Run one lab task, inspect code, and explain output in your own words."),
        ("How does this topic connect to full system?", "Each topic is one layer of the same end-to-end modernization pipeline."),
    ]
    topic_q = {
        "idea": [
            ("How is this problem relevant in real world?", "Many teams still maintain old scripts and internal tools that fail on modern Python runtimes."),
            ("Why not solve every Python version edge case now?", "Breadth-first support without validation depth would reduce reliability for a student project."),
            ("What is your crisp one-line vision?", "Safe, transparent, and practical modernization for legacy Python code."),
        ],
        "agentic": [
            ("Why separate analyzer and execution?", "Detection and rewriting have different responsibilities and failure modes."),
            ("How does the planner add value?", "It imposes deterministic order and allows risk-aware selection."),
            ("Can agents be distributed later?", "Yes, contracts are already explicit enough for queue-based scaling."),
        ],
        "backend": [
            ("What is the most critical backend path?", "The /refactor route because it executes full guarded pipeline and returns final artifacts."),
            ("How do you keep backend maintainable?", "By isolating concerns into modules and keeping response contracts stable."),
            ("What is first backend improvement you would do?", "Add more AST-based transforms where regex is fragile."),
        ],
        "frontend": [
            ("Why keep input and results on same page?", "It reduces context switching and makes diff review faster."),
            ("How do keyboard shortcuts help?", "They speed up demo and expert workflows."),
            ("What frontend risk remains?", "Large-file rendering and complexity can grow without careful UX constraints."),
        ],
        "math": [
            ("Why not use complex models immediately?", "Simple formulas are easier to verify and defend in reliability-focused migration."),
            ("What formula is most important?", "The final planner score and the validation accept/reject boolean gate."),
            ("What is next mathematically?", "Confidence calibration and per-transform threshold tuning."),
        ],
        "testing": [
            ("What does passing tests guarantee?", "Core expected behaviors are preserved for tested patterns, not universal correctness for all code."),
            ("Why still need manual review?", "Semantic edge cases can exist beyond current test coverage."),
            ("What test upgrade is highest impact?", "Pattern-level benchmark expansion with failure category tracking."),
        ],
        "positioning": [
            ("How do you compare fairly with bigger tools?", "Use migration-specific criteria and clearly acknowledge where general tools are stronger."),
            ("What is your strongest comparative message?", "Predictable modernization with visible validation and audit trail."),
            ("What makes positioning credible?", "Balanced claims, measurable evidence, and explicit limitations."),
        ],
    }
    return common + topic_q.get(topic, [])


def topic_code_excerpts(topic: str) -> list[tuple[str, Path, int, int]]:
    profiles: dict[str, list[tuple[str, Path, int, int]]] = {
        "idea": [
            ("Core API Flow", ROOT / "main.py", 1, 120),
            ("Analyzer Rules", ROOT / "agents" / "analyzer.py", 1, 140),
            ("Validation Gate", ROOT / "core" / "validation.py", 1, 130),
        ],
        "agentic": [
            ("Analyzer Stage", ROOT / "agents" / "analyzer.py", 1, 130),
            ("Suggester Stage", ROOT / "agents" / "suggester.py", 1, 130),
            ("Planner + Critic Stage", ROOT / "agents" / "planner.py", 1, 90),
            ("Orchestration", ROOT / "main.py", 180, 290),
        ],
        "backend": [
            ("API + Pipeline", ROOT / "main.py", 1, 160),
            ("Execution Core", ROOT / "core" / "execution.py", 1, 150),
            ("Validation Core", ROOT / "core" / "validation.py", 1, 140),
            ("Run Store + Reporting", ROOT / "core" / "run_store.py", 1, 90),
        ],
        "frontend": [
            ("Inner Page Structure", ROOT / "templates" / "index.html", 1, 140),
            ("UI State Machine Part 1", ROOT / "static" / "js" / "app.js", 1, 150),
            ("UI State Machine Part 2", ROOT / "static" / "js" / "app.js", 261, 370),
        ],
        "math": [
            ("Analyzer Complexity Logic", ROOT / "agents" / "analyzer.py", 130, 210),
            ("Critic + Planner Score Logic", ROOT / "agents" / "critic.py", 1, 100),
            ("Validation Decision Logic", ROOT / "core" / "validation.py", 1, 120),
            ("Benchmark Evaluator", ROOT / "ml" / "evaluate_modernizer.py", 1, 120),
        ],
        "testing": [
            ("Pipeline Tests", ROOT / "tests" / "test_pipeline.py", 1, 170),
            ("API Tests", ROOT / "tests" / "test_api.py", 1, 140),
            ("ML Asset + Evaluator", ROOT / "tests" / "test_ml_assets.py", 1, 120),
            ("Orchestration Context", ROOT / "main.py", 180, 280),
        ],
        "positioning": [
            ("Comparison Visual Pack Generator", ROOT / "docs" / "generate_4ai_visual_pack.py", 1, 180),
            ("Project README Positioning Context", ROOT / "README.md", 1, 140),
            ("Architecture + Manifest Context", ROOT / "docs" / "ARCHITECTURE.md", 1, 120),
        ],
    }
    return profiles.get(topic, profiles["idea"])


def infer_module_role(path: Path) -> str:
    pth = str(path).replace("\\", "/")
    if pth.endswith("/main.py"):
        return "API orchestration and full modernization flow control"
    if "/agents/" in pth and "analyzer.py" in pth:
        return "legacy pattern detection and risk mode assignment"
    if "/agents/" in pth and "suggester.py" in pth:
        return "issue-to-transform mapping and confidence metadata"
    if "/agents/" in pth and "critic.py" in pth:
        return "safety scoring and warning classification"
    if "/agents/" in pth and "planner.py" in pth:
        return "execution ordering and transform selection"
    if "/core/" in pth and "execution.py" in pth:
        return "deterministic modernization rewrite engine"
    if "/core/" in pth and "validation.py" in pth:
        return "validation gate and rollback decision logic"
    if "/core/" in pth and "run_store.py" in pth:
        return "run persistence and retrieval contracts"
    if "/core/" in pth and "report_generator.py" in pth:
        return "human-readable modernization report composition"
    if "/core/" in pth and "ml_reasoner.py" in pth:
        return "optional model-assisted modernization pathway"
    if "/static/js/" in pth:
        return "frontend state machine and user interaction handling"
    if "/templates/" in pth:
        return "UI structure and screen information hierarchy"
    if "/ml/" in pth and "evaluate" in pth:
        return "benchmark evaluation and evidence generation"
    if "/ml/" in pth:
        return "ML data/training/inference support logic"
    if "/tests/" in pth:
        return "automated regression and contract verification"
    return "project implementation logic"


def excerpt_features(snippet: list[str]) -> dict[str, Any]:
    raw = "\n".join(snippet)
    fn_names = re.findall(r"def\s+([A-Za-z_]\w*)\s*\(", raw)
    async_fn_names = re.findall(r"async\s+def\s+([A-Za-z_]\w*)\s*\(", raw)
    class_names = re.findall(r"class\s+([A-Za-z_]\w*)\s*[:(]", raw)
    decorators = re.findall(r"^\s*@([A-Za-z_][\w\.]*)", raw, flags=re.MULTILINE)
    endpoint_decorators = [d for d in decorators if d.startswith("app.")]
    regex_usage = bool(re.search(r"\bre\.(?:compile|sub|search|finditer)\b", raw))
    ast_usage = bool(re.search(r"\bast\.", raw))
    warning_terms = len(re.findall(r"\bwarning\b|\brisk\b|\bblocked\b", raw, flags=re.IGNORECASE))
    return {
        "fn_names": fn_names,
        "async_fn_names": async_fn_names,
        "class_names": class_names,
        "endpoint_decorators": endpoint_decorators,
        "regex_usage": regex_usage,
        "ast_usage": ast_usage,
        "warning_terms": warning_terms,
    }


def add_code_explained_excerpt(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    title: str,
    path: Path,
    start: int,
    end: int,
) -> None:
    text = safe_read(path)
    if not text.strip():
        return
    lines = text.splitlines()
    s = max(1, start)
    e = min(len(lines), end)
    snippet_lines = [lines[i - 1] for i in range(s, e + 1)]
    numbered = [f"{i:04d}: {lines[i-1]}" for i in range(s, e + 1)]

    role = infer_module_role(path)
    feats = excerpt_features(snippet_lines)
    fn_preview = feats["fn_names"][:4] + feats["async_fn_names"][:4]

    story.append(p(title, styles["h2"]))
    story.append(p(f"File: {path}", styles["body"]))
    story.append(
        p(
            f"Simple explanation: this block handles {role}. It is an important piece in the from-input to validated-output workflow.",
            styles["body"],
        )
    )
    story.append(p("Technical explanation:", styles["body"]))
    detail_lines = [
        f"Detected in this excerpt: functions={len(feats['fn_names']) + len(feats['async_fn_names'])}, classes={len(feats['class_names'])}, endpoint decorators={len(feats['endpoint_decorators'])}.",
        "This code should be read as part of a contract chain: what it receives, what it returns, and how the next stage depends on it.",
    ]
    if fn_preview:
        detail_lines.append(f"Key function names to read first: {', '.join(fn_preview)}.")
    if feats["endpoint_decorators"]:
        detail_lines.append(f"Endpoint decorators in excerpt: {', '.join(feats['endpoint_decorators'][:5])}.")
    if feats["regex_usage"]:
        detail_lines.append("Regex operations are present, so edge-case pattern handling should be tested carefully.")
    if feats["ast_usage"]:
        detail_lines.append("AST usage is present, indicating structured syntax analysis/validation behavior.")
    if feats["warning_terms"] > 0:
        detail_lines.append("Risk/warning language exists in this block, so it affects safety signaling.")
    add_bullets(story, detail_lines, styles)

    story.append(p("Why this matters:", styles["body"]))
    add_bullets(
        story,
        [
            "If this module fails, pipeline reliability drops immediately.",
            "Changes in this block should always be paired with targeted tests.",
            "When presenting in viva, mention one metric and one limitation tied to this code.",
        ],
        styles,
    )

    story.append(p("Code excerpt:", styles["body"]))
    story.append(Preformatted("\n".join(numbered), styles["mono_small"]))


def add_extended_content(
    story: list[Any],
    styles: dict[str, ParagraphStyle],
    spec: ReportSpec,
    snapshot: dict[str, Any],
    unit_summary: dict[str, Any],
    eval_summary: dict[str, Any],
) -> None:
    topic = topic_key(spec)
    seeds = topic_seed_points(topic)
    labs = topic_labs(topic)
    issues = topic_troubleshooting(topic)
    glossary = topic_glossary(topic)
    qa = topic_extended_qa(topic)
    excerpts = topic_code_excerpts(topic)

    story.append(PageBreak())
    story.append(p("From Scratch Learning Track", styles["h1"]))
    story.append(
        p(
            "This chapter is written for beginners first. Each module starts with very simple meaning, then engineering depth, then practical action.",
            styles["body"],
        )
    )

    for i, seed in enumerate(seeds, start=1):
        story.append(p(f"Module {i}: {seed.title()}", styles["h2"]))
        story.append(
            p(
                f"Simple view: {seed} explains one important part of this topic in plain language. If this part is weak, the whole workflow becomes harder to trust or harder to explain.",
                styles["body"],
            )
        )
        story.append(
            p(
                f"Deep view: in this project, {seed} connects to concrete modules, endpoint contracts, and validation behavior. A good explanation should reference both logic and evidence.",
                styles["body"],
            )
        )
        story.append(
            p(
                f"Project evidence tie-in: backend LOC={snapshot['backend_loc']}, frontend LOC={snapshot['frontend_loc']}, transforms={snapshot['transform_rule_count']}, tests={unit_summary.get('ran', 0)}.",
                styles["body"],
            )
        )
        add_bullets(
            story,
            [
                "Write this concept in your own 5-line explanation.",
                "Map this concept to one file and one function.",
                "Run one command or endpoint that demonstrates it.",
                "State one current limitation and one improvement idea.",
            ],
            styles,
        )
        story.append(Spacer(1, 0.12 * cm))
        if i % 4 == 0 and i != len(seeds):
            story.append(PageBreak())

    story.append(PageBreak())
    story.append(p("Hands-On Practical Labs", styles["h1"]))
    for i, (title, goal, steps) in enumerate(labs, start=1):
        story.append(p(f"{i}. {title}", styles["h2"]))
        story.append(p(goal, styles["body"]))
        add_bullets(story, steps, styles)
        story.append(
            p(
                "Expected output: produce notes with input, observed output, interpretation, and one risk/next-action line.",
                styles["body"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        if i % 3 == 0 and i != len(labs):
            story.append(PageBreak())

    story.append(PageBreak())
    story.append(p("Troubleshooting Playbook", styles["h1"]))
    trouble_table_data = [["Issue", "Likely Cause", "How To Fix"]]
    for issue, cause, fix in issues:
        trouble_table_data.append([issue, cause, fix])
    trouble_table = Table(trouble_table_data, colWidths=[5.1 * cm, 5.0 * cm, 5.5 * cm], repeatRows=1)
    trouble_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b1f4d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.3),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#94a3b8")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.HexColor("#eef2ff")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(trouble_table)

    story.append(PageBreak())
    story.append(p("Glossary (Simple Words, Technical Meaning)", styles["h1"]))
    for i, (term, meaning) in enumerate(glossary, start=1):
        story.append(p(f"{i}. {term}", styles["h2"]))
        story.append(p(meaning, styles["body"]))
        if i % 10 == 0 and i != len(glossary):
            story.append(PageBreak())

    story.append(PageBreak())
    story.append(p("Extended Viva and Interview Q&A", styles["h1"]))
    for i, (question, answer) in enumerate(qa, start=1):
        story.append(p(f"Q{i}: {question}", styles["h2"]))
        story.append(p(answer, styles["body"]))
        story.append(
            p(
                "How to answer strongly: begin simple, cite one file/path evidence, cite one metric, then mention one limitation.",
                styles["body"],
            )
        )
        story.append(Spacer(1, 0.08 * cm))
        if i % 5 == 0 and i != len(qa):
            story.append(PageBreak())

    story.append(PageBreak())
    story.append(p("Code Walkthrough Appendix (With Explanation)", styles["h1"]))
    story.append(
        p(
            "This appendix connects explanation to real files. Each excerpt includes simple-language meaning, technical interpretation, and why it matters before showing code lines.",
            styles["body"],
        )
    )
    for i, (title, path, start, end) in enumerate(excerpts, start=1):
        add_code_explained_excerpt(story, styles, f"Excerpt {i}: {title}", path, start, end)
        if i != len(excerpts):
            story.append(PageBreak())


def build_story(
    spec: ReportSpec,
    snapshot: dict[str, Any],
    unit_summary: dict[str, Any],
    eval_summary: dict[str, Any],
    extra_pages: int = 0,
) -> list[Any]:
    styles = build_styles()
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    story: list[Any] = []
    story.append(p(spec.title, styles["title"]))
    story.append(p(spec.subtitle, styles["subtitle"]))
    story.append(Spacer(1, 0.2 * cm))
    story.append(p(f"Generated: {generated_at}", styles["body"]))
    story.append(p(spec.objective, styles["body"]))
    story.append(Spacer(1, 0.2 * cm))

    summary_table_data = [["Project Snapshot", "Value"]]
    summary_table_data.extend(spec.kpis)
    summary_table_data.extend(
        [
            ["Backend LOC", str(snapshot["backend_loc"])],
            ["Frontend LOC", str(snapshot["frontend_loc"])],
            ["Test LOC", str(snapshot["test_loc"])],
            ["Detected endpoints", str(snapshot["endpoint_count"])],
            ["Migration transform rules", str(snapshot["transform_rule_count"])],
            ["Rule benchmark pass", f"{eval_summary.get('rule_pass', 0)}/{eval_summary.get('benchmark_size', 0)}"],
            ["Unit test status", f"{unit_summary.get('status')} ({unit_summary.get('ran')} tests)"],
        ]
    )
    table = Table(summary_table_data, colWidths=[7.4 * cm, 8.2 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b1f4d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#94a3b8")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.HexColor("#eef2ff")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.25 * cm))
    story.append(
        p(
            "How to read this document: each section starts with a simple explanation, then a deeper engineering explanation, then a practical checklist.",
            styles["body"],
        )
    )
    story.append(PageBreak())

    for idx, section in enumerate(spec.sections, start=1):
        story.append(p(section.heading, styles["h1"]))
        story.append(p("Simple Explanation", styles["label"]))
        story.append(p(section.simple, styles["body"]))

        if section.deep_points:
            story.append(p("Deep Explanation", styles["label"]))
            for point in section.deep_points:
                story.append(p(point, styles["body"]))

        if section.checklist:
            story.append(p("Practical Checklist", styles["label"]))
            add_bullets(story, section.checklist, styles)

        if section.equations:
            story.append(p("Formulas", styles["label"]))
            story.append(Preformatted("\n".join(section.equations), styles["mono"]))

        if section.code_refs:
            story.append(p("Code References", styles["label"]))
            story.append(Preformatted("\n".join(section.code_refs), styles["mono"]))

        story.append(Spacer(1, 0.18 * cm))
        if idx % 3 == 0 and idx != len(spec.sections):
            story.append(PageBreak())

    story.append(PageBreak())
    story.append(p("Viva Quick Answers", styles["h1"]))
    for question, answer in spec.viva:
        story.append(p(f"Q: {question}", styles["label"]))
        story.append(p(answer, styles["body"]))
        story.append(Spacer(1, 0.1 * cm))

    add_extended_content(story, styles, spec, snapshot, unit_summary, eval_summary)

    for i in range(extra_pages):
        story.append(PageBreak())
        story.append(p(f"Extended Deep-Dive Practice Page {i + 1}", styles["h1"]))
        story.append(
            p(
                "This page is part of the deep-learning appendix to keep this report fully in-depth. Use it to practice one complete trace: issue detection -> suggestion -> critique -> planning -> execution -> validation -> report.",
                styles["body"],
            )
        )
        add_bullets(
            story,
            [
                "Pick one real legacy input and annotate each pipeline stage output.",
                "Write one beginner explanation and one technical explanation for the same result.",
                "List exactly where deterministic behavior is guaranteed.",
                "List one limitation and one mitigation plan.",
                "State which metric would prove this part improved in next iteration.",
            ],
            styles,
        )
        story.append(
            p(
                "Instructor note: this practice format helps convert passive reading into active understanding for viva and implementation work.",
                styles["body"],
            )
        )

    return story


def build_specs(snapshot: dict[str, Any], unit_summary: dict[str, Any], eval_summary: dict[str, Any]) -> list[ReportSpec]:
    eval_size = int(eval_summary.get("benchmark_size", 0))
    eval_pass = int(eval_summary.get("rule_pass", 0))
    eval_ratio = (eval_pass / eval_size * 100.0) if eval_size else 0.0
    unit_status = unit_summary.get("status", "unknown")
    unit_ran = unit_summary.get("ran", 0)

    idea_sections = [
        Section(
            heading="0. Project Idea in 60 Seconds",
            simple="In simple words: Helix AI takes old Python code, finds outdated syntax, upgrades what is safe, and asks for review where behavior can change.",
            deep_points=[
                "This project is focused and practical: legacy modernization, not full general-purpose refactoring.",
                f"The active backend currently exposes {snapshot['endpoint_count']} API routes to support analyze, modernize, run history, health, and model-status flows.",
                "The architecture keeps deterministic rules as the source of truth and treats ML as an optional assistant.",
            ],
            checklist=[
                "Say the goal as old-to-modern migration with safety gates.",
                "Explain that diff-first review is a core product decision.",
                "Mention that unsupported or risky semantics are flagged, not silently auto-fixed.",
            ],
            code_refs=[
                "main.py",
                "core/execution.py",
                "core/validation.py",
            ],
        ),
        Section(
            heading="1. Problem Definition",
            simple="In simple words: old Python code breaks on modern runtimes because keywords, builtins, and APIs changed.",
            deep_points=[
                f"Analyzer currently tracks around {snapshot['legacy_rule_count']} explicit legacy syntax/API patterns and classifies high-risk semantics separately.",
                "Examples include print statement syntax, xrange/raw_input, dict iterator APIs, has_key, backtick repr, and apply builtin usage.",
                "A migration tool must separate syntax conversion from behavior-sensitive conversion.",
            ],
            checklist=[
                "Differentiate syntax breakages vs semantic breakages.",
                "Call out string/bytes and division behavior as high review areas.",
                "Show that issue detection is explicit and testable.",
            ],
            code_refs=["agents/analyzer.py"],
        ),
        Section(
            heading="2. Why Existing Generic Tools Are Not Enough",
            simple="In simple words: general AI coding tools are good at broad coding, but they are not always deterministic for migration safety.",
            deep_points=[
                "Helix AI optimizes for repeatability: same input should produce predictable transforms and transparent risk reports.",
                "The planner and validator enforce a guarded path; this is different from free-form generation-only workflows.",
                "The run history API enables auditability for educational and engineering reviews.",
            ],
            checklist=[
                "Position Helix as specialized, not universally superior.",
                "Use deterministic + validation as your key differentiator.",
                "Always mention traceable diffs and run logs.",
            ],
            code_refs=["core/run_store.py", "core/report_generator.py"],
        ),
        Section(
            heading="3. Scope and Boundaries",
            simple="In simple words: this version strongly targets Python 2.x and selected Python 1-era constructs; it does not promise perfect migration for every historical edge case.",
            deep_points=[
                "The project intentionally prioritizes high-frequency legacy constructs seen in real educational or maintenance scenarios.",
                "Unsupported complex migrations are surfaced via warnings and validation failures, which keeps the product honest and safer.",
                "This boundary-first design makes the system deliverable for a student project while still technically credible.",
            ],
            checklist=[
                "Be explicit about what is supported now.",
                "Use roadmap language for broader Python-version coverage.",
                "Avoid claiming 100 percent automatic migration for every file.",
            ],
            code_refs=["README.md", "docs/ARCHITECTURE.md"],
        ),
        Section(
            heading="4. Success Criteria",
            simple="In simple words: success means safe upgrades, clear diffs, and no silent breakage.",
            deep_points=[
                f"Current benchmark script reports rule pass {eval_pass}/{eval_size} ({eval_ratio:.1f} percent) on the bundled benchmark set.",
                f"Unit test suite currently reports status '{unit_status}' over {unit_ran} discovered tests in this environment.",
                "Human review experience is measured by clarity: issue list, planned transforms, diff tab, output tab, and report tab.",
            ],
            checklist=[
                "Track pass rate, warning rate, and manual-edit rate.",
                "Track validation failures by category.",
                "Track turnaround time from paste to reviewed diff.",
            ],
            code_refs=["ml/evaluate_modernizer.py", "tests/test_pipeline.py", "tests/test_api.py"],
        ),
        Section(
            heading="5. Hybrid ML + Rule Strategy",
            simple="In simple words: ML can suggest and rank, but rules and validation decide what is accepted.",
            deep_points=[
                "The ML reasoner is optional and environment-driven; core modernization remains available even with ML disabled.",
                "This architecture protects reliability in low-resource or no-GPU environments.",
                "Adapter-based inference enables future improvements without rewriting the main API layer.",
            ],
            checklist=[
                "Treat ML as a confidence booster, not an uncontrolled executor.",
                "Keep deterministic fallback always active.",
                "Expose model status in API and UI for transparency.",
            ],
            code_refs=["core/ml_reasoner.py", "core/config.py", "main.py"],
        ),
        Section(
            heading="6. Risk and Governance",
            simple="In simple words: do not auto-apply risky semantic changes without explicit visibility.",
            deep_points=[
                f"Analyzer currently flags at least {snapshot['high_risk_count']} high-risk classes plus medium-risk semantic areas.",
                "Validation blocks output when legacy patterns remain or migrated code becomes syntactically invalid.",
                "A run record stores context for debugging and project defense.",
            ],
            checklist=[
                "Never hide warnings from the user.",
                "Fail closed when validation fails.",
                "Keep run logs for reproducibility.",
            ],
            code_refs=["agents/analyzer.py", "core/validation.py", "core/run_store.py"],
        ),
        Section(
            heading="7. Roadmap",
            simple="In simple words: next steps are broader pattern coverage, stronger ML ranking, and larger evaluation sets.",
            deep_points=[
                "Near-term technical upgrades include richer AST-based transforms for complex expressions and function signatures.",
                "Medium-term upgrades include larger benchmark pools and mutation tests for semantic regression detection.",
                "Long-term work includes automated repository-level migration planning with dependency-aware ordering.",
            ],
            checklist=[
                "Keep roadmap split into near, medium, long term.",
                "Tie each roadmap item to a measurable KPI.",
                "Preserve deterministic safety baseline through all upgrades.",
            ],
            code_refs=["docs/VIVA_NOTES.md", "docs/PROJECT_ABSTRACT.md"],
        ),
    ]

    architecture_sections = [
        Section(
            heading="0. Agentic Pipeline at a Glance",
            simple="In simple words: Analyzer finds issues, Suggester proposes fixes, Critic scores risk, Planner orders actions, Execution applies, Validation checks, Report explains.",
            deep_points=[
                "The pipeline is sequential by design to keep state transitions easy to reason about and debug.",
                "Each stage emits structured data that the next stage can consume without hidden side effects.",
                "The architecture aligns with your original diagram while tightening contracts between stages.",
            ],
            checklist=[
                "Explain each stage in one sentence.",
                "Emphasize explicit hand-off data.",
                "Mention that report and diff close the loop.",
            ],
            code_refs=[
                "agents/analyzer.py",
                "agents/suggester.py",
                "agents/critic.py",
                "agents/planner.py",
                "core/execution.py",
                "core/validation.py",
                "core/report_generator.py",
            ],
        ),
        Section(
            heading="1. Agent Responsibilities (Detailed)",
            simple="In simple words: each agent has one job, so errors are easier to isolate.",
            deep_points=[
                "Analyzer: pattern detection, source-version hinting, risk mode assignment, and lightweight complexity estimate.",
                "Suggester: deterministic mapping from issue id to actionable transform candidate.",
                "Critic: safety score and warning state based on transform type and confidence.",
                "Planner: final execution ordering based on priority and safety score.",
            ],
            checklist=[
                "Keep single-responsibility boundaries.",
                "Avoid mixing transformation logic into analysis stage.",
                "Avoid direct code edits outside execution core.",
            ],
            code_refs=[
                "agents/analyzer.py",
                "agents/suggester.py",
                "agents/critic.py",
                "agents/planner.py",
            ],
        ),
        Section(
            heading="2. Data Contracts Between Agents",
            simple="In simple words: every stage returns JSON-like structured objects.",
            deep_points=[
                "Analyzer output includes success flag, probable source version, issue list, risk score, mode, and semantic risk set.",
                "Suggester output is a list of normalized suggestion records with id, type, confidence, priority, line, and reasoning.",
                "Critic output is a list of per-suggestion statuses and safety scores.",
                "Planner output includes selected_plans and candidates for traceability.",
            ],
            checklist=[
                "Keep field names stable across versions.",
                "Default missing lists to empty lists, not null.",
                "Log schema mismatches quickly during integration.",
            ],
            code_refs=["main.py", "agents/*.py"],
        ),
        Section(
            heading="3. Orchestration and Control Flow",
            simple="In simple words: API endpoint /refactor is the orchestrator that runs the full chain end-to-end.",
            deep_points=[
                "The orchestrator first analyzes, then plans, then executes, then validates, then stores run data and returns result payload.",
                "If validation fails, rollback to original code is enforced before response.",
                "If ML is available, it runs as auxiliary output and does not override deterministic final code.",
            ],
            checklist=[
                "Preserve rollback on validation failure.",
                "Keep ML branch side-effect free on deterministic code path.",
                "Always include logs and diff in response.",
            ],
            code_refs=["main.py"],
        ),
        Section(
            heading="4. Safety Layers",
            simple="In simple words: safety is not a single check; it is multiple guardrails in sequence.",
            deep_points=[
                "Layer 1: analyzer risk modes include SAFE, RESTRICTED, BLOCKED.",
                "Layer 2: critic reduces scores for semantic and low-confidence changes.",
                "Layer 3: validation reparses Python and checks leftover legacy patterns.",
                "Layer 4: behavior checks ensure key function names are not accidentally removed.",
            ],
            checklist=[
                "Design for fail-closed behavior.",
                "Require explicit user review for warning-heavy runs.",
                "Store warnings in run records.",
            ],
            code_refs=["agents/analyzer.py", "agents/critic.py", "core/validation.py"],
        ),
        Section(
            heading="5. ML Placement in Agentic Architecture",
            simple="In simple words: ML is a helper brain, not the only brain.",
            deep_points=[
                "Reasoner availability is environment controlled and visible to user through /model-status.",
                "ML inference uses adapter path + base model and can produce a side-channel modernization draft.",
                "Final production-safe output remains the validated deterministic output unless you intentionally redesign the authority model.",
            ],
            checklist=[
                "Use ML for ranking and fallback suggestions first.",
                "Avoid giving ML direct write authority over accepted output.",
                "Gate ML outputs through same validator in future extensions.",
            ],
            code_refs=["core/ml_reasoner.py", "main.py"],
        ),
        Section(
            heading="6. State, Persistence, and Observability",
            simple="In simple words: each run is saved with enough data to replay and audit what happened.",
            deep_points=[
                f"Run store currently has {snapshot['run_history_count']} persisted records in the local history file (count can grow during usage).",
                "Saved fields include original/new code, analysis, validation, applied transforms, diff, and report text.",
                "This enables a simple but effective audit trail for demo, viva, and debugging.",
            ],
            checklist=[
                "Keep run payload complete enough for debugging.",
                "Limit run list endpoint output to summary fields for UI performance.",
                "Provide run detail endpoint for deep inspection.",
            ],
            code_refs=["core/run_store.py", "main.py"],
        ),
        Section(
            heading="7. Scale and Future Agent Evolution",
            simple="In simple words: if usage grows, separate agent steps into workers while preserving current contracts.",
            deep_points=[
                "Current in-process orchestration is ideal for prototype speed and low operational overhead.",
                "Future architecture can split into queue-based workers for analyzer/planner/execution with the same message schema.",
                "Versioned schemas should be introduced before distributed execution to avoid drift.",
            ],
            checklist=[
                "Stabilize schema before scaling architecture.",
                "Add structured event logs for each stage.",
                "Keep deterministic stage idempotent for retries.",
            ],
            code_refs=["docs/ARCHITECTURE.md"],
        ),
    ]

    backend_sections = [
        Section(
            heading="0. Backend Structure Overview",
            simple="In simple words: main.py wires all agents and cores, while each module handles one concern.",
            deep_points=[
                f"Backend currently spans {snapshot['backend_files']} core Python files with about {snapshot['backend_loc']} non-empty lines.",
                f"Code analysis finds roughly {snapshot['function_count']} functions and {snapshot['class_count']} classes in backend + tests.",
                "This modular shape makes it straightforward to explain and extend in academic defense.",
            ],
            checklist=[
                "Keep module boundaries clear.",
                "Avoid business logic in route handlers where possible.",
                "Preserve pure helper functions for testability.",
            ],
            code_refs=["main.py", "agents/", "core/"],
        ),
        Section(
            heading="1. API Design",
            simple="In simple words: the API has dedicated routes for health, model status, analysis, refactor, and run history.",
            deep_points=[
                "GET /health and GET /model-status provide operations visibility.",
                "POST /analyze provides non-destructive planning output.",
                "POST /refactor executes guarded modernization and returns diff/report.",
                "GET /runs and GET /runs/{id} support run timeline UX.",
            ],
            checklist=[
                "Keep analyze and refactor separate for user trust.",
                "Return consistent JSON structures.",
                "Use proper HTTP errors for missing runs or failures.",
            ],
            code_refs=["main.py"],
        ),
        Section(
            heading="2. Analyzer Internals",
            simple="In simple words: analyzer uses explicit regex rules and small AST checks to detect legacy patterns quickly.",
            deep_points=[
                f"Current analyzer holds around {snapshot['legacy_rule_count']} legacy-pattern rules and risk mode escalation logic.",
                "Source version inference is evidence-based: issue hints determine whether input looks like Python 1/2 or Python 3.",
                "The analyzer also emits semantic risk signals for division and text/bytes boundaries.",
            ],
            checklist=[
                "Keep every rule documented with id and replacement hint.",
                "Prefer transparent rules over hidden heuristics for first release.",
                "Add new rules with paired tests.",
            ],
            code_refs=["agents/analyzer.py"],
        ),
        Section(
            heading="3. Suggestion, Critique, Planning",
            simple="In simple words: suggestion maps issue to action, critic scores risk, planner decides execution order.",
            deep_points=[
                "Suggestion mapping uses a deterministic issue-to-suggestion table with confidence and priority values.",
                "Critic applies type-based base score and penalties for semantic or low-confidence operations.",
                "Planner computes final score = safety_score + max(0, 50 - priority), then sorts by order and score.",
            ],
            equations=[
                "final_score = critique_safety_score + max(0, 50 - suggestion_priority)",
                "selected_plan = candidate where suggestion_type != 'NOOP'",
            ],
            checklist=[
                "Keep scoring function simple and explainable.",
                "Use warning status to surface review needs.",
                "Preserve deterministic sort order for repeatability.",
            ],
            code_refs=["agents/suggester.py", "agents/critic.py", "agents/planner.py"],
        ),
        Section(
            heading="4. Execution Core",
            simple="In simple words: execution applies only known transforms, one by one, using explicit rule ids.",
            deep_points=[
                f"The execution core currently includes {snapshot['transform_rule_count']} explicit transformation branches.",
                "Most transforms are regex-based; some (print/exec/apply/backticks) use dedicated helper methods.",
                "Sequential application allows ordered rewrites and predictable diff output.",
            ],
            checklist=[
                "Never run unknown transform ids.",
                "Prefer idempotent rewrite functions when possible.",
                "Keep special cases as helper methods, not giant regex.",
            ],
            code_refs=["core/execution.py"],
        ),
        Section(
            heading="5. Validation Core",
            simple="In simple words: validation is the final gate that decides pass or rollback.",
            deep_points=[
                "Validation stages: syntax parse, leftover-legacy lint checks, and behavior checks.",
                "Syntax parse prevents invalid output from being accepted.",
                "Legacy remainder patterns prevent partial migration from silently passing.",
                "Behavior check compares function-name sets between original and migrated code.",
            ],
            checklist=[
                "Block output if syntax fails.",
                "Block output if leftover legacy constructs remain.",
                "Return warnings for manual semantic review areas.",
            ],
            code_refs=["core/validation.py"],
        ),
        Section(
            heading="6. Report + Run Persistence",
            simple="In simple words: every run can be inspected later with report, diff, and metadata.",
            deep_points=[
                "Report generator produces a markdown report with analysis, planned transformations, semantic risks, and validation summary.",
                "Run store writes JSONL records for append-only history and quick retrieval.",
                "This supports evidence-based demos and debugging sessions.",
            ],
            checklist=[
                "Keep report content human-readable.",
                "Avoid storing only aggregate numbers; keep context too.",
                "Use run ids as stable references.",
            ],
            code_refs=["core/report_generator.py", "core/run_store.py"],
        ),
        Section(
            heading="7. ML Runtime Integration",
            simple="In simple words: ML path can be enabled with environment variables and adapter files, without breaking deterministic path.",
            deep_points=[
                "Model status and availability are visible in API responses and health checks.",
                "If adapter path is missing, system gracefully reports unavailable ML instead of crashing pipeline.",
                "Inference prompt is explicit and constrained to code modernization task.",
            ],
            checklist=[
                "Keep ML dependencies optional.",
                "Always expose model status for debugging.",
                "Treat ML output as auxiliary unless validated.",
            ],
            code_refs=["core/config.py", "core/ml_reasoner.py"],
        ),
        Section(
            heading="8. Backend Improvement Plan",
            simple="In simple words: next backend upgrades are stronger AST rewrites, richer metrics, and CI checks.",
            deep_points=[
                "Add AST-level transforms for complex patterns to reduce regex false positives.",
                "Add per-stage latency metrics and warning counters.",
                "Integrate pre-commit linting and CI test execution for faster regression detection.",
            ],
            checklist=[
                "Prioritize correctness before adding transform count.",
                "Instrument each stage for observability.",
                "Keep backward-compatible API responses.",
            ],
            code_refs=["tests/", "core/", "agents/"],
        ),
    ]

    frontend_sections = [
        Section(
            heading="0. Frontend Philosophy",
            simple="In simple words: keep the user on one page, show clear steps, and never hide risky changes.",
            deep_points=[
                f"Frontend currently uses {snapshot['frontend_files']} key files with around {snapshot['frontend_loc']} non-empty lines.",
                "The UI is designed around a guided flow: analyze, review, modernize, validate.",
                "The layout keeps input editor and result panel side by side for immediate comparison.",
            ],
            checklist=[
                "Keep one-screen workflow for focus.",
                "Always show next action guidance.",
                "Do not replace input automatically without consent.",
            ],
            code_refs=["templates/index.html", "static/js/app.js", "static/css/styles.css"],
        ),
        Section(
            heading="1. Screen Architecture",
            simple="In simple words: header for context, step strip for progress, editor on left, result tabs on right.",
            deep_points=[
                "Header communicates project identity and mode/status badges.",
                "Step cards represent state transitions with active, done, and warning visual semantics.",
                "Result area includes review, diff, output, and report tabs for layered inspection.",
            ],
            checklist=[
                "Make status badges obvious at glance.",
                "Keep critical actions near editor context.",
                "Limit cognitive load by progressive disclosure.",
            ],
            code_refs=["templates/index.html"],
        ),
        Section(
            heading="2. Interaction Flow",
            simple="In simple words: user pastes code, analyzes, sees findings, then chooses to modernize.",
            deep_points=[
                "Primary action button changes label and behavior by state: Analyze Code, Modernize Code, Apply Output.",
                "Keyboard shortcut Cmd/Ctrl + Enter triggers next primary action.",
                "Sample snippet buttons reduce friction in demos and viva presentations.",
            ],
            checklist=[
                "Preserve deterministic button state machine.",
                "Keep keyboard shortcuts discoverable.",
                "Provide sample snippets for fast walkthroughs.",
            ],
            code_refs=["static/js/app.js"],
        ),
        Section(
            heading="3. State Management",
            simple="In simple words: a single JavaScript state object tracks code, analysis, plan, diff, report, and logs.",
            deep_points=[
                "State fields include originalCode/newCode/diff/report/runId plus agent outputs.",
                "Rendering functions (renderReview/renderDiff/renderOutput/renderReport) read state and update panels.",
                "This central state model avoids scattered DOM-only logic.",
            ],
            checklist=[
                "Keep state schema explicit.",
                "Update state before rendering.",
                "Avoid hidden side effects inside renderers.",
            ],
            code_refs=["static/js/app.js"],
        ),
        Section(
            heading="4. Diff-First UX",
            simple="In simple words: users inspect changes first, then apply to editor only if they accept them.",
            deep_points=[
                "Diff panel uses visual line classes for added/removed/meta lines.",
                "Output and report remain available without forcing immediate overwrite of editor input.",
                "This reduces accidental acceptance of unsafe changes.",
            ],
            checklist=[
                "Show diff before apply.",
                "Keep apply action explicit and reversible via rerun.",
                "Include warning text when validation is not fully clean.",
            ],
            code_refs=["templates/index.html", "static/js/app.js"],
        ),
        Section(
            heading="5. Run History UX",
            simple="In simple words: recent runs are clickable so users can re-open previous modernization reports quickly.",
            deep_points=[
                "UI fetches summarized runs then lazy-loads full details when a run is clicked.",
                "Loaded runs repopulate review/diff/output/report panels without modifying current editor text unless user applies.",
                "This interaction supports iterative experimentation safely.",
            ],
            checklist=[
                "Keep history item compact and scannable.",
                "Display validation status per run.",
                "Load full run on click, not upfront.",
            ],
            code_refs=["static/js/app.js", "core/run_store.py"],
        ),
        Section(
            heading="6. Accessibility and Responsiveness",
            simple="In simple words: UI should still be understandable on smaller screens and keyboard-first usage.",
            deep_points=[
                "Layout degrades from dual-column desktop to stacked mobile flow through responsive classes.",
                "Interactive controls are keyboard reachable and tab sequences are predictable.",
                "Reduced-motion media queries are included to lower animation intensity where needed.",
            ],
            checklist=[
                "Validate with keyboard-only navigation.",
                "Keep text contrast high in dark theme.",
                "Ensure action labels remain clear on mobile widths.",
            ],
            code_refs=["templates/index.html"],
        ),
        Section(
            heading="7. Frontend Maturity Plan",
            simple="In simple words: next UX upgrades are guided walkthroughs, inline explanations, and visual analytics.",
            deep_points=[
                "Add contextual explanation popovers for each detected legacy pattern.",
                "Add per-transform confidence badges directly in review cards.",
                "Add lightweight performance telemetry to detect slow API calls and large-code rendering issues.",
            ],
            checklist=[
                "Prioritize clarity over visual novelty.",
                "Keep API error handling user-friendly.",
                "Preserve current clean single-page mental model.",
            ],
            code_refs=["templates/index.html", "static/js/app.js"],
        ),
    ]

    math_sections = [
        Section(
            heading="0. Why a Mathematical Model Matters",
            simple="In simple words: math makes decisions explainable, consistent, and testable.",
            deep_points=[
                "Helix uses explicit scoring and thresholding logic rather than opaque end-to-end generation.",
                "This enables deterministic behavior and easier academic defense.",
                "Each score in the pipeline is traceable to code-level rules and confidence values.",
            ],
            checklist=[
                "Keep formulas simple enough to explain on whiteboard.",
                "Tie each formula to one code location.",
                "Avoid hidden weights without rationale.",
            ],
        ),
        Section(
            heading="1. Analyzer Complexity Metric",
            simple="In simple words: complexity is approximated by counting control-flow nodes in AST plus a base value.",
            deep_points=[
                "The analyzer starts at complexity = 1 and increments for If, For, While, ExceptHandler, With, and Try nodes.",
                "This is not a full cyclomatic complexity implementation, but a practical complexity proxy.",
                "The metric supports triage and report readability.",
            ],
            equations=[
                "complexity = 1 + count(If, For, While, ExceptHandler, With, Try in AST)",
            ],
            checklist=[
                "State clearly this is a proxy metric.",
                "Do not over-claim static-analysis precision.",
                "Use it for trend and triage, not absolute code quality.",
            ],
            code_refs=["agents/analyzer.py"],
        ),
        Section(
            heading="2. Critic Safety Score",
            simple="In simple words: each suggestion gets a base score by type, then penalties are applied for risk signals.",
            deep_points=[
                "Base score table encodes trust in transform categories: syntax and API are usually safer than semantic rewrites.",
                "Penalty for semantic upgrade and low confidence forces additional caution.",
                "Status is marked WARNING when caution is needed.",
            ],
            equations=[
                "safety_score = TYPE_BASE_SCORE[type] - semantic_penalty - confidence_penalty",
                "semantic_penalty = 10 if type == 'SEMANTIC_UPGRADE' else 0",
                "confidence_penalty = 5 if confidence < 0.9 else 0",
            ],
            checklist=[
                "Keep penalty values documented.",
                "Tune using benchmark errors, not intuition only.",
                "Preserve lower bound at zero.",
            ],
            code_refs=["agents/critic.py"],
        ),
        Section(
            heading="3. Planner Final Score and Ordering",
            simple="In simple words: planner combines safety with priority to decide execution sequence.",
            deep_points=[
                "Priority comes from suggestion metadata; lower priority number means earlier execution intent.",
                "Final score adds a bounded priority boost to safety score.",
                "Candidates are sorted by execution order, then score, then line number for deterministic tie-breaking.",
            ],
            equations=[
                "priority_boost = max(0, 50 - priority)",
                "final_score = critique_safety_score + priority_boost",
                "sort_key = (execution_order, -final_score, line_number)",
            ],
            checklist=[
                "Use deterministic sort keys.",
                "Separate selection logic from scoring logic.",
                "Document why NOOP is filtered from selected_plans.",
            ],
            code_refs=["agents/planner.py"],
        ),
        Section(
            heading="4. Validation Decision Function",
            simple="In simple words: output passes only if syntax, lint-legacy, and behavior checks all pass.",
            deep_points=[
                "Validation runs as a staged gate where first failure exits early with stage-specific error.",
                "Legacy remainder regex set functions as a strict residual detector.",
                "Behavior check currently verifies function-name preservation and emits warning for sensitive type migrations.",
            ],
            equations=[
                "valid = syntax_pass AND lint_pass AND behavior_pass",
                "if not valid => rollback to original input",
            ],
            checklist=[
                "Expose failure stage in API response.",
                "Keep warning list separate from hard failures.",
                "Treat rollback as required safety behavior.",
            ],
            code_refs=["core/validation.py", "main.py"],
        ),
        Section(
            heading="5. Benchmark and Pass-Rate Metrics",
            simple="In simple words: benchmark score tells us how often modernization output meets expected checks.",
            deep_points=[
                f"Current local evaluation snapshot reports {eval_pass}/{eval_size} rule-pass cases, equivalent to {eval_ratio:.1f} percent.",
                "This is a small benchmark and should be treated as smoke-test evidence, not full statistical proof.",
                "Use larger and stratified benchmark sets for stronger claims.",
            ],
            equations=[
                "rule_pass_rate = rule_pass / benchmark_size",
                "error_rate = 1 - rule_pass_rate",
            ],
            checklist=[
                "Always report dataset size with pass rate.",
                "Avoid headline metrics without context.",
                "Track failure categories, not just totals.",
            ],
            code_refs=["ml/evaluate_modernizer.py"],
        ),
        Section(
            heading="6. Data Mixture Weighting (ML Pipeline)",
            simple="In simple words: training mixture combines curated modernization data and public sources with controlled weights.",
            deep_points=[
                "Weighted mixture prevents model from drifting too far into unrelated coding styles.",
                "Task-fit data should dominate over generic code corpus for transformation accuracy.",
                "Weight updates should follow evaluation findings.",
            ],
            equations=[
                "mixture = w1*curated_modernization + w2*repair_pairs + w3*reasoning_data",
                "sum(wi) = 1",
            ],
            checklist=[
                "Start with task-fit-heavy weights.",
                "Change one weight group at a time during experiments.",
                "Record config with every training run.",
            ],
            code_refs=["ml/build_training_mixture.py", "ml/train_modernizer_unsloth.py"],
        ),
        Section(
            heading="7. Confidence Calibration Roadmap",
            simple="In simple words: future model should estimate how certain each change is, and unsafe low-confidence outputs should be downgraded.",
            deep_points=[
                "Confidence can be calibrated against validation failures and benchmark mismatches.",
                "Planner can use calibrated confidence for dynamic thresholds per transform type.",
                "This improves selective automation while preserving trust.",
            ],
            equations=[
                "calibrated_confidence = f(raw_confidence, historical_error_rate, transform_type)",
                "auto_apply_allowed if calibrated_confidence >= threshold[type]",
            ],
            checklist=[
                "Collect calibration data continuously.",
                "Use separate thresholds for syntax vs semantic transforms.",
                "Document confidence interpretation for users.",
            ],
        ),
    ]

    testing_sections = [
        Section(
            heading="0. Test Strategy in Simple Terms",
            simple="In simple words: we test the pipeline logic, API behavior, and ML assets separately so failures are easier to diagnose.",
            deep_points=[
                f"Current tests include about {snapshot['test_case_count']} explicit test methods across {snapshot['test_files']} test files.",
                "Pipeline tests verify end-to-end transformation correctness on representative legacy snippets.",
                "API tests ensure route contracts and response fields remain stable.",
            ],
            checklist=[
                "Keep tests grouped by concern.",
                "Prefer deterministic fixtures.",
                "Verify both success and failure paths.",
            ],
            code_refs=["tests/test_pipeline.py", "tests/test_api.py", "tests/test_ml_assets.py"],
        ),
        Section(
            heading="1. Pipeline Unit Tests",
            simple="In simple words: these tests check if old patterns are detected, transformed, and validated correctly.",
            deep_points=[
                "A core sample verifies modernization of print/xrange/has_key/raw_input in one flow.",
                "A very-old sample verifies backtick repr and apply builtin handling for Python 1-era style.",
                "Validation failure tests verify that leftover legacy constructs are rejected.",
            ],
            checklist=[
                "Add one test per new transform rule.",
                "Add one negative test per risk area.",
                "Ensure deterministic expected output strings.",
            ],
            code_refs=["tests/test_pipeline.py"],
        ),
        Section(
            heading="2. API Contract Tests",
            simple="In simple words: API tests ensure frontend can trust backend response shapes.",
            deep_points=[
                "Analyze endpoint test asserts availability of analysis, plan, and ML status blocks.",
                "Refactor endpoint test checks for new code, diff output, and validation status.",
                "Run-history tests verify saved run retrieval path.",
            ],
            checklist=[
                "Pin response field names in tests.",
                "Cover health and model-status routes.",
                "Cover run list and run detail retrieval.",
            ],
            code_refs=["tests/test_api.py"],
        ),
        Section(
            heading="3. ML Asset and Benchmark Tests",
            simple="In simple words: ML tests confirm dataset presence and evaluator script behavior.",
            deep_points=[
                "Dataset sanity test checks curated training data exists and has required fields.",
                "Evaluator invocation test ensures modernization benchmark script returns expected structure.",
                "This gives baseline confidence even before full model training runs.",
            ],
            checklist=[
                "Validate data schema before training.",
                "Treat evaluator as regression gate.",
                "Add adapter-loading tests when model artifacts are present.",
            ],
            code_refs=["tests/test_ml_assets.py", "ml/evaluate_modernizer.py"],
        ),
        Section(
            heading="4. Current Execution Snapshot",
            simple="In simple words: this report includes a live test/eval snapshot generated from your current workspace.",
            deep_points=[
                f"Unit test run status: {unit_status}, discovered tests: {unit_ran}.",
                f"Benchmark pass summary: {eval_pass}/{eval_size} ({eval_ratio:.1f} percent).",
                "If these numbers differ in your local run, regenerate this PDF to keep evidence aligned.",
            ],
            checklist=[
                "Regenerate reports after major code changes.",
                "Keep test and benchmark outputs versioned for submissions.",
                "Use same environment when comparing metrics.",
            ],
            code_refs=["docs/generate_all_in_depth_reports.py"],
        ),
        Section(
            heading="5. Failure Mode Coverage",
            simple="In simple words: tests should also prove that unsafe outputs are blocked.",
            deep_points=[
                "Validation layer is tested for rejection when legacy constructs remain after transformation.",
                "Blocked/restricted analyzer modes should be exercised with dynamic execution samples.",
                "Run-history retrieval should be tested for non-existent run IDs.",
            ],
            checklist=[
                "Add explicit blocked-mode test cases.",
                "Add malformed-input API tests.",
                "Add concurrency tests for run-store growth scenarios.",
            ],
            code_refs=["core/validation.py", "agents/analyzer.py", "main.py"],
        ),
        Section(
            heading="6. Quality Gates for Delivery",
            simple="In simple words: code should be merged only when tests and benchmark checks pass.",
            deep_points=[
                "Minimum gate can include pipeline tests, API tests, and evaluator smoke benchmark.",
                "Optional gate can include style checks and static analysis.",
                "Release notes should include transform changes and risk notes.",
            ],
            checklist=[
                "Define mandatory checks in one script or CI job.",
                "Fail build on regression in critical tests.",
                "Track flaky tests and stabilize quickly.",
            ],
            code_refs=["tests/", "ml/evaluate_modernizer.py"],
        ),
        Section(
            heading="7. Evaluation Roadmap",
            simple="In simple words: to claim stronger quality, we need larger benchmark sets and per-pattern metrics.",
            deep_points=[
                "Add stratified benchmark slices by syntax pattern type and risk category.",
                "Track precision/recall for each transform rule using labeled samples.",
                "Add human-review scoring rubric for readability and behavior trust.",
            ],
            checklist=[
                "Scale benchmark beyond smoke-test size.",
                "Track per-rule failure heatmap.",
                "Keep monthly evaluation snapshots for trend analysis.",
            ],
            code_refs=["ml/data/eval_benchmark.jsonl", "docs/pdfs/"],
        ),
    ]

    positioning_sections = [
        Section(
            heading="0. Positioning in One Line",
            simple="In simple words: Helix AI is a specialized legacy Python modernization workbench, not a generic coding chatbot.",
            deep_points=[
                "Specialization gives predictability in one difficult task domain.",
                "Deterministic transforms + validation + diff-first review create trust for migration workflows.",
                "General assistants remain useful for broad coding but may not provide deterministic migration traces.",
            ],
            checklist=[
                "Lead with specialization message.",
                "Do not claim universal superiority.",
                "Use evidence metrics with clear scope.",
            ],
        ),
        Section(
            heading="1. Comparison Dimensions",
            simple="In simple words: compare tools on migration fit, control, visibility, and breadth.",
            deep_points=[
                "For this project, migration fit and validation visibility matter more than open-ended code generation breadth.",
                "Deterministic control is a key criterion in codebase modernization use-cases.",
                "Breadth remains important for ideation but is secondary for guarded migration pipelines.",
            ],
            checklist=[
                "Use weighted criteria tied to project goal.",
                "Keep scoring method transparent.",
                "Separate objective metrics from subjective opinions.",
            ],
            code_refs=["docs/generate_4ai_visual_pack.py", "docs/assets/helix_4ai_comparison_meta.json"],
        ),
        Section(
            heading="2. Where Helix AI Stands Out",
            simple="In simple words: Helix stands out in deterministic modernization and validation-first workflow.",
            deep_points=[
                "Explicit issue-to-transform mapping enables predictable behavior and easier debugging.",
                "Validation gate prevents unsafe outputs from silently passing.",
                "Run history with diff/report supports traceability for teams and academic review.",
            ],
            checklist=[
                "Demonstrate analyze->diff->validate loop live.",
                "Show rollback behavior on validation failure.",
                "Show run history retrieval to prove auditability.",
            ],
            code_refs=["core/execution.py", "core/validation.py", "core/run_store.py"],
        ),
        Section(
            heading="3. Where Other Tools Still Lead",
            simple="In simple words: general tools usually win on broad coding tasks, ecosystem integrations, and large-context generation.",
            deep_points=[
                "This is expected because their design goals are wider than legacy modernization.",
                "Helix should integrate with them instead of trying to replace them in every workflow.",
                "Clear honesty in positioning increases credibility.",
            ],
            checklist=[
                "Acknowledge strengths of competitors.",
                "Position Helix as complementary in modernization scenarios.",
                "Avoid exaggerated claims in formal reports.",
            ],
        ),
        Section(
            heading="4. Adoption Story",
            simple="In simple words: start with old snippets, then module-level migration, then larger repository migration.",
            deep_points=[
                "Phase 1: team runs snippets through analyze and diff-first workflow.",
                "Phase 2: teams modernize utility modules with manual review loops.",
                "Phase 3: repository-level migration planning with staged rollout.",
                "Each phase should track pass rates and manual-adjustment rates.",
            ],
            checklist=[
                "Define pilot scope before broad rollout.",
                "Collect before/after metrics per phase.",
                "Keep fallback path to original code always available.",
            ],
        ),
        Section(
            heading="5. Product Value Communication",
            simple="In simple words: the value is reduced migration risk, faster review, and clear modernization evidence.",
            deep_points=[
                "Engineers value predictable transforms and transparent warnings.",
                "Managers value measurable progress metrics and reduced migration uncertainty.",
                "Academic evaluators value reproducible process and explicit architecture reasoning.",
            ],
            checklist=[
                "Use persona-specific messaging.",
                "Support claims with logs, diffs, and test outcomes.",
                "Show both strengths and current limits.",
            ],
        ),
        Section(
            heading="6. Strategic Gaps to Close",
            simple="In simple words: to be stronger, Helix needs broader pattern coverage and larger validation evidence.",
            deep_points=[
                "Expand transform library beyond current high-frequency patterns.",
                "Expand benchmark dataset and publish per-pattern accuracy.",
                "Improve ML confidence calibration and gated usage.",
            ],
            checklist=[
                "Prioritize high-impact pattern gaps first.",
                "Publish periodic evaluation snapshots.",
                "Integrate feedback loop from real migration runs.",
            ],
        ),
        Section(
            heading="7. Final Positioning Statement",
            simple="In simple words: Helix AI is best framed as a focused modernization copilot with deterministic safety rails.",
            deep_points=[
                "This framing is realistic, technically honest, and defensible in viva and project review.",
                "As data and transform coverage grow, Helix can progressively take on larger automation responsibility.",
                "The current architecture already supports that growth path without full redesign.",
            ],
            checklist=[
                "Keep positioning aligned with evidence.",
                "Show roadmap with measurable milestones.",
                "Defend specialization as deliberate strategy.",
            ],
        ),
    ]

    reports = [
        ReportSpec(
            filename="HELIX_AI_IDEA_AND_PROBLEM_IN_DEPTH.pdf",
            title="Helix AI: Idea and Problem Statement (In-Depth)",
            subtitle="Simple words first, deep engineering details next",
            objective="This report explains why the project exists, what exact problem it solves, where boundaries are, and how success should be measured.",
            kpis=[
                ("Primary focus", "Legacy Python modernization"),
                ("Architecture mode", "Hybrid deterministic + optional ML"),
                ("Current test status", f"{unit_status} ({unit_ran} tests)"),
            ],
            sections=idea_sections,
            viva=[
                ("Why did you choose this problem?", "Because legacy Python migration is high-friction, high-risk, and still common in real codebases."),
                ("Why not pure ML only?", "Pure ML is flexible but less deterministic; we need reproducibility and safety gates for migration."),
                ("What is your strongest differentiator?", "Deterministic transforms with validation and diff-first review in a single guided workflow."),
                ("What is your biggest current limitation?", "Coverage is still targeted, so very rare or highly complex legacy constructs may need manual intervention."),
                ("How will you scale this project?", "Add more transform rules, larger benchmarks, stronger ML ranking, and CI-backed quality gates."),
            ],
        ),
        ReportSpec(
            filename="HELIX_AI_AGENTIC_ARCHITECTURE_IN_DEPTH.pdf",
            title="Helix AI: Agentic Architecture (In-Depth)",
            subtitle="Seven-stage modernization workflow with guarded execution",
            objective="This report documents how each agent/core module collaborates, what data is exchanged, and why this architecture is safe and extensible.",
            kpis=[
                ("Agent stages", "Analyzer, Suggester, Critic, Planner, Execution, Validation, Report"),
                ("Legacy rules tracked", str(snapshot["legacy_rule_count"])),
                ("Transform branches", str(snapshot["transform_rule_count"])),
            ],
            sections=architecture_sections,
            viva=[
                ("Why split into multiple agents?", "Separation of concerns keeps behavior explainable and makes debugging easier."),
                ("Where is orchestration done?", "In main.py endpoints, especially /analyze and /refactor."),
                ("What prevents unsafe changes?", "Risk mode gating + critic warnings + validation gate + rollback."),
                ("How does ML fit this architecture?", "ML provides auxiliary modernization output and status, while deterministic validated output remains authoritative."),
                ("How can this architecture scale?", "By preserving contracts and moving stages into queue workers when needed."),
            ],
        ),
        ReportSpec(
            filename="HELIX_AI_BACKEND_CODE_IN_DEPTH.pdf",
            title="Helix AI: Backend Code Walkthrough (In-Depth)",
            subtitle="From API entrypoint to validated modernization output",
            objective="This report teaches the backend from scratch in simple language, then dives into module-level implementation details.",
            kpis=[
                ("Backend files", str(snapshot["backend_files"])),
                ("Backend LOC", str(snapshot["backend_loc"])),
                ("API endpoints", str(snapshot["endpoint_count"])),
            ],
            sections=backend_sections,
            viva=[
                ("Why FastAPI?", "It gives fast route development, typed request models, and straightforward JSON responses."),
                ("Where are transformations implemented?", "In core/execution.py as explicit operation handlers."),
                ("How do you guarantee correctness?", "Validation core checks syntax, leftover legacy patterns, and behavior proxies before acceptance."),
                ("How is history stored?", "Append-only JSONL via RunStore for simplicity and auditability."),
                ("How can someone add a new rule?", "Add analyzer pattern, suggester mapping, execution transform, and a dedicated test case."),
            ],
        ),
        ReportSpec(
            filename="HELIX_AI_FRONTEND_UI_IN_DEPTH.pdf",
            title="Helix AI: Frontend and UX System (In-Depth)",
            subtitle="Professional single-page modernization experience",
            objective="This report describes the inner-page UI design decisions, interaction states, and how the frontend supports safe modernization review.",
            kpis=[
                ("Frontend files", str(snapshot["frontend_files"])),
                ("Frontend LOC", str(snapshot["frontend_loc"])),
                ("Sample buttons", str(snapshot["sample_button_count"])),
                ("Result tabs", str(snapshot["ui_tab_count"])),
            ],
            sections=frontend_sections,
            viva=[
                ("Why diff-first UX?", "Because migration trust depends on seeing exact line-level changes before applying."),
                ("How is user flow simplified?", "Single page, clear step cards, guided focus text, and one primary action button."),
                ("How do you avoid confusion?", "Separate Analyze and Modernize phases and keep output in tabs before applying to editor."),
                ("How is run history useful?", "It allows reopening previous reports and diffs without rerunning the pipeline."),
                ("What is next for UI?", "Contextual explanations, confidence badges, and richer per-pattern insights."),
            ],
        ),
        ReportSpec(
            filename="HELIX_AI_MATHEMATICAL_MODEL_IN_DEPTH.pdf",
            title="Helix AI: Mathematical Model and Scoring Logic (In-Depth)",
            subtitle="Simple formulas that drive safe modernization decisions",
            objective="This report explains every scoring and gating formula used by the current pipeline and how to evolve it rigorously.",
            kpis=[
                ("Critic base score families", "SYNTAX/API/TYPE/SEMANTIC/NOOP"),
                ("Planner score formula", "Safety + bounded priority boost"),
                ("Benchmark snapshot", f"{eval_pass}/{eval_size}"),
            ],
            sections=math_sections,
            viva=[
                ("What is your main scoring formula?", "Planner uses final_score = safety_score + max(0, 50 - priority)."),
                ("How do you avoid black-box decisions?", "All rule, score, and threshold logic is explicit in code."),
                ("Why not use neural confidence only?", "Model confidence alone is not enough for deterministic migration safety."),
                ("How do you evaluate improvement?", "By benchmark pass rates, failure category analysis, and regression tests."),
                ("What is next mathematically?", "Confidence calibration and per-transform dynamic thresholds."),
            ],
        ),
        ReportSpec(
            filename="HELIX_AI_TESTING_EVALUATION_IN_DEPTH.pdf",
            title="Helix AI: Testing and Evaluation Report (In-Depth)",
            subtitle="What was tested, how it was tested, and what results mean",
            objective="This report presents the quality strategy for pipeline, API, and ML data assets, with a live snapshot of current test/evaluation status.",
            kpis=[
                ("Test files", str(snapshot["test_files"])),
                ("Test methods", str(snapshot["test_case_count"])),
                ("Unit test status", f"{unit_status} ({unit_ran})"),
                ("Rule benchmark pass", f"{eval_pass}/{eval_size} ({eval_ratio:.1f}%)"),
            ],
            sections=testing_sections,
            viva=[
                ("What do your tests prove?", "They prove detection, transformation, validation behavior, API contract stability, and evaluator execution."),
                ("How do you handle regressions?", "By adding rule-specific tests and using benchmark checks as release gates."),
                ("Is benchmark enough today?", "It is a useful smoke baseline, but needs expansion for stronger statistical confidence."),
                ("Why include failure-path tests?", "Because safe migration requires proving blocking behavior as much as success behavior."),
                ("What is your next testing milestone?", "Per-pattern metrics with larger benchmark sets and CI automation."),
            ],
        ),
        ReportSpec(
            filename="HELIX_AI_COMPETITIVE_POSITIONING_IN_DEPTH.pdf",
            title="Helix AI: Competitive Positioning (In-Depth)",
            subtitle="Where Helix is strong, where others are strong, and how to position honestly",
            objective="This report frames Helix AI against general AI coding tools using migration-specific criteria and realistic strategic positioning.",
            kpis=[
                ("Positioning theme", "Specialized modernization with safety rails"),
                ("Comparison pack", "HELIX_AI_4AI_COMPARISON_PACK.pdf"),
                ("Evidence style", "Weighted criteria + explainable workflow"),
            ],
            sections=positioning_sections,
            viva=[
                ("How do you compare with general AI tools?", "We compare by migration-specific criteria first, then acknowledge breadth differences."),
                ("What is Helix strongest at?", "Deterministic migration flow, explicit validation, and auditable outputs."),
                ("Where does Helix still lag?", "General coding breadth and ecosystem-level integrations."),
                ("How do you keep comparison credible?", "By being explicit about scope and avoiding universal superiority claims."),
                ("What is the strategic path forward?", "Expand coverage and evaluation while preserving deterministic safety core."),
            ],
        ),
    ]

    return reports


def build_pdf(
    spec: ReportSpec,
    snapshot: dict[str, Any],
    unit_summary: dict[str, Any],
    eval_summary: dict[str, Any],
    min_pages: int = 30,
    max_pages: int = 40,
) -> tuple[Path, int]:
    output_path = PDF_DIR / spec.filename
    extra_pages = 0
    pages = 0

    for _ in range(6):
        story = build_story(spec, snapshot, unit_summary, eval_summary, extra_pages=extra_pages)
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=1.8 * cm,
            rightMargin=1.8 * cm,
            topMargin=1.9 * cm,
            bottomMargin=1.8 * cm,
            title=spec.title,
            author="Helix AI",
        )
        doc.build(story, onFirstPage=report_footer, onLaterPages=report_footer)
        pages = maybe_page_count(output_path)

        if pages < min_pages:
            extra_pages += (min_pages - pages)
            continue
        if pages > max_pages and extra_pages > 0:
            extra_pages = max(0, extra_pages - (pages - max_pages))
            continue
        break

    return output_path, pages


def main() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    snapshot = collect_snapshot()
    unit_summary = run_unittests()
    eval_summary = run_eval_benchmark()
    specs = build_specs(snapshot, unit_summary, eval_summary)

    generated: list[dict[str, Any]] = []
    for spec in specs:
        output, pages = build_pdf(spec, snapshot, unit_summary, eval_summary, min_pages=30, max_pages=40)
        generated.append(
            {
                "file": output.name,
                "path": str(output),
                "pages": pages,
            }
        )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot": snapshot,
        "unit_summary": unit_summary,
        "eval_summary": eval_summary,
        "generated_reports": generated,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
