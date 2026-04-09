from __future__ import annotations

import json
import statistics
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
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
ASSETS_DIR = DOCS_DIR / "assets"
PDF_DIR = DOCS_DIR / "pdfs"
OUTPUT_PDF = PDF_DIR / "HELIX_AI_ML_TRAINING_IN_DEPTH.pdf"

TRAINING_MIXTURE = ROOT / "ml" / "data" / "training_mixture.jsonl"
MODERNIZATION_TRAIN = ROOT / "ml" / "data" / "modernization_train.jsonl"
SEED_DATASET = ROOT / "ml" / "data" / "seed_modernization_dataset.jsonl"
EVAL_BENCHMARK = ROOT / "ml" / "data" / "eval_benchmark.jsonl"
MANIFEST_PATH = ROOT / "ml" / "public_dataset_manifest.json"
CHECKPOINT_292 = ROOT / "ml" / "models" / "nebula-modernizer-qwen25-1.5b" / "checkpoint-292" / "trainer_state.json"
CHECKPOINT_146 = ROOT / "ml" / "models" / "nebula-modernizer-qwen25-1.5b" / "checkpoint-146" / "trainer_state.json"
ADAPTER_CONFIG = ROOT / "ml" / "models" / "nebula-modernizer-qwen25-1.5b" / "adapter_config.json"
ADAPTER_FILE = ROOT / "ml" / "models" / "nebula-modernizer-qwen25-1.5b" / "adapter_model.safetensors"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_read(path: Path, fallback: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return fallback


def dataset_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts: dict[str, int] = {}
    risk_counts: dict[str, int] = {}
    tag_counts: dict[str, int] = {}
    input_lens: list[int] = []
    output_lens: list[int] = []

    for row in rows:
        source = row.get("mixture_source") or row.get("source")
        if source:
            source_counts[source] = source_counts.get(source, 0) + 1

        risk = row.get("risk")
        if isinstance(risk, str):
            risk_key = risk.strip().lower()
            risk_counts[risk_key] = risk_counts.get(risk_key, 0) + 1

        tags = row.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        input_text = row.get("input")
        output_text = row.get("output")
        if isinstance(input_text, str):
            input_lens.append(len(input_text))
        if isinstance(output_text, str):
            output_lens.append(len(output_text))

    return {
        "rows": len(rows),
        "sources": source_counts,
        "risks": risk_counts,
        "tags": tag_counts,
        "input_lens": input_lens,
        "output_lens": output_lens,
        "input_char_stats": describe_numeric(input_lens),
        "output_char_stats": describe_numeric(output_lens),
    }


def describe_numeric(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "count": 0,
            "min": 0.0,
            "max": 0.0,
            "mean": 0.0,
            "median": 0.0,
            "p90": 0.0,
        }

    sorted_values = sorted(values)
    p90_idx = int(0.9 * (len(sorted_values) - 1))
    return {
        "count": float(len(values)),
        "min": float(min(values)),
        "max": float(max(values)),
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)),
        "p90": float(sorted_values[p90_idx]),
    }


def load_trainer_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    log_history = payload.get("log_history", [])
    points = [x for x in log_history if isinstance(x, dict) and "loss" in x and "step" in x]
    losses = [float(p["loss"]) for p in points]
    steps = [int(p["step"]) for p in points]
    lrs = [float(p.get("learning_rate", 0.0)) for p in points]
    grads = [float(p.get("grad_norm", 0.0)) for p in points]
    return {
        "global_step": payload.get("global_step"),
        "num_train_epochs": payload.get("num_train_epochs"),
        "log_points": points,
        "steps": steps,
        "losses": losses,
        "learning_rates": lrs,
        "grad_norms": grads,
        "loss_summary": describe_numeric(losses),
    }


def run_eval_benchmark() -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "ml" / "evaluate_modernizer.py")]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except Exception as exc:
        return {
            "benchmark_size": 0,
            "rule_pass": 0,
            "ml_pass": None,
            "details": [],
            "error": str(exc),
        }


def setup_plot_style() -> None:
    plt.style.use("dark_background")
    plt.rcParams.update(
        {
            "font.size": 10.5,
            "figure.facecolor": "#0b0d12",
            "axes.facecolor": "#0f1217",
            "axes.edgecolor": "#3a4050",
            "axes.labelcolor": "#d8e0ef",
            "xtick.color": "#c7d2e0",
            "ytick.color": "#c7d2e0",
            "grid.color": "#2f3645",
        }
    )


