import difflib
import json
import logging
import os
from datetime import datetime

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agents.analyzer import AnalyzerAgent
from agents.critic import CriticAgent
from agents.planner import PlannerAgent
from agents.suggester import SuggestionAgent
from core.config import settings
from core.execution import ExecutionCore
from core.ml_reasoner import MLReasoner
from core.report_generator import ReportGenerator
from core.run_store import RunStore
from core.validation import ValidationCore


analyzer = AnalyzerAgent()
suggester = SuggestionAgent()
critic = CriticAgent()
planner = PlannerAgent()
executor = ExecutionCore()
validator = ValidationCore()
reporter = ReportGenerator()
run_store = RunStore(settings.RUN_HISTORY_FILE)
reasoner = MLReasoner(
    enabled=settings.ML_MODEL_ENABLED,
    adapter_path=os.path.join(settings.BASE_DIR, settings.ML_MODEL_ADAPTER_PATH)
    if not os.path.isabs(settings.ML_MODEL_ADAPTER_PATH)
    else settings.ML_MODEL_ADAPTER_PATH,
    base_model=settings.ML_MODEL_BASE,
)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url=None,
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=settings.STATIC_DIR), name="static")
templates = Jinja2Templates(directory=settings.TEMPLATE_DIR)


class CodeRequest(BaseModel):
    code: str


class ContactRequest(BaseModel):
    name: str
    email: str
    project: str
    message: str


INFO_PAGES = {
    "mission": {
        "title": "Our Mission",
        "content": "<p>Helix AI modernizes legacy Python code with an autonomous multi-agent workflow. Our mission is to reduce migration effort, surface risky compatibility changes early, and give teams a safer path from outdated Python code to modern Python.</p>",
    },
    "team": {
        "title": "The Team",
        "content": "<p>A platform prototype built around agentic planning, rule-based modernization, and validation-driven execution.</p><ul class='list-disc pl-5 mt-4 space-y-2'><li><strong>Rutwik Bhondave</strong> - Platform Architecture</li><li><strong>Amit Jagtap</strong> - Migration Engine</li><li><strong>Priyanshu Nalwade</strong> - Validation and Reporting</li><li><strong>Abhishek Gadilkar</strong> - Frontend Experience</li></ul>",
    },
    "newsletter": {
        "title": "Helix AI Updates",
        "content": "<p>Track new migration rules, supported legacy patterns, and autonomous validation improvements.</p>",
    },
    "careers": {
        "title": "Join Us",
        "content": "<p>We are focused on developer tooling, code migration, and safe autonomous execution.</p>",
    },
    "contact": {
        "title": "Contact Us",
        "content": "<p>Questions about legacy Python modernization, agentic workflows, or enterprise migration support?</p><p class='mt-4'>Email us at: <a href='mailto:hello@helixai.dev' class='text-orange-400 hover:text-orange-300'>hello@helixai.dev</a></p><p>Pune, India</p>",
    },
    "refund-policy": {
        "title": "Project Scope",
        "content": "<p>Helix AI focuses on legacy Python modernization. The current prototype strongly supports Python 2.x patterns and now includes best-effort handling for selected earlier legacy constructs, with guarded validation before applying automated changes.</p>",
    },
    "faqs": {
        "title": "Frequently Asked Questions",
        "content": "<p><strong>Q: What does Helix AI do today?</strong><br>A: It analyzes legacy Python code, detects outdated constructs, plans modernization steps, applies supported rewrites, and validates the result.</p><p class='mt-4'><strong>Q: Which legacy patterns are supported?</strong><br>A: The prototype supports modernization for constructs such as <code>print</code> statements, <code>xrange</code>, <code>raw_input</code>, old exception syntax, dictionary iterator APIs, <code>has_key</code>, legacy type names, backtick repr syntax, and <code>apply(...)</code> builtins.</p><p class='mt-4'><strong>Q: Does this include very old Python input?</strong><br>A: Helix AI now handles selected early legacy patterns on a best-effort basis, but heavily archaic or unsupported constructs may still require manual review.</p><p class='mt-4'><strong>Q: Is every migration fully automatic?</strong><br>A: No. The planner marks higher-risk semantic changes for review, especially division semantics and text/bytes boundaries.</p><p class='mt-4'><strong>Q: Does Helix AI validate output?</strong><br>A: Yes. The pipeline reparses the migrated code, checks for leftover legacy constructs, and blocks unsafe results.</p>",
    },
    "stories": {
        "title": "Use Cases",
        "content": "<p>Helix AI is designed for teams modernizing older Python services, educational code archives, and legacy utilities that need a safer path to current Python.</p>",
    },
    "status": {
        "title": "System Status",
        "content": "<p>Modernization pipeline online.</p><ul class='list-disc pl-5 mt-4 space-y-2'><li class='text-emerald-400'>Analysis Engine: Online</li><li class='text-emerald-400'>Transformation Engine: Online</li><li class='text-emerald-400'>Validation Core: Online</li></ul>",
    },
}


