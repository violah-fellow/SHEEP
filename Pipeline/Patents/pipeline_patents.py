## Pipeline for Patent Data collection and classification
## Calls S0-S3 in sequence with checkpoint/resume support.
## To restart a completed or unwanted run, delete its status file from status_logs/.

import os
from datetime import datetime

from Helper_pipeline_functions import save_status, mark_done, find_incomplete_run
from S0_ML_training import main as train_classifiers
from S1_query_dimensions import main as query_dimensions
from S2_ML_classification import main as classify_run
from S3_query_reverse import main as query_reverse

# CONFIG 
# edit parameters for this run here

# Resuming inclompete runs rom status_log
RESUME = True

# Shared paths
DB_PATH           = 'patents.db'
DB_PATH_TRAINING  = 'patents_training.db'
SCOPE_MODEL_PATH  = 'models/LR_scope.joblib'
PILLAR_MODEL_PATH = 'models/LR_pillar.joblib'
THRESHOLD_PATH    = 'models/LR_scope_threshold.txt'
KEY_PATH          = '../.env'

# Query
STRINGS_FILE    = 'dimensions_search_patents.txt'
CPC_SEARCH_FILE = 'CPC_for_query.txt'
CPC_FILTER_FILE = 'CPC_for_filter.txt'
YEAR            = 2025

# Training
TRAINING_TABLE        = 'patents_raw'
EMBEDDINGS_TABLE      = 'patents_embeddings'
EMBEDDINGS_PATH_TRAIN = 'embeddings/embeddings_new_training.npy'
MAX_FN                = 0.01

STATUS_DIR = 'status_logs'
os.makedirs(STATUS_DIR, exist_ok=True)


# START SCRIPT

# Resolve config: resume incomplete run or start fresh
incomplete = find_incomplete_run(STATUS_DIR) if RESUME else None

if incomplete:
    cfg = incomplete['config']
    status = incomplete
    print(f"Resuming run '{cfg['RUN_TABLE']}'"
          f"\ncompleted steps: {[k for k,v in status['steps'].items() if v == 'done']}")
else:
    date = datetime.today().strftime("%y%m%d_%H%M")
    RUN_TABLE             = f'run_{date}'
    REVERSE_TABLE         = RUN_TABLE + '_reverse'
    EMBEDDINGS_PATH_RUN     = f'embeddings/embeddings_{RUN_TABLE}.npy'

    cfg = {
        'DB_PATH':                DB_PATH,
        'DB_PATH_TRAINING':       DB_PATH_TRAINING,
        'KEY_PATH':               KEY_PATH,
        'RUN_TABLE':              RUN_TABLE,
        'REVERSE_TABLE':          REVERSE_TABLE,
        'STRINGS_FILE':           STRINGS_FILE,
        'CPC_SEARCH_FILE':        CPC_SEARCH_FILE,
        'CPC_FILTER_FILE':        CPC_FILTER_FILE,
        'YEAR':                   YEAR,
        'SCOPE_MODEL_PATH':       SCOPE_MODEL_PATH,
        'PILLAR_MODEL_PATH':      PILLAR_MODEL_PATH,
        'THRESHOLD_PATH':         THRESHOLD_PATH,
        'MAX_FN':                 MAX_FN,
        'TRAINING_TABLE':         TRAINING_TABLE,
        'EMBEDDINGS_TABLE':       EMBEDDINGS_TABLE,
        'EMBEDDINGS_PATH_TRAIN':  EMBEDDINGS_PATH_TRAIN,
        'EMBEDDINGS_PATH_RUN':    EMBEDDINGS_PATH_RUN,
    }
    status = {
        'config': cfg,
        'steps': {
            'train':            'pending',
            'query':            'pending',
            'classify':         'pending',
            'reverse_query':    'pending',
        }
    }
    save_status(status, STATUS_DIR)
    print(f"Starting new run '{cfg['RUN_TABLE']}'")


# Step 0: Train classifiers
if status['steps']['train'] != 'done':
    print("\nStarting Step 0: Train classifiers.")
    train_classifiers(
        DB_PATH=cfg['DB_PATH_TRAINING'],
        TRAINING_TABLE=cfg['TRAINING_TABLE'],
        EMBEDDINGS_TABLE=cfg['EMBEDDINGS_TABLE'],
        EMBEDDINGS_PATH=cfg['EMBEDDINGS_PATH_TRAIN'],
        SCOPE_MODEL_PATH=cfg['SCOPE_MODEL_PATH'],
        PILLAR_MODEL_PATH=cfg['PILLAR_MODEL_PATH'],
        THRESHOLD_PATH=cfg['THRESHOLD_PATH'],
        MAX_FN=cfg['MAX_FN'],
    )
    mark_done(status, 'train', STATUS_DIR)
else:
    print("\nStep 0 (train) already done, skipping.")

# Step 1: Query Dimensions
if status['steps']['query'] != 'done':
    print("\nStarting Step 1: Query Dimensions for publications.")
    query_dimensions(
        KEY_PATH=cfg['KEY_PATH'],
        DB_PATH=cfg['DB_PATH'],
        RUN_TABLE=cfg['RUN_TABLE'],
        STRINGS_FILE=cfg['STRINGS_FILE'],
        CPC_SEARCH_FILE=cfg['CPC_SEARCH_FILE'],
        CPC_FILTER_FILE=cfg['CPC_FILTER_FILE'],
        YEAR=cfg['YEAR'],
    )
    mark_done(status, 'query', STATUS_DIR)
else:
    print("\nStep 1 (query) already done, skipping.")

# Step 2: Classify queried publications
if status['steps']['classify'] != 'done':
    print("\nStarting Step 2: Classify queried publications.")
    classify_run(
        DB_PATH=cfg['DB_PATH'],
        RUN_TABLE=cfg['RUN_TABLE'],
        EMBEDDINGS_TABLE=cfg['EMBEDDINGS_TABLE'],
        EMBEDDINGS_PATH=cfg['EMBEDDINGS_PATH_RUN'],
        SCOPE_MODEL_PATH=cfg['SCOPE_MODEL_PATH'],
        PILLAR_MODEL_PATH=cfg['PILLAR_MODEL_PATH'],
        THRESHOLD_PATH=cfg['THRESHOLD_PATH'],
    )
    mark_done(status, 'classify', STATUS_DIR)
else:
    print("\nStep 2 (classify) already done, skipping.")

# Step 3: Reverse search
if status['steps']['reverse_query'] != 'done':
    print("\nStarting Step 3: Reverse search for researcher IDs.")
    query_reverse(
        KEY_PATH=cfg['KEY_PATH'],
        DB_PATH=cfg['DB_PATH'],
        RUN_TABLE=cfg['RUN_TABLE'],
        REVERSE_TABLE=cfg['REVERSE_TABLE'],
        YEAR=cfg['YEAR'],
    )
    mark_done(status, 'reverse_query', STATUS_DIR)
else:
    print("\nStep 3 (reverse_query) already done, skipping.")