def chart_dataset_sources(stats: dict[str, Any]) -> Path:
    out = ASSETS_DIR / "helix-ml-dataset-source-distribution.png"
    source_counts = stats["sources"] or {"unknown": stats["rows"]}
    labels = list(source_counts.keys())
    values = list(source_counts.values())

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.bar(labels, values, color="#4aa8ff", alpha=0.92)
    ax.set_title("Training Mixture Source Distribution")
    ax.set_ylabel("Record Count")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + max(values) * 0.01, str(val), ha="center")
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def chart_risk_distribution(stats: dict[str, Any]) -> Path:
    out = ASSETS_DIR / "helix-ml-risk-distribution.png"
    risk_counts = stats["risks"] or {"low": 0, "medium": 0, "high": 0}
    labels = ["low", "medium", "high"]
    values = [risk_counts.get(k, 0) for k in labels]
    colors_map = {"low": "#39d98a", "medium": "#f6b84f", "high": "#ff7070"}
    colors_used = [colors_map[k] for k in labels]

    fig, ax = plt.subplots(figsize=(8, 5.2))
    bars = ax.bar(labels, values, color=colors_used, alpha=0.95)
    ax.set_title("Risk Label Distribution in Training Mixture")
    ax.set_ylabel("Record Count")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + max(values + [1]) * 0.01, str(val), ha="center")
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def chart_top_tags(stats: dict[str, Any]) -> Path:
    out = ASSETS_DIR / "helix-ml-top-tags.png"
    tag_counts = stats["tags"]
    top = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:12]
    if not top:
        top = [("no_tags", 0)]
    labels = [x[0] for x in top]
    values = [x[1] for x in top]

    fig, ax = plt.subplots(figsize=(11, 5.8))
    bars = ax.bar(labels, values, color="#8f9fff", alpha=0.92)
    ax.set_title("Most Frequent Training Tags")
    ax.set_ylabel("Frequency")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    plt.xticks(rotation=25, ha="right")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + max(values + [1]) * 0.01, str(val), ha="center", fontsize=8.8)
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def chart_loss_curve(state292: dict[str, Any], state146: dict[str, Any]) -> Path:
    out = ASSETS_DIR / "helix-ml-loss-curve.png"

    fig, ax = plt.subplots(figsize=(11, 5.8))
    if state292.get("steps") and state292.get("losses"):
        ax.plot(state292["steps"], state292["losses"], color="#42d392", linewidth=2.0, label="checkpoint-292 trajectory")
    if state146.get("steps") and state146.get("losses"):
        ax.plot(state146["steps"], state146["losses"], color="#4aa8ff", linewidth=1.5, alpha=0.8, label="checkpoint-146 trajectory")

    ax.set_title("Observed Training Loss Trajectory")
    ax.set_xlabel("Training Step")
    ax.set_ylabel("Loss")
    ax.grid(linestyle="--", alpha=0.35)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def chart_lr_and_grad(state292: dict[str, Any]) -> Path:
    out = ASSETS_DIR / "helix-ml-lr-grad-dynamics.png"
    steps = state292.get("steps", [])
    lrs = state292.get("learning_rates", [])
    grads = state292.get("grad_norms", [])

    fig, ax1 = plt.subplots(figsize=(11, 5.8))
    if steps and lrs:
        ax1.plot(steps, lrs, color="#ff9f4a", linewidth=2.0, label="learning rate")
    ax1.set_xlabel("Training Step")
    ax1.set_ylabel("Learning Rate", color="#ff9f4a")
    ax1.tick_params(axis="y", labelcolor="#ff9f4a")
    ax1.grid(linestyle="--", alpha=0.28)

    ax2 = ax1.twinx()
    if steps and grads:
        ax2.plot(steps, grads, color="#52c7ea", linewidth=1.7, alpha=0.85, label="grad norm")
    ax2.set_ylabel("Gradient Norm", color="#52c7ea")
    ax2.tick_params(axis="y", labelcolor="#52c7ea")

    ax1.set_title("Learning Rate Schedule vs Gradient Norm")
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def chart_eval_results(eval_result: dict[str, Any]) -> Path:
    out = ASSETS_DIR / "helix-ml-eval-results.png"
    benchmark_size = int(eval_result.get("benchmark_size", 0))
    rule_pass = int(eval_result.get("rule_pass", 0))
    ml_pass = eval_result.get("ml_pass")
    ml_pass_val = 0 if ml_pass is None else int(ml_pass)

    categories = ["Rule Pipeline Pass", "ML Pass (if enabled)", "Benchmark Size"]
    values = [rule_pass, ml_pass_val, benchmark_size]
    colors_used = ["#39d98a", "#4aa8ff", "#f6b84f"]

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    bars = ax.bar(categories, values, color=colors_used, alpha=0.92)
    ax.set_title("Evaluation Snapshot from ml/evaluate_modernizer.py")
    ax.set_ylabel("Count")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, val + max(values + [1]) * 0.02, str(val), ha="center")
    plt.xticks(rotation=12, ha="right")
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def chart_input_output_length_hist(stats: dict[str, Any]) -> Path:
    out = ASSETS_DIR / "helix-ml-input-output-length-hist.png"
    input_lens = stats.get("input_lens", [])
    output_lens = stats.get("output_lens", [])

    fig, ax = plt.subplots(figsize=(11, 5.8))
    if input_lens:
        ax.hist(input_lens, bins=20, alpha=0.65, color="#4aa8ff", label="input length")
    if output_lens:
        ax.hist(output_lens, bins=20, alpha=0.65, color="#42d392", label="output length")
    ax.set_title("Input vs Output Character Length Distribution")
    ax.set_xlabel("Characters")
    ax.set_ylabel("Frequency")
    ax.grid(linestyle="--", alpha=0.35)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def chart_loss_delta(state292: dict[str, Any]) -> Path:
    out = ASSETS_DIR / "helix-ml-loss-delta.png"
    steps = state292.get("steps", [])
    losses = state292.get("losses", [])
    deltas: list[float] = []
    delta_steps: list[int] = []
    if len(losses) > 1:
        for i in range(1, len(losses)):
            deltas.append(losses[i] - losses[i - 1])
            delta_steps.append(steps[i] if i < len(steps) else i)

    fig, ax = plt.subplots(figsize=(11, 5.4))
    if delta_steps and deltas:
        ax.plot(delta_steps, deltas, color="#f6b84f", linewidth=1.8)
    ax.axhline(0, color="#9fb0c8", linewidth=1.0)
    ax.set_title("Step-to-Step Loss Delta")
    ax.set_xlabel("Training Step")
    ax.set_ylabel("Delta Loss")
    ax.grid(linestyle="--", alpha=0.35)
    fig.tight_layout()
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def draw_charts(stats: dict[str, Any], state292: dict[str, Any], state146: dict[str, Any], eval_result: dict[str, Any]) -> dict[str, Path]:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    setup_plot_style()
    charts = {
        "sources": chart_dataset_sources(stats),
        "risks": chart_risk_distribution(stats),
        "tags": chart_top_tags(stats),
        "loss": chart_loss_curve(state292, state146),
        "lr_grad": chart_lr_and_grad(state292),
        "eval": chart_eval_results(eval_result),
        "length_hist": chart_input_output_length_hist(stats),
        "loss_delta": chart_loss_delta(state292),
    }
    return charts


def para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text, style)


def add_heading(story: list[Any], text: str, style: ParagraphStyle) -> None:
    story.append(para(text, style))
    story.append(Spacer(1, 0.22 * cm))


def add_paragraphs(story: list[Any], paragraphs: list[str], style: ParagraphStyle, gap: float = 0.16) -> None:
    for text in paragraphs:
        story.append(para(text, style))
        story.append(Spacer(1, gap * cm))


def add_bullets(story: list[Any], items: list[str], style: ParagraphStyle) -> None:
    for item in items:
        story.append(para(f"- {item}", style))
        story.append(Spacer(1, 0.11 * cm))
    story.append(Spacer(1, 0.14 * cm))


def add_table(story: list[Any], rows: list[list[Any]], col_widths: list[float]) -> None:
    t = Table(rows, colWidths=[w * cm for w in col_widths], repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2634")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#dfe8f6")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#3d4a60")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.0),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#0f131b")),
                ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor("#d2d9e6")),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 0.25 * cm))


def add_image(
    story: list[Any],
    path: Path,
    width_cm: float,
    caption: str,
    styles: dict[str, ParagraphStyle],
    start_on_new_page: bool = True,
) -> None:
    if not path.exists():
        return
    if start_on_new_page:
        story.append(PageBreak())
    img = Image(str(path))
    max_width = width_cm * cm
    max_height = 8.8 * cm
    scale = min(max_width / img.imageWidth, max_height / img.imageHeight)
    img.drawWidth = img.imageWidth * scale
    img.drawHeight = img.imageHeight * scale
    story.append(img)
    story.append(Spacer(1, 0.08 * cm))
    story.append(para(f"<i>{caption}</i>", styles["caption"]))
    story.append(Spacer(1, 0.25 * cm))


def code_excerpt(path: Path, start: int, end: int) -> str:
    lines = safe_read(path).splitlines()
    if not lines:
        return f"# missing file: {path}"
    start_idx = max(start - 1, 0)
    end_idx = min(end, len(lines))
    sliced = lines[start_idx:end_idx]
    return "\n".join(f"{i+start_idx+1:04d}: {line}" for i, line in enumerate(sliced))


def chunk_list(items: list[Any], chunk_size: int) -> list[list[Any]]:
    if chunk_size <= 0:
        return [items]
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def trim_text(text: str, limit: int = 340) -> str:
    if text is None:
        return ""
    cleaned = str(text).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3] + "..."


