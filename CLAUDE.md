# Project Name: SHEEP

## Context
Dual pipeline to assess whether publications are relevant to alternative proteins (in-scope/out-of-scope) and apply category labels. Two pipeline variants: an ML pipeline (embedding-based classifiers) and a GenAI pipeline (LLM-based). Publications are the initial scope; Patents and Grants will be added later.

Data is sourced from the Dimensions API and stored in a DuckDB database.

## ML Pipeline approach
Stage 1: binary scope classifier — predict in/out-of-scope from publication metadata (title + abstract).
Stage 2: category classifier — assign topic labels to in-scope records.
Both stages use sentence-transformer embeddings as features, trained on labelled data in `Publications/publications.db`.

## GenAI Pipeline approach
Uses Claude (via Anthropic API) to scope and label publications.

## Tech stack
- Language: Python 3.12 (Jupyter notebooks), R (data curation)
- Environment: conda, env name `sheep` — activate with `conda activate sheep`
- Database: DuckDB (`Publications/publications.db`)
- Key libraries: scikit-learn, PyTorch, sentence-transformers, transformers (HuggingFace), dimcli
- APIs: Dimensions API (data source), Anthropic/Claude API (GenAI pipeline)
- Credentials: stored in `.env` (gitignored); see `.env.example` for required keys

## Repo layout
- `Publications/Publications_Data/` — raw Excel exports from Dimensions; **never modify directly**
- `Publications/publications_curated.csv` — cleaned, curated publication records
- `Publications/publications.db` — DuckDB database (working data)
- `Publications/SQL_setup_publications.ipynb` — database setup and schema
- `Publications/ML/` — ML pipeline notebooks
- `Publications/GenAI/` — GenAI pipeline notebooks
- `Publications/Data_curation_publications.r` — R script for initial data cleaning
- `SQL_Tutorial/` — learning materials, not part of the pipeline
- `.env` — API keys (gitignored)

## Things to avoid
- **Do not call paid LLM APIs (OpenAI, Anthropic) from one-off scripts in a session.** Use Claude Code's own agents instead. Direct API calls bill on top of the subscription.
- **Do not run destructive commands without asking.** `rm -rf`, `git push --force`, dropping tables, overwriting uncommitted work, force-deleting branches. Confirm first.
- **Do not commit `.env`, credentials, API keys, or large binary scrape dumps.** Add them to `.gitignore` before they show up in `git status`.
- **Do not write speculative comments in code** ("# this might break if..."). Comments explain non-obvious *why*, nothing else.
- **Do not modify raw data** in `Publications_Data/` or write directly to DuckDB tables without a script.

## Status
<!-- Update this as the project evolves -->
- ML pipeline: Stage 1 binary classifier in progress (`ML/Optimisation_Stage1.ipynb`)
- GenAI pipeline: early experiments (`GenAI/test.ipynb`)
- Database: set up and populated
