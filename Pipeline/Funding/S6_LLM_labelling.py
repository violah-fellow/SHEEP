## LLM labelling script: assign a "Research category" label to in-scope grants via Claude's
## Batch API, then promote successfully-labelled Dimensions-sourced grants from funding_classified
## into funding_curated, and fill in Research category for the Grants-Tracker-sourced rows S2
## already appended into funding_curated (Airtable has no Research category field at all).
## Submits a batch, waits (polling) for it to complete, then parses and writes results back.
## Can be run standalone (uses CONFIG defaults) or imported and called as main().
## Currently implements Research category only - End product type, Award purpose, and
## Sub-AP pillar are deferred (no prompts exist for them yet).
## Standalone, not wired into pipeline_funding.py - run whenever there's newly-scoped data
## ready to label, same as S5.

import os
import re

# CONFIG
# edit parameters for this run here

# Anthropic API
# path to API key
KEY_PATH = '../../.env'

# Database
# path to DuckDB database (self-contained in Pipeline/Funding, mirrors Publications)
DB_PATH = 'funding.db'
# Dimensions-sourced staging table (populated by S1/S3, curated by S5)
CLASSIFICATION_TABLE = 'funding_classified'
# final GFI-tracker-schema dataset (built/grown by S2)
CURATED_TABLE = 'funding_curated'
SCOPE_COL = 'scope_curated'
PILLAR_COL = 'pillar_curated'

# LLM
# one system prompt per pillar - each asks for an independent TRUE/FALSE per category
PROMPT_PATHS = {
    'PB': 'llm_prompts/rescat_prompt_grants_PB.md',
    'F':  'llm_prompts/rescat_prompt_grants_F.md',
    'CM': 'llm_prompts/rescat_prompt_grants_CM.md',
    'CC': 'llm_prompts/rescat_prompt_grants_CC.md',
}
LLM_MODEL_LABEL = 'claude-sonnet-4-6'  # or 'claude-haiku-4-5' for cheap test runs
MAX_TOKENS = 300
TEMPERATURE = 0.0

# Batch
# directory for batch submission metadata
BATCH_DIR = 'batch_jobs'
# how often to check whether the batch has finished
POLL_INTERVAL_SECONDS = 600
# None = auto-resume the newest incomplete labelling run, or mint a fresh timestamped one
RUN_LABEL = None

# START OF SCRIPT

# Category lists per pillar - verbatim from llm_prompts/rescat_prompt_grants_{PILLAR}.md
PB_CATS = ["Crop development", "Strain development", "Ingredient optimisation", "End product formulation",
           "Texturization methods", "Food safety & quality", "Health & nutrition",
           "Consumer & market research", "Impact Assessments", "Other"]
F_CATS = ["Feedstocks", "Target molecule selection", "Strain development", "Bioprocess design",
          "Ingredient optimisation", "End product formulation", "Texturization methods",
          "Food safety & quality", "Health & nutrition", "Consumer & market research",
          "Impact Assessments", "Other"]
CM_CATS = ["Cell line development", "Cell culture media", "Bioprocess design", "Scaffolding",
           "End product formulation", "Food safety & quality", "Health & nutrition",
           "Consumer & market research", "Impact Assessments", "Other"]
CC_CATS = ["Crop development", "Cell line development", "Strain development", "Target molecule selection",
           "Cell culture media", "Feedstocks", "Bioprocess design", "Scaffolding", "Ingredient optimisation",
           "End product formulation", "Texturization methods", "Food safety & quality", "Health & nutrition",
           "Consumer & market research", "Impact Assessments", "Other"]
PILLAR_CATS = {'PB': PB_CATS, 'F': F_CATS, 'CM': CM_CATS, 'CC': CC_CATS}

# Maps funding_curated's 'AP pillar' values (full names, Grants Tracker origin) to the same
# short pillar codes funding_classified's pillar_curated already uses. Lowercased for lookup
# so case variants (e.g. a stray "Plant-Based") still resolve.
AP_PILLAR_TO_CODE = {
    'plant-based': 'PB',
    'fermentation': 'F',
    'cultivated': 'CM',
    'cross-cutting': 'CC',
}

# Column mapping from funding_classified's Dimensions-derived schema into funding_curated's
# tracker schema - copied verbatim from S2_grant_deduplication.ipynb's col_map, so promoted
# rows land in the same columns S2 itself would gap-fill into.
PROMOTE_COL_MAP = {
    'Title translated':                              'Title',
    'Title':                                         'Original title',
    'Abstract translated':                           'Abstract',
    'Total amount':                                  'Total amount',
    'Currency':                                      'Currency',
    'Total amount (USD)':                            'Total amount (USD)',
    'Total amount (EUR)':                             'Total amount (EUR)',
    'Start date':                                    'Project start date',
    'Start Year':                                    'Year project started',
    'End Year':                                      'End date',
    'State of standardized research organization':   'PI organisation state',
    'Country of standardized research organization': 'PI organisation country',
    'Funder':                                        'Funder name',
    'Funder Country':                                'Funder Country',
    'Source Linkout':                                'URL for announcement',
}


