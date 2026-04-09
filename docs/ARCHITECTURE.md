# Architecture Overview

## Core flow

1. User submits legacy Python code
2. Analyzer detects legacy syntax and probable source version
3. Suggester builds modernization candidates
4. Critic scores migration safety
5. Planner orders executable transformations
6. Execution core applies deterministic upgrades
7. Validation core blocks unsafe or incomplete output
8. Report generator returns logs, diff, and migration summary

## Major modules

- `agents/analyzer.py`
  Detects legacy patterns, semantic risks, and probable legacy version.

- `agents/suggester.py`
  Maps detected issues to concrete modernization suggestions.

- `agents/critic.py`
  Assigns safety scores and warning states to planned changes.

- `agents/planner.py`
  Chooses and orders transformations for execution.

- `core/execution.py`
  Applies sequential deterministic code upgrades.

- `core/validation.py`
  Verifies syntax, rejects leftover legacy constructs, and flags risky behavior.

- `core/ml_reasoner.py`
  Optional adapter-backed ML reasoning layer for future model-assisted modernization.

- `core/report_generator.py`
  Produces the modernization report and validation summary.

## ML path

- local curated modernization data
- public dataset ingestion scripts
- weighted training mixture builder
- LoRA fine-tuning path using Unsloth
- optional runtime inference hook through environment variables

## Safety model

- rule-based transforms are the authoritative execution path
- validation is required before accepting migrated output
- semantic risks such as division semantics and text/bytes migration are surfaced as warnings
- ML suggestions are auxiliary unless validated
