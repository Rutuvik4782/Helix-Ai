# Viva Notes

## What is the project?

Helix AI is an autonomous multi-agent platform for modernizing legacy Python code into current Python-compatible code.

## Why is this project needed?

Legacy Python code often contains outdated syntax and APIs that are incompatible with modern Python versions. Manual migration is slow and risky. Helix AI reduces effort by automating detection, planning, transformation, and validation.

## What makes it different?

- focused on legacy Python modernization
- multi-agent pipeline
- deterministic transformation engine
- optional ML reasoning layer
- validation-driven safety checks
- unified diff and report generation

## Why not use only an LLM?

A pure LLM rewrite is risky for code migration. This project uses deterministic rules for supported upgrades and reserves ML for reasoning, ranking, and future fallback suggestions.

## What are the supported transformations?

- `print` statement to `print(...)`
- `xrange` to `range`
- `raw_input` to `input`
- `except X, e` to `except X as e`
- `<>` to `!=`
- `.iteritems()` to `.items()`
- `.iterkeys()` to `.keys()`
- `.itervalues()` to `.values()`
- `.has_key(x)` to `x in dict`
- `unicode` / `basestring` to `str`
- `long` to `int`

## Where is ML used?

The project includes:

- curated modernization dataset
- public dataset integration strategy
- Unsloth fine-tuning pipeline
- optional runtime inference hook

The current deterministic rule engine is used as the trusted modernization path, while the ML layer is prepared for model-assisted modernization after training.

## What are the limitations?

- current deterministic upgrades focus mainly on Python 2.x and early legacy syntax patterns
- semantic migration for all edge cases is not fully automatic
- full model fine-tuning requires external training infrastructure

## How did you verify the system?

- automated unit and API tests
- evaluation benchmark for modernization cases
- syntax and validation checks
- unified diff and report generation for each modernization run
