from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "docs" / "assets"


def setup_style() -> None:
    plt.style.use("dark_background")
    plt.rcParams.update(
        {
            "font.size": 11,
            "figure.facecolor": "#07090f",
            "axes.facecolor": "#0d1018",
            "axes.edgecolor": "#3b4356",
            "axes.labelcolor": "#d8e1f0",
            "xtick.color": "#c7d2e0",
            "ytick.color": "#c7d2e0",
            "grid.color": "#2f3645",
        }
    )


def save_gantt() -> Path:
    out = ASSETS_DIR / "helix-timeline-nov-apr-gantt.png"

    months = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]
    phases = [
        ("Research + Problem Framing", 0.0, 1.0, "#f97316"),
        ("Architecture + Agent Contracts", 0.4, 1.6, "#f59e0b"),
        ("Backend Pipeline Core", 1.1, 3.0, "#38bdf8"),
        ("Frontend UX + Workflow", 2.0, 4.0, "#22c55e"),
        ("ML Dataset + Fine-Tune", 2.5, 4.8, "#a78bfa"),
        ("Testing + Evaluation", 3.2, 5.2, "#f43f5e"),
        ("Reports + Final Submission", 4.5, 6.0, "#eab308"),
    ]

    fig, ax = plt.subplots(figsize=(14, 8))
    y_pos = np.arange(len(phases))[::-1]

    for y, (name, start, end, color) in zip(y_pos, phases):
        ax.barh(y, end - start, left=start, color=color, height=0.6, alpha=0.95)
        ax.text(start + 0.05, y, name, va="center", ha="left", fontsize=10, color="#f8fafc")

    for m in range(len(months) + 1):
        ax.axvline(m, color="#1f2431", linewidth=1, alpha=0.8)

    ax.set_xlim(0, 6)
    ax.set_ylim(-1, len(phases))
    ax.set_xticks(np.arange(0.5, 6.5, 1.0))
    ax.set_xticklabels(months)
    ax.set_yticks([])
    ax.set_title("Helix AI Project Timeline (Nov to Apr) - Execution Gantt", fontsize=18, pad=16)
    ax.set_xlabel("Project Months")
    ax.grid(axis="x", linestyle="--", alpha=0.25)

    fig.tight_layout()
    fig.savefig(out, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return out


def save_roadmap() -> Path:
    out = ASSETS_DIR / "helix-timeline-nov-apr-roadmap.png"

    months = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]
    milestones = [
        "Idea + Scope Freeze",
        "Agentic Architecture\n+ Analyzer Rules",
        "Execution + Validation\nCore Complete",
        "UI Workflow + Run History\nIntegrated",
        "ML Training + Benchmark\nRuns Finalized",
        "In-Depth Reports +\nFinal Packaging",
    ]

    x = np.arange(len(months))
    y = np.zeros_like(x)
    milestone_colors = ["#f97316", "#f59e0b", "#38bdf8", "#22c55e", "#a78bfa", "#eab308"]

    fig, ax = plt.subplots(figsize=(14, 5.8))
    ax.plot(x, y, color="#64748b", linewidth=3, alpha=0.8)

    for i, (mx, text, color) in enumerate(zip(x, milestones, milestone_colors)):
        ax.scatter(mx, 0, s=240, color=color, edgecolors="#ffffff", linewidths=1.2, zorder=3)
        offset = 0.22 if i % 2 == 0 else -0.25
        va = "bottom" if i % 2 == 0 else "top"
        ax.text(mx, offset, text, ha="center", va=va, fontsize=10, color="#e2e8f0")

    ax.set_xlim(-0.5, len(months) - 0.5)
    ax.set_ylim(-0.6, 0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.set_yticks([])
    ax.set_title("Helix AI Project Timeline (Nov to Apr) - Milestone Roadmap", fontsize=18, pad=14)
    ax.grid(False)

    fig.tight_layout()
    fig.savefig(out, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return out


def save_progress() -> Path:
    out = ASSETS_DIR / "helix-timeline-nov-apr-progress.png"

    months = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]
    x = np.arange(len(months))
    planned = np.array([10, 25, 45, 65, 85, 100])
    actual = np.array([12, 28, 52, 70, 88, 100])

    fig, ax = plt.subplots(figsize=(14, 6.2))
    ax.plot(x, planned, color="#94a3b8", linewidth=2.5, linestyle="--", marker="o", label="Planned Progress")
    ax.plot(x, actual, color="#22d3ee", linewidth=3, marker="o", label="Actual Progress")
    ax.fill_between(x, actual, color="#0891b2", alpha=0.15)

    for i, value in enumerate(actual):
        ax.text(i, value + 2.5, f"{value}%", ha="center", fontsize=10, color="#e2e8f0")

    ax.set_xticks(x)
    ax.set_xticklabels(months)
    ax.set_ylim(0, 110)
    ax.set_ylabel("Completion (%)")
    ax.set_title("Helix AI Project Timeline (Nov to Apr) - Progress Curve", fontsize=18, pad=14)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.legend(frameon=False, loc="upper left")

    fig.tight_layout()
    fig.savefig(out, dpi=240, bbox_inches="tight")
    plt.close(fig)
    return out


def main() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()
    outputs = [save_gantt(), save_roadmap(), save_progress()]
    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