def build_report() -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    mixture_rows = load_jsonl(TRAINING_MIXTURE)
    modernization_rows = load_jsonl(MODERNIZATION_TRAIN)
    seed_rows = load_jsonl(SEED_DATASET)
    benchmark_rows = load_jsonl(EVAL_BENCHMARK)
    manifest = load_json(MANIFEST_PATH)
    adapter_cfg = load_json(ADAPTER_CONFIG)
    state292 = load_trainer_state(CHECKPOINT_292)
    state146 = load_trainer_state(CHECKPOINT_146)
    eval_result = run_eval_benchmark()

    mixture_stats = dataset_stats(mixture_rows)
    modernization_stats = dataset_stats(modernization_rows)
    seed_stats = dataset_stats(seed_rows)

    adapter_size_mb = round(ADAPTER_FILE.stat().st_size / (1024 * 1024), 2) if ADAPTER_FILE.exists() else 0.0

    charts = draw_charts(mixture_stats, state292, state146, eval_result)

    styles_sheet = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {
        "title": ParagraphStyle(
            "TitleCustom",
            parent=styles_sheet["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            textColor=colors.HexColor("#e7eefc"),
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=styles_sheet["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=19,
            textColor=colors.HexColor("#dce8ff"),
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=styles_sheet["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.5,
            leading=15,
            textColor=colors.HexColor("#9fd1ff"),
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=styles_sheet["BodyText"],
            fontName="Helvetica",
            fontSize=9.8,
            leading=13.7,
            textColor=colors.HexColor("#d3dbea"),
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=styles_sheet["BodyText"],
            fontName="Helvetica",
            fontSize=9.6,
            leading=13.2,
            textColor=colors.HexColor("#d3dbea"),
            leftIndent=6,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=styles_sheet["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=8.7,
            leading=11,
            textColor=colors.HexColor("#aab6c8"),
        ),
        "code": ParagraphStyle(
            "Code",
            parent=styles_sheet["Code"],
            fontName="Courier",
            fontSize=7.3,
            leading=9.0,
            textColor=colors.HexColor("#d7ffe2"),
            backColor=colors.HexColor("#101621"),
            leftIndent=5,
            rightIndent=5,
        ),
    }

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        rightMargin=1.45 * cm,
        leftMargin=1.45 * cm,
        topMargin=1.25 * cm,
        bottomMargin=1.25 * cm,
        title="HELIX AI ML Training In-Depth Report",
        author="Helix AI Team",
    )

    story: list[Any] = []

    generated_on = datetime.now().strftime("%Y-%m-%d %H:%M")
    add_heading(story, "HELIX AI", styles["title"])
    add_heading(story, "ML Training In-Depth Report", styles["h1"])
    add_paragraphs(
        story,
        [
            "This report documents the complete ML training lifecycle for the Helix AI legacy Python modernization assistant. It includes data curation, model adaptation strategy, objective function, optimization configuration, measured results, operational constraints, and deployment integration with the deterministic modernization pipeline.",
            f"Generated on: {generated_on}",
            "Important scope note: this is an engineering report for the current student-project implementation. It is intended to be technically rigorous and reproducible, while clearly separating measured facts from design recommendations.",
        ],
        styles["body"],
    )

    add_table(
        story,
        [
            ["Field", "Value"],
            ["Project", "Helix AI - Legacy Python Modernizer"],
            ["Model family", "Qwen2.5-Coder-1.5B Instruct (4-bit base) + LoRA adapter"],
            ["Training approach", "Supervised fine-tuning (SFT) with prompt-formatted code pairs"],
            ["Primary dataset file", "ml/data/training_mixture.jsonl"],
            ["Training examples in current mixture", str(mixture_stats["rows"])],
            ["Current adapter size", f"{adapter_size_mb} MB"],
            ["Benchmark summary", f"Rule pipeline pass: {eval_result.get('rule_pass', 0)}/{eval_result.get('benchmark_size', 0)}"],
        ],
        [5.0, 10.0],
    )

    story.append(PageBreak())

    add_heading(story, "Table of Contents", styles["h1"])
    toc_items = [
        "0. Simple-Words Deep Guide (How Everything Works)",
        "1. Objective and Problem Formalization",
        "2. End-to-End ML System Boundary in Helix",
        "3. Dataset Strategy, Sources, and Weighting",
        "4. Data Curation and Quality Controls",
        "5. Prompt/Target Formatting for SFT",
        "6. Model, PEFT, and Quantization Choices",
        "7. Hyperparameters and Optimizer Schedule",
        "8. Observed Training Dynamics",
        "9. Artifact Inventory and Versioned Checkpoints",
        "10. Evaluation Protocol and Results",
        "11. Error Analysis and Failure Modes",
        "12. Safety, Validation, and Production Guardrails",
        "13. Reproducibility Runbook",
        "14. Colab Execution Notes and Constraints",
        "15. Integration with Agentic Pipeline",
        "16. Limitations and Next Iterations",
        "17. Data Distribution Deep Dive",
        "18. Detailed Checkpoint Log Analysis",
        "19. Pattern-Level Coverage Matrix",
        "20. Sample-by-Sample Modernization Casebook",
        "Appendix A: Full Command Reference",
        "Appendix B: Code Excerpts",
        "Appendix C: Dataset Snapshots",
        "Appendix D: Full Training Log Dump",
        "Appendix E: Colab Cell-by-Cell Guide",
        "Appendix F: File Inventory (ML Folder)",
    ]
    add_bullets(story, toc_items, styles["bullet"])

    story.append(PageBreak())

    add_heading(story, "0. Simple-Words Deep Guide", styles["h1"])
    add_paragraphs(
        story,
        [
            "This section explains the whole ML part in very simple words, but still in full depth. Think of this as the beginner-friendly version of the technical chapters.",
            "In one line: we show old Python code to the model as input, show what the modern code should look like as output, and train the model to learn that mapping pattern many times.",
            "Important: in Helix, ML is not allowed to run freely without checks. The deterministic pipeline and validator stay in control, so safety and consistency remain high.",
        ],
        styles["body"],
    )
    add_table(
        story,
        [
            ["Question", "Simple Answer"],
            ["What is the model learning?", "How to rewrite old Python patterns into modern Python safely."],
            ["What is training data?", "Many examples of before (legacy code) and after (modern code)."],
            ["Why not only ML?", "ML can be uncertain; deterministic rules + validation make output safer."],
            ["Why LoRA?", "It updates only small adapter weights, so training is cheaper and faster."],
            ["What is success?", "Modern code is correct, validates, and keeps behavior same or close."],
        ],
        [5.2, 9.8],
    )

    story.append(PageBreak())

    add_heading(story, "0.1 Simple View of Full Pipeline", styles["h2"])
    add_paragraphs(
        story,
        [
            "Step 1: User gives legacy code.",
            "Step 2: Analyzer detects old patterns (`xrange`, `raw_input`, old `except`, etc.).",
            "Step 3: Planner decides what transformations should run.",
            "Step 4: Execution engine applies changes.",
            "Step 5: Validator checks syntax, checks leftover legacy constructs, and checks behavior-level guardrails.",
            "Step 6: Optional ML output can assist, but validation gate is still final authority.",
        ],
        styles["body"],
    )
    add_bullets(
        story,
        [
            "Simple memory trick: Detect -> Plan -> Transform -> Validate -> Report.",
            "If validation fails, system can roll back or reject unsafe output.",
            "This is why Helix is reliable for modernization demos and evaluation.",
        ],
        styles["bullet"],
    )

    add_heading(story, "0.2 Simple View of Dataset Building", styles["h2"])
    add_paragraphs(
        story,
        [
            "A model becomes good only if training data is clean and relevant. So we first prepare examples focused on legacy-to-modern migration, not random coding tasks.",
            "Each example has: instruction + old code + modern target code. Some records also include risk labels (`low`, `medium`, `high`) and tags like `xrange` or `raw_input`.",
            "Then we build a weighted mixture. Weight means: some sources appear more often during training because they are more relevant to our task.",
        ],
        styles["body"],
    )
    add_table(
        story,
        [
            ["Data Term", "Simple Meaning", "Why It Matters"],
            ["Instruction", "What task the model should do", "Keeps model behavior focused"],
            ["Input", "Legacy code snippet", "This is what model reads"],
            ["Output", "Expected modern code", "This is what model learns to generate"],
            ["Tag", "Pattern label (like `xrange`)", "Helps track pattern coverage"],
            ["Risk label", "How sensitive a rewrite is", "Used for review priority"],
        ],
        [3.2, 4.7, 7.1],
    )

    story.append(PageBreak())

    add_heading(story, "0.3 Simple View of Training Loop", styles["h2"])
    add_paragraphs(
        story,
        [
            "During training, data is fed in small mini-batches. For each batch, the model predicts tokens and gets a loss value. Lower loss means prediction is closer to expected output.",
            "Optimizer updates adapter weights to reduce this loss over many steps. Learning rate controls how big each update should be.",
            "Gradient accumulation is used when GPU memory is small. It lets us simulate larger effective batch size without crashing memory.",
        ],
        styles["body"],
    )
    add_bullets(
        story,
        [
            "Loss down over time is good.",
            "But low loss alone does not prove real-world correctness.",
            "So we still run benchmark and validator checks after training.",
        ],
        styles["bullet"],
    )

    add_heading(story, "0.4 Simple View of LoRA and 4-bit", styles["h2"])
    add_paragraphs(
        story,
        [
            "Full model training is expensive. LoRA solves this by training a small adapter on top of frozen base model weights.",
            "4-bit loading reduces memory usage so training becomes practical on Colab T4/L4.",
            "Result: good quality improvement at much lower compute cost.",
        ],
        styles["body"],
    )
    add_table(
        story,
        [
            ["Choice", "Simple Explanation", "Project Benefit"],
            ["4-bit base model", "Compressed base weights in memory", "Fits on student GPU runtime"],
            ["LoRA rank r=16", "Small trainable update capacity", "Good balance of quality and cost"],
            ["Cosine schedule", "Learning rate slowly decays", "Stable late training"],
            ["Checkpoint save", "Save model states at intervals", "Recovery + comparison"],
        ],
        [3.1, 5.6, 6.3],
    )

    story.append(PageBreak())

    add_heading(story, "0.5 Simple View of Evaluation and Safety", styles["h2"])
    add_paragraphs(
        story,
        [
            "After training, we test known benchmark snippets. For each case, we check whether expected modernization is present and whether validation passes.",
            "In this project, deterministic baseline currently passes benchmark cases strongly. ML is used as assistive layer and should be measured with `--enable-ml` runs.",
            "Safety rule: never trust generated output blindly. Always validate syntax + leftover legacy patterns + behavior guardrails.",
        ],
        styles["body"],
    )
    add_bullets(
        story,
        [
            "Good system behavior = correct + safe + explainable.",
            "Helix uses logs, diff, and report outputs so each run is auditable.",
            "This helps both viva defense and real engineering use.",
        ],
        styles["bullet"],
    )

    add_heading(story, "0.6 What To Say in Viva (Simple but Strong)", styles["h2"])
    add_paragraphs(
        story,
        [
            "If asked what is special in your ML pipeline, answer like this:",
            "1) We trained a domain-focused modernization model, not a generic chatbot.",
            "2) We used LoRA + 4-bit for practical compute constraints.",
            "3) We kept deterministic validation as final guardrail.",
            "4) We track measurable evidence (dataset stats, checkpoint logs, benchmark outputs).",
            "5) We designed for safe modernization, not just pretty output.",
        ],
        styles["body"],
    )

    story.append(PageBreak())

    add_heading(story, "1. Objective and Problem Formalization", styles["h1"])
    add_paragraphs(
        story,
        [
            "Helix AI targets a constrained but high-value transformation task: converting legacy Python syntax and outdated APIs into current Python while preserving runtime behavior as much as possible. The ML layer is not treated as a free-form code generator; it is treated as a modernization assistant under deterministic controls.",
            "Formally, each training example is a pair (x, y), where x is legacy code and y is modernized code. The learning objective is to maximize the conditional likelihood p(y | x, instruction, template). During inference, generated output is still subject to rule-based validation and lint checks before acceptance.",
            "This design is intentionally hybrid. Pure LLM generation can be fluent but unstable for deterministic migration guarantees. Rule-only engines are predictable but limited on ambiguous rewrites. Helix combines both.",
        ],
        styles["body"],
    )
    add_bullets(
        story,
        [
            "Primary optimization target: modernization correctness and consistency.",
            "Secondary target: broader generalization to near-neighbor legacy patterns.",
            "Constraint: avoid unsafe or hallucinated transformations in production flow.",
        ],
        styles["bullet"],
    )

    add_heading(story, "2. End-to-End ML System Boundary in Helix", styles["h1"])
    add_paragraphs(
        story,
        [
            "In the deployed architecture, ML does not bypass the planner or validation engine. The analyzer detects legacy constructs, the suggester/planner decides deterministic rewrites, and the validator blocks unsafe residual patterns. ML can assist when the deterministic path is unavailable or uncertain, but validation remains authoritative.",
            "The current benchmark confirms the deterministic path as trusted baseline with 4/4 pass on evaluation snippets. ML evaluation in this local run was performed with model-disabled baseline path, so `ml_pass` is null in the benchmark output.",
        ],
        styles["body"],
    )
    add_table(
        story,
        [
            ["Stage", "Role", "Deterministic or ML", "Gate"],
            ["Analyzer", "Detect legacy constructs + risk hints", "Deterministic", "Pattern rules"],
            ["Suggestion/Planner", "Select migration actions", "Deterministic + policy", "Priority/risk ordering"],
            ["Execution", "Apply rewrites", "Deterministic", "Operation-level rewrite functions"],
            ["ML Reasoner (optional)", "Assist modernization for ambiguous cases", "ML", "Enabled flag + adapter availability"],
            ["Validation", "Syntax + residual legacy + behavior checks", "Deterministic", "Hard pass/fail gate"],
        ],
        [2.8, 5.2, 3.3, 3.7],
    )

    story.append(PageBreak())

    add_heading(story, "3. Dataset Strategy, Sources, and Weighting", styles["h1"])
    add_paragraphs(
        story,
        [
            "Helix uses a weighted training mixture declared in `ml/public_dataset_manifest.json`. The design supports multiple sources (local modernization pairs, bug-fix corpora, commit-diff corpora, issue-to-patch corpora), each with explicit purpose and weight.",
            "In the current local state, external prepared datasets are absent; therefore, the generated mixture is entirely from local curated modernization records. This is a transparent and expected result given local availability.",
        ],
        styles["body"],
    )

    manifest_rows = [["Name", "Stage", "Purpose", "Weight", "Path/Prepared Path"]]
    for source in manifest.get("sources", []):
        manifest_rows.append(
            [
                str(source.get("name", "")),
                str(source.get("stage", "")),
                str(source.get("purpose", "")),
                str(source.get("weight", "")),
                str(source.get("path") or source.get("prepared_path") or ""),
            ]
        )
    add_table(story, manifest_rows, [2.6, 2.0, 3.3, 1.2, 5.9])
    add_image(story, charts["sources"], 15.4, "Figure 1. Training source distribution from current mixture build.", styles)

    add_heading(story, "4. Data Curation and Quality Controls", styles["h1"])
    add_paragraphs(
        story,
        [
            "Data quality controls are implemented through source curation, schema normalization, and explicit risk labels. Risk labels are coarse (low/medium/high) and are used for audit visibility and potential curriculum shaping.",
            "The seed dataset intentionally includes canonical modernization constructs such as print statements, xrange, raw_input, old exception binding syntax, dictionary iterator APIs, and type migrations (unicode/basestring/long).",
            "Because noisy records can degrade learning quality, rejected examples are separated and not included in the active training mixture.",
        ],
        styles["body"],
    )
    add_image(story, charts["risks"], 13.8, "Figure 2. Risk distribution in the active mixture.", styles)
    add_image(story, charts["tags"], 15.4, "Figure 3. Most frequent tags in the active dataset.", styles)

    summary_rows = [
        ["Dataset File", "Rows", "Mean Input Chars", "Mean Output Chars", "P90 Input Chars"],
        [
            "seed_modernization_dataset.jsonl",
            str(seed_stats["rows"]),
            f"{seed_stats['input_char_stats']['mean']:.1f}",
            f"{seed_stats['output_char_stats']['mean']:.1f}",
            f"{seed_stats['input_char_stats']['p90']:.1f}",
        ],
        [
            "modernization_train.jsonl",
            str(modernization_stats["rows"]),
            f"{modernization_stats['input_char_stats']['mean']:.1f}",
            f"{modernization_stats['output_char_stats']['mean']:.1f}",
            f"{modernization_stats['input_char_stats']['p90']:.1f}",
        ],
        [
            "training_mixture.jsonl",
            str(mixture_stats["rows"]),
            f"{mixture_stats['input_char_stats']['mean']:.1f}",
            f"{mixture_stats['output_char_stats']['mean']:.1f}",
            f"{mixture_stats['input_char_stats']['p90']:.1f}",
        ],
    ]
    add_table(story, summary_rows, [4.7, 1.7, 2.7, 2.7, 2.7])

    story.append(PageBreak())

    add_heading(story, "5. Prompt/Target Formatting for SFT", styles["h1"])
    add_paragraphs(
        story,
        [
            "The trainer uses instruction-style prompt formatting. Each record is converted into a single training text with explicit sections for instruction, input code, and response code. This keeps the objective aligned with instruction-following code generation.",
            "The prompt template intentionally requires output-only migrated code to reduce extra prose and improve post-processing simplicity.",
        ],
        styles["body"],
    )
    prompt_excerpt = code_excerpt(ROOT / "ml" / "train_modernizer_unsloth.py", 10, 34)
    story.append(Preformatted(prompt_excerpt, styles["code"]))
    story.append(Spacer(1, 0.22 * cm))

    add_heading(story, "6. Model, PEFT, and Quantization Choices", styles["h1"])
    add_paragraphs(
        story,
        [
            "Base model: `unsloth/Qwen2.5-Coder-1.5B-Instruct` in 4-bit loading mode. This choice balances practical Colab feasibility with enough coding capacity for legacy rewrite tasks.",
            "Fine-tuning method: LoRA on core attention and MLP projection modules (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`). Rank r=16 with alpha=16 and dropout=0.",
            "Rationale: full-parameter fine-tuning is not cost-efficient for this project scope. PEFT provides strong adaptation with much smaller trainable footprint and manageable storage (about 70 MB adapter).",
        ],
        styles["body"],
    )

    adapter_rows = [["Adapter Config Field", "Value"]]
    for key in ["base_model_name_or_path", "peft_type", "r", "lora_alpha", "lora_dropout", "target_modules", "task_type", "bias"]:
        val = adapter_cfg.get(key)
        adapter_rows.append([key, str(val)])
    add_table(story, adapter_rows, [4.8, 10.2])

    add_heading(story, "7. Hyperparameters and Optimizer Schedule", styles["h1"])
    hyper_rows = [
        ["Hyperparameter", "Value", "Why It Matters"],
        ["max_seq_length", "2048", "Allows moderate-length code context without excessive memory pressure."],
        ["batch_size", "2 (local script default) / 4 (Colab wrapper)", "Controls memory/throughput tradeoff."],
        ["gradient_accumulation_steps", "4 (default) / 2 (Colab wrapper)", "Increases effective batch while keeping VRAM in bounds."],
        ["epochs", "2-3 typical in scripts", "Enough to adapt to task without immediate overfitting on small data."],
        ["learning_rate", "2e-4", "Fast LoRA adaptation for code-style shifts."],
        ["warmup_ratio", "0.05", "Stabilizes early updates before full LR."],
        ["scheduler", "cosine", "Smooth decay toward low LR for late-step stability."],
        ["weight_decay", "0.01", "Regularization against overfitting."],
    ]
    add_table(story, hyper_rows, [3.0, 2.4, 9.6])

    story.append(PageBreak())

    add_heading(story, "8. Optimization Mathematics (Practical View)", styles["h1"])
    add_paragraphs(
        story,
        [
            "Training objective for causal language modeling is token-level negative log-likelihood:",
            "<font face='Courier'>L = - sum_t log p_theta(y_t | y_&lt;t, x)</font>",
            "With LoRA, trainable updates are low-rank adapters. For a frozen weight matrix W, adapted form is:",
            "<font face='Courier'>W' = W + DeltaW,  DeltaW = B A,  rank(DeltaW) = r</font>",
            "In QLoRA-style setup, base model weights are quantized for memory efficiency while adapter parameters stay trainable in higher precision. This yields practical training on commodity GPU runtimes such as T4.",
            "Cosine learning-rate schedule approximately follows:",
            "<font face='Courier'>lr(step) = lr_min + 0.5*(lr_max - lr_min)*(1 + cos(pi * progress))</font>",
            "These equations are included to make design choices explicit; the implementation uses Unsloth + TRL abstractions to execute this pipeline.",
        ],
        styles["body"],
    )

    add_heading(story, "9. Observed Training Dynamics", styles["h1"])
    add_paragraphs(
        story,
        [
            "From checkpoint logs, the training run reached step 292 with two epochs. Loss dropped from approximately 2.236 at early steps to approximately 0.085 by late steps, indicating strong adaptation to the current dataset.",
            "Loss decrease alone is not sufficient proof of generalization, but it indicates effective optimization on seen distribution.",
        ],
        styles["body"],
    )
    add_image(story, charts["loss"], 15.6, "Figure 4. Loss trajectory across checkpoints.", styles)
    add_image(story, charts["lr_grad"], 15.6, "Figure 5. Learning rate and gradient norm dynamics.", styles)

    state_rows = [
        ["Metric", "checkpoint-146", "checkpoint-292"],
        ["global_step", str(state146.get("global_step")), str(state292.get("global_step"))],
        ["num_train_epochs", str(state146.get("num_train_epochs")), str(state292.get("num_train_epochs"))],
        ["loss points", str(len(state146.get("losses", []))), str(len(state292.get("losses", [])))],
        [
            "first logged loss",
            f"{(state146.get('losses') or [0])[0]:.6f}" if state146.get("losses") else "n/a",
            f"{(state292.get('losses') or [0])[0]:.6f}" if state292.get("losses") else "n/a",
        ],
        [
            "last logged loss",
            f"{(state146.get('losses') or [0])[-1]:.6f}" if state146.get("losses") else "n/a",
            f"{(state292.get('losses') or [0])[-1]:.6f}" if state292.get("losses") else "n/a",
        ],
    ]
    add_table(story, state_rows, [4.5, 5.25, 5.25])

    story.append(PageBreak())

    add_heading(story, "10. Artifact Inventory and Versioning", styles["h1"])
    add_paragraphs(
        story,
        [
            "Artifacts are stored under `ml/models/nebula-modernizer-qwen25-1.5b` and include adapter weights, tokenizer files, and intermediate checkpoints. This allows reproducible rollback and audit of run history.",
            "Current adapter file size is used as a practical deployment metric because model portability matters in student-project environments.",
        ],
        styles["body"],
    )

    artifact_rows = [
        ["Artifact", "Path", "Observed Value"],
        ["Adapter weights", "ml/models/nebula-modernizer-qwen25-1.5b/adapter_model.safetensors", f"{adapter_size_mb} MB"],
        ["Adapter config", "ml/models/nebula-modernizer-qwen25-1.5b/adapter_config.json", "LoRA rank 16, alpha 16"],
        ["Checkpoint 146", "ml/models/nebula-modernizer-qwen25-1.5b/checkpoint-146", "intermediate snapshot"],
        ["Checkpoint 292", "ml/models/nebula-modernizer-qwen25-1.5b/checkpoint-292", "later snapshot"],
        ["Tokenizer", "ml/models/nebula-modernizer-qwen25-1.5b/tokenizer.json", "runtime tokenization metadata"],
    ]
    add_table(story, artifact_rows, [2.8, 8.4, 3.8])

    add_heading(story, "11. Evaluation Protocol and Results", styles["h1"])
    add_paragraphs(
        story,
        [
            "Evaluation script: `ml/evaluate_modernizer.py`. The script runs the full deterministic pipeline and optionally the ML reasoner. For each benchmark case, it checks both validation success and presence of expected modernization tokens.",
            "Current run result: benchmark_size = "
            f"{eval_result.get('benchmark_size', 0)}, "
            f"rule_pass = {eval_result.get('rule_pass', 0)}, "
            f"ml_pass = {eval_result.get('ml_pass')}.",
            "Interpretation: deterministic modernization baseline is currently fully passing on the small benchmark set. ML-assisted pass metrics were not collected in this run because ML flag was not enabled during this specific local evaluation call.",
        ],
        styles["body"],
    )
    add_image(story, charts["eval"], 13.2, "Figure 6. Evaluation summary from benchmark script.", styles)

    eval_rows = [["Case", "Rule OK", "Validation", "Expected modernization achieved"]]
    for detail in eval_result.get("details", []):
        eval_rows.append(
            [
                str(detail.get("name")),
                str(detail.get("rule_ok")),
                str(detail.get("rule_validation")),
                "yes" if detail.get("rule_ok") and detail.get("rule_validation") else "no",
            ]
        )
    add_table(story, eval_rows, [4.8, 2.5, 2.5, 5.2])

    story.append(PageBreak())

    add_heading(story, "12. Error Analysis and Failure Modes", styles["h1"])
    add_paragraphs(
        story,
        [
            "Although benchmark pass is strong on covered patterns, realistic migrations can fail in several ways. The report includes failure modes explicitly to avoid overclaiming.",
            "Observed and anticipated failure classes are listed below, along with mitigation status in current architecture.",
        ],
        styles["body"],
    )
    add_table(
        story,
        [
            ["Failure Class", "Description", "Current Mitigation", "Residual Risk"],
            ["Semantic drift", "Modernized code changes behavior subtly.", "Validator + manual review warnings", "Medium"],
            ["Unsupported archaic syntax", "Rare constructs outside known patterns.", "Best-effort detection + conservative fallback", "Medium/High"],
            ["Overfitting to seen templates", "Model memorizes style and misses edge cases.", "Mixture strategy + external data plan", "Medium"],
            ["Unsafe dynamic execution", "eval/exec behavior can be risky.", "Analyzer marks as blocked/restricted", "Low/Medium"],
            ["Incomplete external data", "Only local source currently active in mixture.", "Manifest supports expansion", "Medium"],
        ],
        [3.0, 4.5, 4.5, 2.5],
    )

    add_heading(story, "13. Safety, Validation, and Production Guardrails", styles["h1"])
    add_bullets(
        story,
        [
            "All generated output is reparsed for syntax; syntax errors fail validation.",
            "Residual legacy constructs are explicitly scanned and blocked if present.",
            "Function-presence checks reduce accidental deletion of original APIs.",
            "Division/text-bytes warnings are surfaced for manual semantic review.",
            "Eval/exec patterns are assigned critical risk in analyzer mode logic.",
        ],
        styles["bullet"],
    )

    add_paragraphs(
        story,
        [
            "This guardrail stack is the main reason Helix prefers hybrid modernization instead of unconstrained LLM rewrite.",
            "In other words: model output can propose; deterministic validation disposes.",
        ],
        styles["body"],
    )

    story.append(PageBreak())

    add_heading(story, "13. Reproducibility Runbook", styles["h1"])
    add_paragraphs(
        story,
        [
            "This section provides a complete practical runbook to rebuild data, train model adapters, evaluate, and integrate with app runtime.",
            "Commands are aligned with project scripts and tested paths.",
        ],
        styles["body"],
    )
    runbook_lines = [
        "# 1) Build seed and curated modernization data",
        "python3 ml/build_seed_modernization_dataset.py",
        "python3 ml/curate_dataset.py",
        "",
        "# 2) Build weighted training mixture",
        "python3 ml/build_training_mixture.py",
        "",
        "# 3) Train (local or Colab wrapper style)",
        "python3 ml/train_modernizer_unsloth.py --data-path ml/data/training_mixture.jsonl",
        "",
        "# 4) Evaluate deterministic baseline",
        "python3 ml/evaluate_modernizer.py",
        "",
        "# 5) Evaluate with ML adapter (when runtime available)",
        "python3 ml/evaluate_modernizer.py --enable-ml \\",
        "  --adapter-path ml/models/nebula-modernizer-qwen25-1.5b \\",
        "  --base-model Qwen/Qwen2.5-Coder-1.5B-Instruct",
    ]
    story.append(Preformatted("\n".join(runbook_lines), styles["code"]))
    story.append(Spacer(1, 0.2 * cm))

    add_heading(story, "14. Colab Execution Notes and Constraints", styles["h1"])
    add_bullets(
        story,
        [
            "Preferred runtime: T4/L4 GPU in Google Colab.",
            "Use fp16 on T4; bf16 may fail on non-Ampere setups.",
            "Upload training_mixture.jsonl manually when notebook asks.",
            "Export adapter and place under ml/models/nebula-modernizer-qwen25-1.5b.",
            "Run benchmark after integrating adapter to validate no regression.",
        ],
        styles["bullet"],
    )

    add_heading(story, "15. Integration with Agentic Pipeline", styles["h1"])
    add_paragraphs(
        story,
        [
            "ML integration is intentionally optional and gated. The app can run with `ML_MODEL_ENABLED=false` and still modernize through deterministic rules. This is valuable for reliability-first demos and offline grading.",
            "When enabled, ML reasoner is expected to support ambiguous transformations, but validation remains mandatory. This prevents silent quality regression from model drift.",
        ],
        styles["body"],
    )

    add_table(
        story,
        [
            ["Environment Variable", "Purpose"],
            ["ML_MODEL_ENABLED", "Toggle model-assisted modernization path."],
            ["ML_MODEL_BASE", "Specify base model identifier at runtime."],
            ["ML_MODEL_ADAPTER_PATH", "Point app to local LoRA adapter folder."],
        ],
        [5.5, 9.5],
    )

    story.append(PageBreak())

    add_heading(story, "16. Limitations and Next Iterations", styles["h1"])
    add_bullets(
        story,
        [
            "Current training mixture is single-source in active run due absent external prepared pairs.",
            "Benchmark set is compact (4 cases) and should be expanded to production-like coverage.",
            "Loss reduction is strong, but behavioral equivalence testing is still limited.",
            "No automatic runtime test harness exists yet for transformed code execution safety.",
            "Model card generated by trainer is generic and should be rewritten with task-specific details.",
        ],
        styles["bullet"],
    )
    add_paragraphs(
        story,
        [
            "Recommended next milestone is evaluation expansion: build 100+ legacy snippets across syntax, API, and semantic-risk categories; report pass/fail with strict criteria and manual audit notes.",
            "Second milestone is external-source activation in mixture builder and ablation runs (local-only vs mixed data).",
        ],
        styles["body"],
    )

    story.append(PageBreak())

    add_heading(story, "17. Data Distribution Deep Dive", styles["h1"])
    add_paragraphs(
        story,
        [
            "Beyond aggregate counts, model quality depends on data-shape properties. Input/output length spread, tag concentration, and source homogeneity directly affect convergence behavior and generalization risk.",
            "In the current run, the mixture is dominated by one source (`local_curated_modernization`), which is transparent but increases distribution-shift risk for unseen legacy styles.",
            "A robust next-step would add external prepared sources and run per-source ablation studies to quantify generalization delta.",
        ],
        styles["body"],
    )
    add_image(
        story,
        charts["length_hist"],
        15.4,
        "Figure 7. Histogram of input/output character lengths across training mixture.",
        styles,
        start_on_new_page=False,
    )
    add_image(
        story,
        charts["loss_delta"],
        15.4,
        "Figure 8. Step-to-step loss delta used to inspect optimization stability.",
        styles,
    )

    add_table(
        story,
        [
            ["Statistic", "Value"],
            ["Mixture row count", str(mixture_stats["rows"])],
            ["Input char mean / median / p90", f"{mixture_stats['input_char_stats']['mean']:.1f} / {mixture_stats['input_char_stats']['median']:.1f} / {mixture_stats['input_char_stats']['p90']:.1f}"],
            ["Output char mean / median / p90", f"{mixture_stats['output_char_stats']['mean']:.1f} / {mixture_stats['output_char_stats']['median']:.1f} / {mixture_stats['output_char_stats']['p90']:.1f}"],
            ["Source diversity count", str(len(mixture_stats.get("sources", {})))],
            ["Risk labels present", ", ".join(sorted(mixture_stats.get("risks", {}).keys())) or "none"],
        ],
        [5.6, 9.4],
    )

    story.append(PageBreak())

    add_heading(story, "18. Detailed Checkpoint Log Analysis", styles["h1"])
    add_paragraphs(
        story,
        [
            "This section presents per-step checkpoint telemetry from `checkpoint-292/trainer_state.json`. It is intentionally verbose to support viva-level technical defense and troubleshooting.",
            "Each row records step, epoch fraction, loss, learning rate, and gradient norm. Reviewing this table helps diagnose instability, scheduler errors, and gradient spikes.",
        ],
        styles["body"],
    )

    log_points = state292.get("log_points", [])
    if log_points:
        segments = chunk_list(log_points, 18)
        for idx, segment in enumerate(segments, start=1):
            add_heading(story, f"Checkpoint-292 Log Segment {idx}/{len(segments)}", styles["h2"])
            log_rows = [["Step", "Epoch", "Loss", "Learning Rate", "Grad Norm"]]
            for p in segment:
                log_rows.append(
                    [
                        str(p.get("step", "")),
                        f"{float(p.get('epoch', 0.0)):.4f}",
                        f"{float(p.get('loss', 0.0)):.6f}",
                        f"{float(p.get('learning_rate', 0.0)):.9f}",
                        f"{float(p.get('grad_norm', 0.0)):.6f}",
                    ]
                )
            add_table(story, log_rows, [2.0, 2.3, 2.5, 4.0, 3.2])
            if idx < len(segments):
                story.append(PageBreak())
    else:
        add_paragraphs(
            story,
            [
                "No per-step log points were available in trainer state.",
            ],
            styles["body"],
        )

    story.append(PageBreak())

    add_heading(story, "19. Pattern-Level Coverage Matrix", styles["h1"])
    add_paragraphs(
        story,
        [
            "This matrix links three perspectives: (1) deterministic rule support in pipeline, (2) observed training tag frequency, and (3) benchmark presence. This helps identify coverage gaps systematically.",
        ],
        styles["body"],
    )

    benchmark_pattern_hits: dict[str, int] = {}
    for row in benchmark_rows:
        for pat in row.get("legacy_patterns", []) if isinstance(row.get("legacy_patterns"), list) else []:
            benchmark_pattern_hits[pat] = benchmark_pattern_hits.get(pat, 0) + 1

    train_tags = mixture_stats.get("tags", {})
    coverage_rows = [["Pattern", "Deterministic Rule", "Train Tag Count", "Benchmark Presence", "Notes"]]
    coverage_spec = [
        ("print_statement", "yes", train_tags.get("print_statement", 0), benchmark_pattern_hits.get("print_statement", 0), "core syntax rewrite"),
        ("xrange", "yes", train_tags.get("xrange", 0), benchmark_pattern_hits.get("xrange", 0), "iterator API migration"),
        ("raw_input", "yes", train_tags.get("raw_input", 0), benchmark_pattern_hits.get("raw_input", 0), "input API migration"),
        ("except_as", "yes", train_tags.get("except_as", 0), benchmark_pattern_hits.get("except_as", 0), "exception binding syntax"),
        ("has_key", "yes", train_tags.get("has_key", 0), benchmark_pattern_hits.get("has_key", 0), "dictionary membership migration"),
        ("iteritems", "yes", train_tags.get("iteritems", 0), benchmark_pattern_hits.get("iteritems", 0), "dict iterator API"),
        ("iterkeys", "yes", train_tags.get("iterkeys", 0), benchmark_pattern_hits.get("iterkeys", 0), "dict iterator API"),
        ("itervalues", "yes", train_tags.get("itervalues", 0), benchmark_pattern_hits.get("itervalues", 0), "dict iterator API"),
        ("unicode", "yes", train_tags.get("unicode", 0), benchmark_pattern_hits.get("unicode", 0), "text type migration"),
        ("long", "yes", train_tags.get("long", 0), benchmark_pattern_hits.get("long", 0), "integer type migration"),
        ("basestring", "yes", train_tags.get("basestring", 0), benchmark_pattern_hits.get("basestring", 0), "type alias migration"),
        ("backtick_repr", "yes", train_tags.get("backtick_repr", 0), benchmark_pattern_hits.get("backtick_repr", 0), "Python 1.x/2.x repr shorthand"),
        ("apply_builtin", "yes", train_tags.get("apply_builtin", 0), benchmark_pattern_hits.get("apply_builtin", 0), "legacy function-apply idiom"),
    ]
    for pat, rule, train_count, bench_count, note in coverage_spec:
        coverage_rows.append([pat, rule, str(train_count), "yes" if bench_count > 0 else "no", note])
    add_table(story, coverage_rows, [2.7, 2.2, 2.5, 2.7, 5.9])

    story.append(PageBreak())

    add_heading(story, "20. Sample-by-Sample Modernization Casebook", styles["h1"])
    add_paragraphs(
        story,
        [
            "This casebook section provides concrete before/after examples from the active datasets. It is included to make training intent auditable and to support examiner-level discussion of what the model is expected to learn.",
        ],
        styles["body"],
    )

    casebook_rows: list[dict[str, Any]] = []
    if seed_rows:
        casebook_rows.extend(seed_rows[:8])
    if modernization_rows:
        casebook_rows.extend(modernization_rows[:8])
    if not casebook_rows and mixture_rows:
        casebook_rows.extend(mixture_rows[:10])

    for idx, row in enumerate(casebook_rows, start=1):
        instruction = trim_text(str(row.get("instruction", "")), 180)
        source = str(row.get("source") or row.get("mixture_source") or "local")
        risk = str(row.get("risk", "n/a"))
        add_heading(story, f"Case {idx}: {instruction}", styles["h2"])
        add_paragraphs(
            story,
            [
                f"Source: {source} | Risk label: {risk}",
            ],
            styles["body"],
            gap=0.1,
        )
        input_snippet = trim_text(str(row.get("input", "")), 520).replace("\r", "")
        output_snippet = trim_text(str(row.get("output", "")), 520).replace("\r", "")
        story.append(Preformatted("Input:\n" + input_snippet, styles["code"]))
        story.append(Spacer(1, 0.08 * cm))
        story.append(Preformatted("Target Output:\n" + output_snippet, styles["code"]))
        story.append(Spacer(1, 0.16 * cm))

        if idx % 2 == 0 and idx < len(casebook_rows):
            story.append(PageBreak())

    story.append(PageBreak())

    add_heading(story, "Appendix A: Full Command Reference", styles["h1"])
    cmd_text = [
        "python3 ml/build_seed_modernization_dataset.py",
        "python3 ml/curate_dataset.py",
        "python3 ml/build_training_mixture.py",
        "python3 ml/train_modernizer_unsloth.py --data-path ml/data/training_mixture.jsonl",
        "python3 ml/train_modernizer_colab.py --data-path /content/training_mixture.jsonl",
        "python3 ml/evaluate_modernizer.py",
        "python3 ml/evaluate_modernizer.py --enable-ml --adapter-path ml/models/nebula-modernizer-qwen25-1.5b --base-model Qwen/Qwen2.5-Coder-1.5B-Instruct",
        "python3 ml/infer_modernizer.py --adapter-path ml/models/nebula-modernizer-qwen25-1.5b --code \"for i in xrange(3):\\n    print i\"",
        "python3 -m uvicorn main:app --reload",
    ]
    story.append(Preformatted("\n".join(cmd_text), styles["code"]))
    story.append(Spacer(1, 0.24 * cm))

    add_heading(story, "Appendix B: Key Code Excerpts", styles["h1"])
    excerpt_blocks = [
        ("train_modernizer_unsloth.py (core setup)", code_excerpt(ROOT / "ml" / "train_modernizer_unsloth.py", 52, 143)),
        ("build_training_mixture.py (weighting logic)", code_excerpt(ROOT / "ml" / "build_training_mixture.py", 1, 61)),
        ("evaluate_modernizer.py (benchmark flow)", code_excerpt(ROOT / "ml" / "evaluate_modernizer.py", 1, 134)),
    ]
    for title, block in excerpt_blocks:
        add_heading(story, title, styles["h2"])
        story.append(Preformatted(block, styles["code"]))
        story.append(Spacer(1, 0.18 * cm))

    story.append(PageBreak())

    add_heading(story, "Appendix C: Dataset Snapshots", styles["h1"])
    add_paragraphs(
        story,
        [
            "Below are abbreviated examples from active dataset files for auditability. Long payloads are trimmed to keep report readable.",
        ],
        styles["body"],
    )

    snapshot_rows = [["File", "Instruction (trimmed)", "Input snippet (trimmed)", "Output snippet (trimmed)"]]
    for file_path in [SEED_DATASET, MODERNIZATION_TRAIN, TRAINING_MIXTURE]:
        rows = load_jsonl(file_path)
        sample = rows[0] if rows else {}
        snapshot_rows.append(
            [
                file_path.name,
                str(sample.get("instruction", ""))[:90],
                str(sample.get("input", ""))[:120].replace("\n", "\\n"),
                str(sample.get("output", ""))[:120].replace("\n", "\\n"),
            ]
        )
    add_table(story, snapshot_rows, [3.2, 3.3, 4.0, 4.5])

    story.append(PageBreak())

    add_heading(story, "Appendix D: Full Training Log Dump", styles["h1"])
    add_paragraphs(
        story,
        [
            "Raw training telemetry (checkpoint-292) is presented below in tabular segments for full transparency.",
        ],
        styles["body"],
    )
    if log_points:
        dump_segments = chunk_list(log_points, 24)
        for idx, segment in enumerate(dump_segments, start=1):
            add_heading(story, f"Log Dump Segment {idx}/{len(dump_segments)}", styles["h2"])
            dump_rows = [["Step", "Epoch", "Loss", "Learning Rate", "Grad Norm"]]
            for p in segment:
                dump_rows.append(
                    [
                        str(p.get("step", "")),
                        f"{float(p.get('epoch', 0.0)):.4f}",
                        f"{float(p.get('loss', 0.0)):.6f}",
                        f"{float(p.get('learning_rate', 0.0)):.9f}",
                        f"{float(p.get('grad_norm', 0.0)):.6f}",
                    ]
                )
            add_table(story, dump_rows, [2.0, 2.3, 2.5, 4.0, 3.2])
            if idx < len(dump_segments):
                story.append(PageBreak())
    else:
        add_paragraphs(story, ["No log points available."], styles["body"])

    story.append(PageBreak())

    add_heading(story, "Appendix E: Colab Cell-by-Cell Guide", styles["h1"])
    add_paragraphs(
        story,
        [
            "This guide maps the practical notebook flow used for LoRA fine-tuning on Colab T4/L4 GPU.",
            "Each block is intentionally short so viva examiners can follow the complete lifecycle quickly.",
        ],
        styles["body"],
    )
    colab_guide = [
        "Cell 1 - Runtime check",
        "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No GPU')",
        "",
        "Cell 2 - Install dependencies",
        "!pip -q install --upgrade unsloth datasets peft trl accelerate sentencepiece transformers",
        "",
        "Cell 3 - Upload dataset",
        "from google.colab import files",
        "uploaded = files.upload()",
        "DATA_PATH = '/content/training_mixture.jsonl'",
        "",
        "Cell 4 - Build Dataset object and prompt formatting",
        "load jsonl -> Dataset.from_list(...) -> shuffle -> map(formatting_prompts_func)",
        "",
        "Cell 5 - Load base model in 4-bit and attach LoRA",
        "FastLanguageModel.from_pretrained(... load_in_4bit=True)",
        "FastLanguageModel.get_peft_model(r=16, target_modules=[...])",
        "",
        "Cell 6 - Trainer config",
        "SFTConfig(output_dir=..., batch_size, grad_accum, lr, epochs, scheduler='cosine')",
        "",
        "Cell 7 - Train and save",
        "trainer.train()",
        "model.save_pretrained(output_dir); tokenizer.save_pretrained(output_dir)",
        "",
        "Cell 8 - Package and download adapter",
        "zip adapter directory and download to local machine",
        "",
        "Cell 9 - Local integration",
        "Place adapter under ml/models/nebula-modernizer-qwen25-1.5b",
        "Run ml/evaluate_modernizer.py and app endpoints.",
    ]
    story.append(Preformatted("\n".join(colab_guide), styles["code"]))
    story.append(Spacer(1, 0.2 * cm))

    story.append(PageBreak())

    add_heading(story, "Appendix F: File Inventory (ML Folder)", styles["h1"])
    ml_dir = ROOT / "ml"
    inventory_rows = [["Path", "Type", "Approx Size"]]
    for path in sorted(ml_dir.glob("*")):
        size = ""
        if path.is_file():
            size = f"{round(path.stat().st_size / 1024, 1)} KB"
        inventory_rows.append([path.name, "file" if path.is_file() else "directory", size])
    add_table(story, inventory_rows, [7.0, 3.0, 4.0])

    add_paragraphs(
        story,
        [
            "End of report.",
            "This document can be regenerated with: `python3 docs/generate_ml_training_in_depth_report.py`",
        ],
        styles["body"],
    )

    def draw_page_background(canvas_obj, doc_obj):
        canvas_obj.saveState()
        w, h = A4
        canvas_obj.setFillColor(colors.HexColor("#090d14"))
        canvas_obj.rect(0, 0, w, h, fill=1, stroke=0)
        canvas_obj.setFillColor(colors.HexColor("#0f1724"))
        canvas_obj.rect(0.5 * cm, 0.5 * cm, w - 1 * cm, h - 1 * cm, fill=0, stroke=1)
        canvas_obj.setFillColor(colors.HexColor("#7a8aa3"))
        canvas_obj.setFont("Helvetica", 8.5)
        canvas_obj.drawRightString(w - 0.9 * cm, 0.7 * cm, f"Page {doc_obj.page}")
        canvas_obj.drawString(0.9 * cm, 0.7 * cm, "Helix AI - ML Training In-Depth")
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=draw_page_background, onLaterPages=draw_page_background)


def main() -> None:
    build_report()
    print(f"Wrote {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