def _field_name(category):
    """Sanitize a category name into a valid tool-schema property name (e.g.
    'Food safety & quality' -> 'Food_safety_quality')."""
    return re.sub(r'\W+', '_', category).strip('_')


def _build_category_tool(categories):
    field_map = {_field_name(c): c for c in categories}  # sanitized field name -> real category name
    return {
        "name": "label_research_category",
        "description": "Record TRUE/FALSE for each research category the grant substantively funds.",
        "input_schema": {
            "type": "object",
            "properties": {fname: {"type": "boolean"} for fname in field_map},
            "required": list(field_map.keys()),
        }
    }, field_map


def _derive_research_category(tool_input, field_map):
    """Comma-joined string of every category flagged TRUE, suppressing 'Other' whenever at
    least one specific category is also TRUE (matches genai_rescat_testing.ipynb's validated logic)."""
    true_labels = [orig for fname, orig in field_map.items() if tool_input.get(fname) is True]
    if 'Other' in true_labels and len(true_labels) > 1:
        true_labels = [l for l in true_labels if l != 'Other']
    return ', '.join(true_labels) if true_labels else 'NA'


def _split_first_rest(value):
    """Split a semicolon-joined value into (first entry, remaining entries joined) - mirrors
    Funding_dedup_helpers.gap_fill_researchers_and_orgs' splitting convention."""
    import pandas as pd
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None, None
    parts = [p.strip() for p in str(value).split(';') if p.strip()]
    if not parts:
        return None, None
    return parts[0], ('; '.join(parts[1:]) or None)


