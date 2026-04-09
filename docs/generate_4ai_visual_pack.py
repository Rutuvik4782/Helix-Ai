from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "docs" / "assets"
PDF_DIR = ROOT / "docs" / "pdfs"
META_PATH = ASSETS_DIR / "helix_4ai_comparison_meta.json"
METRICS_PATH = ASSETS_DIR / "helix_standout_metrics.json"
PDF_PATH = PDF_DIR / "HELIX_AI_4AI_COMPARISON_PACK.pdf"


def load_inputs() -> tuple[list[str], list[str], dict[str, list[float]], dict]:
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    tools = meta["tools"]
    metric_names = meta["metrics"]
    scores = meta["scores"]
    return tools, metric_names, scores, metrics


def setup_style() -> None:
    plt.style.use("dark_background")
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.facecolor": "#0f1217",
            "figure.facecolor": "#0b0d12",
            "axes.edgecolor": "#3a4050",
            "axes.labelcolor": "#d6deeb",
            "xtick.color": "#c7d2e0",
            "ytick.color": "#c7d2e0",
            "grid.color": "#2f3645",
        }
    )


def tool_colors(tools: list[str]) -> list[str]:
    palette = {
        "Helix AI": "#40d68f",
        "OpenAI Codex/ChatGPT": "#4aa8ff",
        "GitHub Copilot": "#7d8cff",
        "Claude Code": "#ff9f4a",
        "Cursor": "#f06d8f",
    }
    return [palette.get(tool, "#a0aec0") for tool in tools]


def save_grouped_metric_chart(
    tools: list[str], metric_names: list[str], scores: dict[str, list[float]]
) -> Path:
    data = np.array([scores[t] for t in tools])
    x = np.arange(len(metric_names))
    width = 0.15
    colors = tool_colors(tools)

    fig, ax = plt.subplots(figsize=(15, 8))
    for i, tool in enumerate(tools):
        ax.bar(
            x + (i - 2) * width,
            data[i],
            width=width,
            label=tool,
            color=colors[i],
            alpha=0.95,
        )

    ax.set_title("Helix AI vs 4 AI Tools: Capability Breakdown", fontsize=17, pad=16)
    ax.set_ylabel("Score (0-10)")
    ax.set_ylim(0, 10)
    ax.set_xticks(x)
    ax.set_xticklabels(metric_names, rotation=16, ha="right")
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(ncol=2, frameon=False, loc="upper left")
    fig.tight_layout()

    out = ASSETS_DIR / "helix-4ai-metric-grouped-bars-v2.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def save_weighted_leaderboard(
    tools: list[str], metric_names: list[str], scores: dict[str, list[float]]
) -> tuple[Path, dict[str, float], dict[str, float]]:
    weights = {
        "Legacy Modernization Fit": 0.30,
        "Deterministic Control": 0.20,
        "Validation Visibility": 0.20,
        "Agentic Workflow Support": 0.15,
        "General Coding Breadth": 0.10,
        "Ecosystem Reach": 0.05,
    }

    weighted = {}
    legacy_focus = {}
    for tool in tools:
        tool_map = {metric_names[i]: scores[tool][i] for i in range(len(metric_names))}
        weighted[tool] = sum(tool_map[m] * w for m, w in weights.items())
        legacy_focus[tool] = (
            0.40 * tool_map["Legacy Modernization Fit"]
            + 0.30 * tool_map["Deterministic Control"]
            + 0.30 * tool_map["Validation Visibility"]
        )

    ordered = sorted(weighted.items(), key=lambda kv: kv[1], reverse=True)
    sorted_tools = [item[0] for item in ordered]
    sorted_scores = [item[1] for item in ordered]
    colors = tool_colors(sorted_tools)

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(sorted_tools, sorted_scores, color=colors, alpha=0.95)
    ax.invert_yaxis()
    ax.set_xlim(0, 10)
    ax.set_xlabel("Weighted Score (0-10)")
    ax.set_title("Weighted Ranking for Legacy Modernization Use-Case", fontsize=16, pad=14)
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    for bar, val in zip(bars, sorted_scores):
        ax.text(val + 0.08, bar.get_y() + bar.get_height() / 2, f"{val:.2f}", va="center")
    fig.tight_layout()

    out = ASSETS_DIR / "helix-4ai-weighted-overall-score.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out, weighted, legacy_focus