@app.get("/", response_class=HTMLResponse)
async def read_landing(request: Request):
    return templates.TemplateResponse(request, "new.html")


@app.get("/health")
async def health_check():
    return JSONResponse(
        content={
            "status": "ok",
            "app": settings.APP_NAME,
            "version": settings.VERSION,
            "ml_reasoner": reasoner.explain_status(),
        }
    )


@app.get("/model-status")
async def model_status():
    return JSONResponse(content=reasoner.explain_status())


@app.get("/runs")
async def list_runs(limit: int = 10):
    return JSONResponse(content={"runs": run_store.list_runs(limit=max(1, min(limit, 50)))})


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    record = run_store.get_run(run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Run not found")
    return JSONResponse(content=record)


@app.get("/app", response_class=HTMLResponse)
async def read_app(request: Request):
    return templates.TemplateResponse(request, "index.html", {"app_name": settings.APP_NAME})


@app.get("/info/{page_name}", response_class=HTMLResponse)
async def read_info_page(request: Request, page_name: str):
    page_data = INFO_PAGES.get(page_name)
    if not page_data:
        raise HTTPException(status_code=404, detail="Page not found")

    return templates.TemplateResponse(
        request,
        "info.html",
        {
            "page_title": page_data["title"],
            "content": page_data["content"],
        },
    )


@app.post("/submit-request")
async def submit_request(request: ContactRequest):
    try:
        logging.info("New Contact Request: %s (%s) - Project: %s", request.name, request.email, request.project)

        inquiry_data = {
            "name": request.name,
            "email": request.email,
            "project": request.project,
            "message": request.message,
            "timestamp": datetime.now().isoformat(),
        }

        file_path = "data/inquiries.json"
        inquiries = []
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    inquiries = json.load(file)
            except Exception as exc:
                logging.error("Failed to read inquiries: %s", exc)
                inquiries = []

        inquiries.append(inquiry_data)

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(inquiries, file, indent=4)

        return JSONResponse(content={"success": True, "message": "Migration inquiry received."})
    except Exception as exc:
        logging.error("Form submission failed: %s", exc)
        raise HTTPException(status_code=500, detail="Transmission failed")


@app.post("/analyze")
async def analyze_code(request: CodeRequest):
    try:
        analysis = await analyzer.process(request.code)
        suggestions = await suggester.process(analysis, request.code)
        critiques = await critic.process(suggestions)
        plan_result = await planner.process(suggestions, critiques)
        ml_status = reasoner.explain_status()

        return JSONResponse(
            content={
                "analysis": analysis,
                "suggestions": suggestions,
                "critiques": critiques,
                "plan": plan_result,
                "ml_reasoner": ml_status,
            }
        )
    except Exception as exc:
        logging.error("Analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/refactor")
async def refactor_code(request: CodeRequest):
    try:
        logs = ["--- Starting Legacy Python Modernization Pipeline ---"]
        run_id = None

        analysis = await analyzer.process(request.code)
        if not analysis.get("success"):
            return JSONResponse(content={"error": "Analysis failed", "details": analysis.get("error")})

        logs.append(f"Analyzer: probable source version = {analysis.get('probable_source_version')}")
        logs.append(f"Analyzer: detected {len(analysis.get('legacy_issues', []))} legacy issues.")

        input_validation = validator.detect_incomplete_input(request.code)
        if not input_validation["success"]:
            logs.append(f"Input validation failed: {input_validation.get('error')}")
            logs.append("Execution skipped because the source file appears incomplete.")
            report = reporter.generate_report(
                analysis=analysis,
                selected_plans=[],
                success=False,
                validation_logs=logs,
                validation_result=input_validation,
            )
            run_record = run_store.save_run(
                {
                    "probable_source_version": analysis.get("probable_source_version"),
                    "risk_score": analysis.get("risk_score"),
                    "legacy_issue_count": len(analysis.get("legacy_issues", [])),
                    "validation_success": False,
                    "applied_transformations": [],
                    "original_code": request.code,
                    "new_code": "",
                    "candidate_code": "",
                    "analysis": analysis,
                    "validation": input_validation,
                    "diff": "",
                    "candidate_diff": "",
                    "report": report,
                    "rolled_back": False,
                    "output_available": False,
                }
            )
            return JSONResponse(
                content={
                    "run_id": run_record["run_id"],
                    "original_code": request.code,
                    "new_code": "",
                    "candidate_code": "",
                    "analysis": analysis,
                    "suggestions": [],
                    "plan": {"selected_plan": None, "selected_plans": [], "total_candidates": 0, "approved_count": 0, "candidates": []},
                    "validation": input_validation,
                    "logs": logs,
                    "report": report,
                    "diff": "",
                    "candidate_diff": "",
                    "rolled_back": False,
                    "output_available": False,
                    "ml_reasoner": reasoner.explain_status(),
                }
            )

        if analysis.get("mode") == "BLOCKED":
            logs.append("Execution blocked due to critical dynamic execution risk.")
            return JSONResponse(content={"error": "Blocked", "logs": logs, "analysis": analysis})

        suggestions = await suggester.process(analysis, request.code)
        critique = await critic.process(suggestions)
        plan_result = await planner.process(suggestions, critique)
        selected_plans = plan_result.get("selected_plans", [])
        ml_result = None

        logs.append(f"Suggester: generated {len(suggestions)} migration suggestions.")
        logs.append(f"Planner: selected {len(selected_plans)} transformations for execution.")

        candidate_code = request.code
        new_code = ""
        validation_result = {"success": False, "stage": "SKIPPED", "message": "No changes applied.", "warnings": []}
        validation_success = False
        rolled_back = False

        if selected_plans:
            candidate_code = executor.apply_changes(request.code, selected_plans)
            logs.append("Execution: transformations applied sequentially.")

            validation_result = validator.validate(request.code, candidate_code)
            if validation_result["success"]:
                validation_success = True
                new_code = candidate_code
                logs.append("Validation: modernization passed all configured checks.")
            else:
                rolled_back = True
                logs.append(f"Validation failed: {validation_result.get('error')}")
                logs.append("Rollback: no safe output was produced.")
        else:
            logs.append("Planner: no executable transformations were selected.")

        if reasoner.is_available():
            ml_result = reasoner.modernize(request.code)
            if ml_result.available and ml_result.output:
                logs.append("ML Reasoner: generated auxiliary modernization output.")
            elif ml_result.error:
                logs.append(f"ML Reasoner unavailable: {ml_result.error}")

        diff = "\n".join(
            difflib.unified_diff(
                request.code.splitlines(),
                new_code.splitlines(),
                fromfile="legacy.py",
                tofile="modernized.py",
                lineterm="",
            )
        ) if validation_success else ""

        candidate_diff = "\n".join(
            difflib.unified_diff(
                request.code.splitlines(),
                candidate_code.splitlines(),
                fromfile="legacy.py",
                tofile="candidate.py",
                lineterm="",
            )
        ) if candidate_code != request.code else ""

        report = reporter.generate_report(
            analysis=analysis,
            selected_plans=selected_plans,
            success=validation_success,
            validation_logs=logs,
            validation_result=validation_result,
        )
        run_record = run_store.save_run(
            {
                "probable_source_version": analysis.get("probable_source_version"),
                "risk_score": analysis.get("risk_score"),
                "legacy_issue_count": len(analysis.get("legacy_issues", [])),
                "validation_success": validation_success,
                "applied_transformations": [plan["suggestion"]["id"] for plan in selected_plans],
                "original_code": request.code,
                "new_code": new_code,
                "candidate_code": candidate_code if not validation_success else "",
                "analysis": analysis,
                "validation": validation_result,
                "diff": diff,
                "candidate_diff": candidate_diff,
                "report": report,
                "rolled_back": rolled_back,
                "output_available": validation_success,
            }
        )
        run_id = run_record["run_id"]

        return JSONResponse(
            content={
                "run_id": run_id,
                "original_code": request.code,
                "new_code": new_code,
                "candidate_code": candidate_code if not validation_success else "",
                "analysis": analysis,
                "suggestions": suggestions,
                "plan": plan_result,
                "validation": validation_result,
                "logs": logs,
                "report": report,
                "diff": diff,
                "candidate_diff": candidate_diff,
                "rolled_back": rolled_back,
                "output_available": validation_success,
                "ml_reasoner": ml_result.__dict__ if ml_result else reasoner.explain_status(),
            }
        )
    except Exception as exc:
        logging.error("Refactor failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
