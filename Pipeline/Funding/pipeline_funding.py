## Pipeline for Funding/Grants data collection, deduplication, and LLM scope screening.
## Calls S1 and S3 in sequence with checkpoint/resume support; S2 (deduplication) is a manual
## notebook step run by hand between them - see the printed instructions when the pipeline
## reaches that step.
## To restart a completed or unwanted run, delete its status file from status_logs/.

import os
import sys
import duckdb
from datetime import datetime

from Helper_pipeline_functions import save_status, mark_done, find_incomplete_run
from S1_query_dimensions import main as query_dimensions
from S3_LLM_scope import main as scope_llm

# CONFIG
# edit parameters for this run here

# Resuming incomplete runs from status_log
RESUME = True

# Shared paths
DB_PATH  = 'funding.db'  # self-contained in Pipeline/Funding, mirrors Publications
KEY_PATH = '../../.env'

# Query
STRINGS_FILE = 'dimensions_search_funding.txt'
YEAR         = 2025

# GenAI
LLM_MODEL_SCOPE = 'claude-sonnet-4-6'   # or 'claude-haiku-4-5' for cheap test runs
# path to the system prompt used for scoping
PROMPT_PATH = 'llm_prompts/scope_prompt_funding.md'

# Classification table (pipeline-owned, accumulates across runs)
CLASSIFICATION_TABLE = 'funding_classified'

STATUS_DIR = 'status_logs'
LOG_DIR    = 'run_logs'
os.makedirs(STATUS_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)


class _Tee:
    def __init__(self, *streams):
        self._streams = streams
    def write(self, data):
        for s in self._streams:
            s.write(data)
            s.flush()
    def flush(self):
        for s in self._streams:
            s.flush()


# START SCRIPT

# Resolve config: resume incomplete run or start fresh
incomplete = find_incomplete_run(STATUS_DIR) if RESUME else None

if incomplete:
    cfg = incomplete['config']
    status = incomplete
    _log_path = os.path.join(LOG_DIR, f"{cfg['RUN_TABLE']}.log")
    _log_file = open(_log_path, 'a', encoding='utf-8')
    sys.stdout = sys.stderr = _Tee(sys.__stdout__, _log_file)
    print(f"Resuming run '{cfg['RUN_TABLE']}'"
          f"\ncompleted steps: {[k for k,v in status['steps'].items() if v == 'done']}")
else:
    date = datetime.today().strftime("%y%m%d_%H%M")
    RUN_TABLE   = f'run_{date}'
    DEDUP_TABLE = RUN_TABLE + '_dedup'

    cfg = {
        'DB_PATH':               DB_PATH,
        'KEY_PATH':              KEY_PATH,
        'RUN_TABLE':             RUN_TABLE,
        'DEDUP_TABLE':           DEDUP_TABLE,
        'STRINGS_FILE':          STRINGS_FILE,
        'YEAR':                  YEAR,
        'LLM_MODEL_SCOPE':       LLM_MODEL_SCOPE,
        'PROMPT_PATH':           PROMPT_PATH,
        'CLASSIFICATION_TABLE':  CLASSIFICATION_TABLE,
    }
    status = {
        'config': cfg,
        'steps': {
            'query':     'pending',
            'dedup':     'pending',
            'llm_scope': 'pending',
        }
    }
    save_status(status, STATUS_DIR)
    _log_path = os.path.join(LOG_DIR, f"{RUN_TABLE}.log")
    _log_file = open(_log_path, 'w', encoding='utf-8')
    sys.stdout = sys.stderr = _Tee(sys.__stdout__, _log_file)
    print(f"Starting new run '{cfg['RUN_TABLE']}'")


# Step 1: Query Dimensions for grants
if status['steps']['query'] != 'done':
    print("\nStarting Step 1: Query Dimensions for grants.")
    query_dimensions(
        KEY_PATH=cfg['KEY_PATH'],
        DB_PATH=cfg['DB_PATH'],
        RUN_TABLE=cfg['RUN_TABLE'],
        CLASSIFICATION_TABLE=cfg['CLASSIFICATION_TABLE'],
        STRINGS_FILE=cfg['STRINGS_FILE'],
        YEAR=cfg['YEAR'],
    )
    mark_done(status, 'query', STATUS_DIR)
else:
    print("\nStep 1 (query) already done, skipping.")

# Step 2: Deduplicate against tracked/historical grants (manual notebook step)
if status['steps']['dedup'] != 'done':
    db = duckdb.connect(database=cfg['DB_PATH'])
    existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()
    db.close()
    if cfg['DEDUP_TABLE'] in existing_tables:
        print(f"\nFound '{cfg['DEDUP_TABLE']}' - dedup step complete, continuing.")
        mark_done(status, 'dedup', STATUS_DIR)
    else:
        print(f"\nStep 2 (dedup) requires a manual step:"
              f"\n  1. Run S2_grant_deduplication.ipynb with RUN_TABLE='{cfg['RUN_TABLE']}' as input."
              f"\n  2. Confirm its output is saved as table '{cfg['DEDUP_TABLE']}' in {cfg['DB_PATH']}."
              f"\n  3. Re-run this script to continue (it will pick up from here).")
        sys.exit(0)
else:
    print("\nStep 2 (dedup) already done, skipping.")

# Step 3: LLM scope classification
if status['steps']['llm_scope'] != 'done':
    print("\nStarting Step 3: LLM scope classification.")
    scope_llm(
        KEY_PATH=cfg['KEY_PATH'],
        DB_PATH=cfg['DB_PATH'],
        RUN_TABLE=cfg['RUN_TABLE'],
        DEDUP_TABLE=cfg['DEDUP_TABLE'],
        CLASSIFICATION_TABLE=cfg['CLASSIFICATION_TABLE'],
        PROMPT_PATH=cfg['PROMPT_PATH'],
        LLM_MODEL_SCOPE=cfg['LLM_MODEL_SCOPE'],
    )
    mark_done(status, 'llm_scope', STATUS_DIR)
else:
    print("\nStep 3 (llm_scope) already done, skipping.")

print(f"\nPipeline complete for run '{cfg['RUN_TABLE']}'.")