def save_legacy_focus_chart(tools: list[str], legacy_focus: dict[str, float]) -> Path:
    ordered = sorted(legacy_focus.items(), key=lambda kv: kv[1], reverse=True)
    labels = [x[0] for x in ordered]
    values = [x[1] for x in ordered]
    colors = tool_colors(labels)

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(labels, values, color=colors, alpha=0.95)
    ax.set_ylim(0, 10)
    ax.set_ylabel("Legacy Modernization Confidence (0-10)")
    ax.set_title("Legacy-First Confidence Index", fontsize=16, pad=14)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for i, val in enumerate(values):
        ax.text(i, val + 0.12, f"{val:.2f}", ha="center")
    plt.xticks(rotation=10)
    fig.tight_layout()

    out = ASSETS_DIR / "helix-4ai-legacy-confidence-index.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def save_breadth_control_scatter(
    tools: list[str], metric_names: list[str], scores: dict[str, list[float]]
) -> Path:
    idx = {m: i for i, m in enumerate(metric_names)}
    colors = tool_colors(tools)

    fig, ax = plt.subplots(figsize=(12, 8))
    for i, tool in enumerate(tools):
        breadth = scores[tool][idx["General Coding Breadth"]]
        control = (
            scores[tool][idx["Legacy Modernization Fit"]]
            + scores[tool][idx["Deterministic Control"]]
            + scores[tool][idx["Validation Visibility"]]
        ) / 3.0
        ecosystem = scores[tool][idx["Ecosystem Reach"]]
        bubble = 180 + ecosystem * 45
        ax.scatter(breadth, control, s=bubble, color=colors[i], alpha=0.9, edgecolors="white")
        ax.text(breadth + 0.04, control + 0.04, tool, fontsize=10)

    ax.set_xlim(4.0, 10.0)
    ax.set_ylim(5.5, 10.0)
    ax.set_xlabel("General Coding Breadth")
    ax.set_ylabel("Modernization Control (Legacy+Deterministic+Validation)")
    ax.set_title("Breadth vs Control Tradeoff (Bubble = Ecosystem Reach)", fontsize=15, pad=14)
    ax.grid(linestyle="--", alpha=0.35)
    fig.tight_layout()

    out = ASSETS_DIR / "helix-4ai-breadth-vs-control-scatter.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def save_gap_to_helix_chart(
    tools: list[str], metric_names: list[str], scores: dict[str, list[float]]
) -> Path:
    helix = np.array(scores["Helix AI"])
    competitors = [t for t in tools if t != "Helix AI"]
    key_metrics = [
        "Legacy Modernization Fit",
        "Deterministic Control",
        "Validation Visibility",
        "Agentic Workflow Support",
    ]
    idx = [metric_names.index(m) for m in key_metrics]
    x = np.arange(len(key_metrics))
    width = 0.18

    fig, ax = plt.subplots(figsize=(14, 8))
    colors = tool_colors(competitors)
    for i, tool in enumerate(competitors):
        gap = helix[idx] - np.array(scores[tool])[idx]
        ax.bar(
            x + (i - 1.5) * width,
            gap,
            width=width,
            label=tool,
            color=colors[i],
            alpha=0.95,
        )

    ax.axhline(0, color="#94a3b8", linewidth=1.1)
    ax.set_xticks(x)
    ax.set_xticklabels(key_metrics, rotation=10)
    ax.set_ylabel("Score Gap (Helix - Competitor)")
    ax.set_title(
        "Where Competitors Trail Helix on Legacy-Migration Critical Metrics",
        fontsize=16,
        pad=14,
    )
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()

    out = ASSETS_DIR / "helix-4ai-gap-to-helix-critical-metrics.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def save_migration_risk_chart(legacy_focus: dict[str, float]) -> Path:
    tools = list(legacy_focus.keys())
    risk = {tool: max(0.0, 10.0 - legacy_focus[tool]) for tool in tools}
    ordered = sorted(risk.items(), key=lambda kv: kv[1], reverse=True)
    labels = [x[0] for x in ordered]
    values = [x[1] for x in ordered]
    colors = tool_colors(labels)

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.barh(labels, values, color=colors, alpha=0.95)
    ax.invert_yaxis()
    ax.set_xlim(0, 4)
    ax.set_xlabel("Modernization Risk Index (10 - Legacy Confidence)")
    ax.set_title(
        "Relative Migration Risk for Legacy Python Use-Case (Lower is Better)",
        fontsize=16,
        pad=14,
    )
    ax.grid(axis="x", linestyle="--", alpha=0.35)
    for bar, val in zip(bars, values):
        ax.text(val + 0.05, bar.get_y() + bar.get_height() / 2, f"{val:.2f}", va="center")
    fig.tight_layout()

    out = ASSETS_DIR / "helix-4ai-migration-risk-index.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def save_helix_evidence_dashboard(metrics: dict) -> Path:
    tests_ran = int(metrics.get("unit_tests", {}).get("ran", 0))
    tests_ok = bool(metrics.get("unit_tests", {}).get("ok", False))
    test_score = 100.0 if tests_ran > 0 and tests_ok else 0.0

    benchmark_size = int(metrics.get("benchmark", {}).get("size", 0))
    benchmark_pass = int(metrics.get("benchmark", {}).get("rule_pass", 0))
    benchmark_score = (benchmark_pass / benchmark_size * 100.0) if benchmark_size else 0.0

    rule_count = int(metrics.get("legacy_rule_count", 0))
    suggestion_count = int(metrics.get("suggestion_mapping_count", 0))
    rule_score = min(100.0, (rule_count / 15.0) * 100.0)
    suggestion_score = min(100.0, (suggestion_count / 15.0) * 100.0)

    labels = [
        "Unit Test Pass",
        "Benchmark Rule Pass",
        "Rule Coverage",
        "Suggestion Map Coverage",
    ]
    values = [test_score, benchmark_score, rule_score, suggestion_score]
    colors = ["#40d68f", "#52c7ea", "#f6b84f", "#e27dff"]

    fig, ax = plt.subplots(figsize=(12, 7))
    bars = ax.bar(labels, values, color=colors, alpha=0.95)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Evidence Score (%)")
    ax.set_title("Helix AI Evidence Dashboard (Local Project Measurements)", fontsize=16, pad=14)
    ax.grid(axis="y", linestyle="--", alpha=0.35)
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + 2,
            f"{val:.1f}%",
            ha="center",
            va="bottom",
            fontsize=11,
        )
    fig.tight_layout()

    out = ASSETS_DIR / "helix-proof-evidence-dashboard-v2.png"
    fig.savefig(out, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return out


def write_summary_json(weighted: dict[str, float], legacy_focus: dict[str, float]) -> Path:
    out = ASSETS_DIR / "helix_4ai_visual_summary.json"
    payload = {
        "weighted_ranking": weighted,
        "legacy_confidence_index": legacy_focus,
        "weights": {
            "Legacy Modernization Fit": 0.30,
            "Deterministic Control": 0.20,
            "Validation Visibility": 0.20,
            "Agentic Workflow Support": 0.15,
            "General Coding Breadth": 0.10,
            "Ecosystem Reach": 0.05,
        },
        "note": "Scores are rubric-based positioning for legacy modernization. Helix evidence dashboard uses local project test/benchmark counts.",
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def draw_pdf_page(pdf: canvas.Canvas, title: str, subtitle: str, image_path: Path) -> None:
    page_w, page_h = A4
    pdf.setFillColorRGB(0.04, 0.05, 0.07)
    pdf.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    pdf.setFillColorRGB(0.85, 0.9, 0.98)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(40, page_h - 42, title)
    pdf.setFont("Helvetica", 10)
    pdf.setFillColorRGB(0.72, 0.78, 0.88)
    pdf.drawString(40, page_h - 58, subtitle)

    reader = ImageReader(str(image_path))
    iw, ih = reader.getSize()
    max_w = page_w - 80
    max_h = page_h - 120
    scale = min(max_w / iw, max_h / ih)
    w = iw * scale
    h = ih * scale
    x = (page_w - w) / 2
    y = 35 + (max_h - h) / 2
    pdf.drawImage(reader, x, y, width=w, height=h, preserveAspectRatio=True, mask="auto")
    pdf.showPage()


def draw_positioning_page(pdf: canvas.Canvas) -> None:
    page_w, page_h = A4
    pdf.setFillColorRGB(0.04, 0.05, 0.07)
    pdf.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    pdf.setFillColorRGB(0.86, 0.92, 1.0)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(40, page_h - 44, "Helix AI Positioning: Standout vs Competitor Weakness")

    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColorRGB(0.33, 0.89, 0.64)
    pdf.drawString(40, page_h - 78, "Where Helix AI stands out")
    pdf.setFillColorRGB(0.8, 0.85, 0.93)
    pdf.setFont("Helvetica", 10.5)
    y = page_h - 98
    standout = [
        "Built for Python-legacy modernization first, not as a generic code assistant.",
        "Deterministic rule + validation pipeline gives reproducible, auditable migrations.",
        "Diff-first workflow and issue-level explanation improve review confidence.",
        "Domain-focused checks reduce silent misses on classic Python 1.x/2.x patterns.",
    ]
    for line in standout:
        pdf.drawString(48, y, f"- {line}")
        y -= 17

    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColorRGB(1.0, 0.67, 0.42)
    y -= 8
    pdf.drawString(40, y, "Where competitors are weaker for this specific use-case")
    y -= 20
    pdf.setFillColorRGB(0.8, 0.85, 0.93)
    pdf.setFont("Helvetica", 10.5)
    gaps = [
        "General-purpose tools optimize for broad coding help, not strict legacy migration guarantees.",
        "Modernization decisions can vary across runs unless constrained by custom guardrails.",
        "Validation visibility is often lower for legacy-specific semantic rewrites.",
        "Less targeted handling for Python-era edge patterns without project-specific rule packs.",
    ]
    for line in gaps:
        pdf.drawString(48, y, f"- {line}")
        y -= 17

    pdf.setFont("Helvetica-Bold", 12)
    pdf.setFillColorRGB(0.47, 0.77, 1.0)
    y -= 8
    pdf.drawString(40, y, "Fair note")
    pdf.setFillColorRGB(0.8, 0.85, 0.93)
    pdf.setFont("Helvetica", 10.5)
    y -= 20
    fair = [
        "Tools like Codex/Copilot/Claude/Cursor are stronger for broad coding breadth and ecosystem integrations.",
        "For this project goal, Helix's specialization gives it the strategic edge in migration reliability.",
    ]
    for line in fair:
        pdf.drawString(48, y, f"- {line}")
        y -= 17

    pdf.showPage()


def build_pdf(image_map: dict[str, tuple[str, str]]) -> None:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(PDF_PATH), pagesize=A4)

    w, h = A4
    pdf.setFillColorRGB(0.03, 0.04, 0.06)
    pdf.rect(0, 0, w, h, fill=1, stroke=0)
    pdf.setFillColorRGB(0.85, 0.92, 1.0)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(56, h - 90, "HELIX AI")
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(56, h - 118, "4-AI Visual Comparison Pack")
    pdf.setFont("Helvetica", 11)
    pdf.setFillColorRGB(0.72, 0.79, 0.88)
    pdf.drawString(
        56,
        h - 148,
        "Use-case focus: legacy Python modernization with deterministic review and validation.",
    )
    pdf.drawString(
        56,
        h - 166,
        "Note: comparative scores are rubric-based positioning; Helix dashboard includes local measured evidence.",
    )
    pdf.showPage()
    draw_positioning_page(pdf)

    for img_name, (title, subtitle) in image_map.items():
        path = ASSETS_DIR / img_name
        if path.exists():
            draw_pdf_page(pdf, title, subtitle, path)

    pdf.save()


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()

    tools, metric_names, scores, metrics = load_inputs()

    generated = []
    generated.append(save_grouped_metric_chart(tools, metric_names, scores))
    weighted_chart, weighted, legacy_focus = save_weighted_leaderboard(tools, metric_names, scores)
    generated.append(weighted_chart)
    generated.append(save_legacy_focus_chart(tools, legacy_focus))
    generated.append(save_breadth_control_scatter(tools, metric_names, scores))
    generated.append(save_gap_to_helix_chart(tools, metric_names, scores))
    generated.append(save_migration_risk_chart(legacy_focus))
    generated.append(save_helix_evidence_dashboard(metrics))
    summary_path = write_summary_json(weighted, legacy_focus)

    image_map = {
        "helix-4ai-comparison-matrix.png": (
            "Capability Matrix",
            "Baseline matrix used for side-by-side tool positioning.",
        ),
        "helix-4ai-legacy-fit-ranking.png": (
            "Legacy Fit Ranking",
            "Ranking by legacy modernization suitability for this project goal.",
        ),
        "helix-4ai-breadth-tradeoff.png": (
            "Breadth Tradeoff",
            "General coding breadth compared with modernization specialization.",
        ),
        "helix-4ai-metric-grouped-bars-v2.png": (
            "Expanded Metric Bars",
            "Grouped bars across all six comparison dimensions.",
        ),
        "helix-4ai-weighted-overall-score.png": (
            "Weighted Overall Score",
            "Weights prioritize legacy migration reliability and deterministic control.",
        ),
        "helix-4ai-legacy-confidence-index.png": (
            "Legacy Confidence Index",
            "Focused score from legacy fit, deterministic control, and validation visibility.",
        ),
        "helix-4ai-breadth-vs-control-scatter.png": (
            "Breadth vs Control",
            "Bubble chart where bubble size represents ecosystem reach.",
        ),
        "helix-4ai-gap-to-helix-critical-metrics.png": (
            "Gap to Helix on Critical Metrics",
            "Positive values indicate where a competitor trails Helix in migration-critical dimensions.",
        ),
        "helix-4ai-migration-risk-index.png": (
            "Migration Risk Index",
            "Derived from legacy confidence; lower values indicate safer legacy modernization behavior.",
        ),
        "helix-proof-evidence-dashboard-v2.png": (
            "Helix Evidence Dashboard",
            "Local project metrics: unit tests, benchmark pass, and rule/suggestion coverage.",
        ),
    }
    build_pdf(image_map)

    print("Generated files:")
    for p in generated:
        print(f"- {p}")
    print(f"- {summary_path}")
    print(f"- {PDF_PATH}")


if __name__ == "__main__":
    main()
