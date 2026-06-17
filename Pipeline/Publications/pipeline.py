## Pipeline 
## Calls train_classifiers and classify_run in sequence.

from datetime import datetime

from S0_ML_training import main as train_classifiers
from S1_query_dimensions import main as query_dimensions
from S2_ML_classification import main as classify_run
from S3_query_reverse import main as query_reverse

# CONFIG 
# edit parameters for this run here

# Shared paths
DB_PATH           = 'publications.db'
SCOPE_MODEL_PATH  = 'models/LR_scope.joblib'
PILLAR_MODEL_PATH = 'models/LR_pillar.joblib'
THRESHOLD_PATH    = 'models/LR_scope_threshold.txt'

# create run table path with date and time of run
date = datetime.today().strftime("%y%m%d_%H%M")
RUN_TABLE = f'run_{date}'
REVERSE_TABLE = RUN_TABLE + '_reverse'

# QUERY
STRINGS_FILE = 'dimensions_search_publications.txt'
YEAR = 2025

# Training
TRAINING_TABLE  = 'publications_new_training'
EMBEDDINGS_PATH_TRAIN = 'embeddings/embeddings_new_training.npy'

# Classification run
EMBEDDINGS_PATH_RUN = 'embeddings/embeddings_' + RUN_TABLE + '.npy'
EMBEDDINGS_PATH_REVERSE = 'embeddings/embeddings_' + REVERSE_TABLE + '.npy'

# START OF SCRIPT

# Step 0: Train classifiers on new + all existing training data
# train_classifiers(
#     DB_PATH='publications_training.db',
#     TRAINING_TABLE=TRAINING_TABLE,
#     EMBEDDINGS_PATH=EMBEDDINGS_PATH_TRAIN,
#     SCOPE_MODEL_PATH=SCOPE_MODEL_PATH,
#     PILLAR_MODEL_PATH=PILLAR_MODEL_PATH,
#     THRESHOLD_PATH=THRESHOLD_PATH,
# )

# Step 1: Query dimensions for publications
print("\nStarting Step 1: Query dimensions for publications.")

query_dimensions(
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    STRINGS_FILE=STRINGS_FILE,
    YEAR=YEAR,
)

# Step 2: Classify the queried publications
print("\nStarting Step 2: Classification of queried publications.")

classify_run(
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    EMBEDDINGS_PATH=EMBEDDINGS_PATH_RUN,
    SCOPE_MODEL_PATH=SCOPE_MODEL_PATH,
    PILLAR_MODEL_PATH=PILLAR_MODEL_PATH,
    THRESHOLD_PATH=THRESHOLD_PATH,
)

# Step 3: Reverse search for top researchers
print("\nStarting Step 3: Reverse search for Researcher ID's.")

query_reverse(
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    REVERSE_TABLE=REVERSE_TABLE,
    YEAR=YEAR,
)

# Step 4: Classify the additional publications from reverse search
print("\nStarting Step 4: Classification of additional publications from reverse search.")

classify_run(
    DB_PATH=DB_PATH,
    RUN_TABLE=REVERSE_TABLE,
    EMBEDDINGS_PATH=EMBEDDINGS_PATH_REVERSE,
    SCOPE_MODEL_PATH=SCOPE_MODEL_PATH,
    PILLAR_MODEL_PATH=PILLAR_MODEL_PATH,
    THRESHOLD_PATH=THRESHOLD_PATH,
)