def main(
    KEY_PATH=KEY_PATH,
    DB_PATH=DB_PATH,
    CLASSIFICATION_TABLE=CLASSIFICATION_TABLE,
    CURATED_TABLE=CURATED_TABLE,
    SCOPE_COL=SCOPE_COL,
    PILLAR_COL=PILLAR_COL,
    PROMPT_PATHS=PROMPT_PATHS,
    LLM_MODEL_LABEL=LLM_MODEL_LABEL,
    MAX_TOKENS=MAX_TOKENS,
    TEMPERATURE=TEMPERATURE,
    BATCH_DIR=BATCH_DIR,
    POLL_INTERVAL_SECONDS=POLL_INTERVAL_SECONDS,
    RUN_LABEL=RUN_LABEL,
):
    import time
    import json
    from datetime import datetime
    from pathlib import Path

    import anthropic
    import duckdb
    import pandas as pd
    from dotenv import load_dotenv

    # 1. Authenticate with the Anthropic API
    print("\nConnecting to the Anthropic API")

    load_dotenv(KEY_PATH)
    client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

    batch_dir = Path(BATCH_DIR)
    batch_dir.mkdir(exist_ok=True)

    # 2. Resolve RUN_LABEL: resume the newest incomplete labelling batch, or mint a fresh one
    def find_incomplete_batch():
        files = sorted(
            (f for f in os.listdir(batch_dir) if f.endswith('_llm_labelling.json')),
            reverse=True,
        )
        for fname in files:
            meta = json.loads((batch_dir / fname).read_text(encoding="utf-8"))
            if 'completed_at' not in meta:
                return meta['run_label']
        return None

    if RUN_LABEL is None:
        RUN_LABEL = find_incomplete_batch()
    if RUN_LABEL is None:
        RUN_LABEL = f"labelling_{datetime.today().strftime('%y%m%d_%H%M')}"

    metadata_path = batch_dir / f"{RUN_LABEL}_llm_labelling.json"

    def mark_batch_complete():
        metadata["completed_at"] = datetime.now().isoformat()
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    db = duckdb.connect(database=DB_PATH)

    # 3. Load and filter input data (only when submitting fresh - a resumed run doesn't need to
    # re-derive eligibility, just which pillar each custom_id belongs to, which comes from the
    # persisted metadata instead)
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        batch_id = metadata["batch_id"]
        print(f"Found existing labelling batch '{RUN_LABEL}': {batch_id}. Resuming without resubmitting.")
        curated_df = db.sql(f"SELECT * FROM {CURATED_TABLE}").df()
    else:
        # --- Pool A: funding_classified, scope_curated == 'in', not yet attempted ---
        fc = db.sql(f"SELECT * FROM {CLASSIFICATION_TABLE}").df()
        if 'category_status_LLM' not in fc.columns:
            fc['category_status_LLM'] = None
        pool_a = fc[
            (fc[SCOPE_COL] == 'in') &
            (fc['category_status_LLM'].isna()) &
            (fc[PILLAR_COL].isin(PILLAR_CATS.keys()))
        ].reset_index(drop=True)
        print(f"Pool A (funding_classified, {SCOPE_COL}='in', not yet attempted): {len(pool_a)} rows")

        # --- Pool B: funding_curated, Database == 'airtable', Research category missing ---
        curated_df = db.sql(f"SELECT * FROM {CURATED_TABLE}").df()
        curated_df['_ap_pillar_code'] = (
            curated_df['AP pillar'].astype(str).str.strip().str.lower().map(AP_PILLAR_TO_CODE)
        )
        research_cat_missing = (
            curated_df['Research category'].isna() |
            (curated_df['Research category'].astype(str).str.strip() == '')
        )
        pool_b_mask = (
            (curated_df['Database'] == 'airtable') &
            research_cat_missing &
            curated_df['_ap_pillar_code'].isin(PILLAR_CATS.keys())
        )
        pool_b_indices = curated_df[pool_b_mask].index.tolist()
        print(f"Pool B ({CURATED_TABLE}, Database='airtable', Research category missing): {len(pool_b_indices)} rows")

        if len(pool_a) == 0 and len(pool_b_indices) == 0:
            print("No new rows to label. Skipping batch.")
            db.close()
            return

        # 4. Build per-pillar system prompts + tool schemas up front
        system_prompts = {}
        tools = {}
        for pillar, prompt_path in PROMPT_PATHS.items():
            with open(prompt_path, "r", encoding="utf-8") as f:
                system_prompts[pillar] = f.read().strip()
            tools[pillar], _ = _build_category_tool(PILLAR_CATS[pillar])

        def build_request(custom_id, pillar, title, abstract):
            user_message = f"Title: {title}\n\nAbstract: {abstract}"
            return {
                "custom_id": custom_id,
                "params": {
                    "model": LLM_MODEL_LABEL,
                    "max_tokens": MAX_TOKENS,
                    "temperature": TEMPERATURE,
                    "system": [
                        {"type": "text", "text": system_prompts[pillar], "cache_control": {"type": "ephemeral"}}
                    ],
                    "messages": [{"role": "user", "content": user_message}],
                    "tools": [tools[pillar]],
                    "tool_choice": {"type": "tool", "name": "label_research_category"},
                }
            }

        batch_requests = []
        pillar_by_custom_id = {}

        for _, row in pool_a.iterrows():
            custom_id = f"fc_{row['Grant ID'].replace('.', '_')}"
            pillar = row[PILLAR_COL]
            batch_requests.append(build_request(custom_id, pillar, row['Title translated'], row['Abstract translated']))
            pillar_by_custom_id[custom_id] = pillar

        for idx in pool_b_indices:
            row = curated_df.loc[idx]
            custom_id = f"curated_{idx}"
            pillar = row['_ap_pillar_code']
            batch_requests.append(build_request(custom_id, pillar, row['Title'], row['Abstract']))
            pillar_by_custom_id[custom_id] = pillar

        print(f"\nSubmitting batch of {len(batch_requests)} requests")
        batch = client.messages.batches.create(requests=batch_requests)
        batch_id = batch.id
        print(f"Batch ID: {batch_id}")
        print(f"Status:   {batch.processing_status}")

        metadata = {
            "batch_id": batch_id,
            "run_label": RUN_LABEL,
            "model": LLM_MODEL_LABEL,
            "n_records": len(batch_requests),
            "pillar_by_custom_id": pillar_by_custom_id,
            "created_at": datetime.now().isoformat(),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(f"Batch metadata saved to {metadata_path}")

    # 5. Poll until the batch has finished
    print("\nWaiting for batch to complete")

    while True:
        batch = client.messages.batches.retrieve(batch_id)
        print(f"Processing status: {batch.processing_status}   Counts: {batch.request_counts}")
        if batch.processing_status == "ended":
            break
        time.sleep(POLL_INTERVAL_SECONDS)

    # 6. Retrieve and parse results
    print("\nRetrieving results")

    pillar_by_custom_id = metadata["pillar_by_custom_id"]
    field_maps = {pillar: _build_category_tool(cats)[1] for pillar, cats in PILLAR_CATS.items()}

    date_labelling = datetime.today().strftime('%y%m%d')
    fc_results = []       # rows destined for funding_classified (Pool A)
    curated_updates = {}  # {curated_df index: research_category} for Pool B

    for result in client.messages.batches.results(batch_id):
        custom_id = result.custom_id
        pillar = pillar_by_custom_id.get(custom_id)
        field_map = field_maps.get(pillar, {})

        if result.result.type == "succeeded":
            content = result.result.message.content
            stop_reason = result.result.message.stop_reason
            tool_block = next((b for b in content if b.type == "tool_use"), None)
            if tool_block:
                research_category = _derive_research_category(tool_block.input, field_map)
                status = "ok"
            else:
                research_category = None
                status = "parse_error"
        else:
            stop_reason = None
            research_category = None
            status = result.result.type

        if custom_id.startswith("fc_"):
            grant_id = custom_id[len("fc_"):].replace("_", ".")
            fc_results.append({
                "Grant ID": grant_id,
                "research_category_LLM": research_category,
                "category_status_LLM": status,
                "category_stop_reason_LLM": stop_reason,
                "date_labelling": date_labelling,
            })
        elif custom_id.startswith("curated_"):
            idx = int(custom_id[len("curated_"):])
            if status == "ok":
                curated_updates[idx] = research_category

    # explicit columns so a batch containing only Pool B (or only Pool A) requests still has
    # the right shape, rather than a zero-column DataFrame when one pool is empty
    fc_results_df = pd.DataFrame(fc_results, columns=[
        "Grant ID", "research_category_LLM", "category_status_LLM",
        "category_stop_reason_LLM", "date_labelling",
    ])

    n_ok = (fc_results_df['category_status_LLM'] == 'ok').sum()
    print(f"Pool A results: {len(fc_results_df)} total, {n_ok} succeeded")
    print(f"Pool B results: {len(curated_updates)} rows updated with a Research category")

    # 7. Write Pool A diagnostic columns onto funding_classified
    if len(fc_results_df):
        llm_columns = {
            'research_category_LLM':    'VARCHAR',
            'category_status_LLM':      'VARCHAR',
            'category_stop_reason_LLM': 'VARCHAR',
            'date_labelling':           'VARCHAR',
        }
        for col, dtype in llm_columns.items():
            db.sql(f'ALTER TABLE {CLASSIFICATION_TABLE} ADD COLUMN IF NOT EXISTS {col} {dtype}')

        db.register('fc_results', fc_results_df)
        set_clause = ", ".join(f"{col} = fc_results.{col}" for col in llm_columns)
        db.sql(f"""
            UPDATE {CLASSIFICATION_TABLE}
            SET {set_clause}
            FROM fc_results
            WHERE {CLASSIFICATION_TABLE}."Grant ID" = fc_results."Grant ID"
        """)
        print(f"'{CLASSIFICATION_TABLE}' updated with labelling diagnostic columns for {len(fc_results_df)} rows.")

    # 8. Apply Pool B updates directly onto the in-memory funding_curated snapshot
    for idx, research_category in curated_updates.items():
        curated_df.at[idx, 'Research category'] = research_category

    # 9. Promote successfully-labelled, not-already-promoted Pool A rows into funding_curated.
    # Re-read funding_classified fresh (now including the diagnostic columns just written) and
    # filter in pandas, rather than build a dynamic SQL IN-list.
    already_promoted_ids = set(curated_df['Identification code'].dropna().astype(str))
    fc_full = db.sql(f"SELECT * FROM {CLASSIFICATION_TABLE}").df()
    to_promote = fc_full[
        (fc_full['category_status_LLM'] == 'ok') &
        (~fc_full['Grant ID'].astype(str).isin(already_promoted_ids))
    ]

    if len(to_promote):
        new_rows = []
        for _, row in to_promote.iterrows():
            new_row = {lrd_col: row.get(src_col) for src_col, lrd_col in PROMOTE_COL_MAP.items()}

            names_first, names_rest = _split_first_rest(row.get('Researchers'))
            if names_first:
                new_row['Project lead (PI)'] = names_first
                if names_rest:
                    new_row['Collaborator names'] = names_rest

            org_first, org_rest = _split_first_rest(row.get('Research Organization - standardized'))
            if org_first:
                new_row['PI organisation'] = org_first
                if org_rest:
                    new_row['Collaborator institutions'] = org_rest

            new_row['Database'] = 'Dimensions'
            new_row['Identification code'] = row['Grant ID']
            new_row['Research category'] = row.get('research_category_LLM')
            new_rows.append(new_row)

        new_rows_df = pd.DataFrame(new_rows).reindex(columns=[c for c in curated_df.columns if c != '_ap_pillar_code'])
        curated_df = pd.concat([curated_df, new_rows_df], ignore_index=True)
        print(f"Promoted {len(new_rows_df)} newly-labelled Dimensions grants into '{CURATED_TABLE}'.")
    else:
        print("No new Dimensions grants to promote.")

    # 10. Persist funding_curated once, atomically, with both Pool B updates and Pool A promotions
    curated_df = curated_df.drop(columns=['_ap_pillar_code'], errors='ignore')
    db.sql(f"CREATE OR REPLACE TABLE {CURATED_TABLE} AS SELECT * FROM curated_df")
    print(f"'{CURATED_TABLE}' rewritten with {len(curated_df)} total rows.")

    mark_batch_complete()
    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
