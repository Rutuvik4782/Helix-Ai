# Project Abstract

Helix AI is an autonomous multi-agent platform for legacy Python modernization. The system analyzes legacy Python code, detects outdated syntax and compatibility risks, plans migration steps, applies supported transformations, validates the result, and produces a modernization report with a unified diff.

The platform combines deterministic rule-based modernization with an optional ML reasoning layer. The rule engine ensures safe upgrades for common legacy constructs such as `print` statements, `xrange`, `raw_input`, old exception syntax, deprecated dictionary iteration APIs, `has_key`, and legacy type names. The ML layer is designed to support ranking, ambiguity resolution, and future fallback modernization suggestions after fine-tuning.

The architecture is organized around analyzer, suggester, critic, planner, execution, validation, and reporting components. A modern web interface provides analysis summaries, risk modes, execution logs, and diff views. The project also includes a curated dataset pipeline, public dataset integration strategy, evaluation scripts, and automated tests.

Helix AI is intended as a safer modernization prototype for legacy Python codebases rather than a general-purpose refactoring engine.
