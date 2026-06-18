## Pipeline 
## Calls train_classifiers and classify_run in sequence.

from dimensions_query import main as dimensions_query
from train_classifiers import main as train_classifiers
from classify_run import main as classify_run

# CONFIG 
# edit parameters for this run here

# Shared paths
DB_PATH           = 'publications.db'
SCOPE_MODEL_PATH  = 'Models/LR_scope.joblib'
PILLAR_MODEL_PATH = 'Models/LR_pillar.joblib'
THRESHOLD_PATH    = 'Models/LR_scope_threshold.txt'
RUN_TABLE         = 'data_run_1'

# QUERY
STRINGS_FILE = 'dimensions_search_publications.txt'
YEAR = 2025

# Training
TRAINING_TABLE  = 'publications_new_training'
EMBEDDINGS_PATH_TRAIN = 'embeddings_new_training.npy'

# Classification run
EMBEDDINGS_PATH_RUN = 'embeddings_run_1.npy'

# START OF SCRIPT

# Step 1: Train classifiers on new + all existing training data
train_classifiers(
    DB_PATH='publications_training.db',
    TRAINING_TABLE=TRAINING_TABLE,
    EMBEDDINGS_PATH=EMBEDDINGS_PATH_TRAIN,
    SCOPE_MODEL_PATH=SCOPE_MODEL_PATH,
    PILLAR_MODEL_PATH=PILLAR_MODEL_PATH,
    THRESHOLD_PATH=THRESHOLD_PATH,
)

# Step 2: Query dimensions for publications
dimensions_query(
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    STRINGS_FILE=STRINGS_FILE,
    YEAR=YEAR,
)

# Step 3: Classify the queried publications
classify_run(
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    EMBEDDINGS_PATH=EMBEDDINGS_PATH_RUN,
    SCOPE_MODEL_PATH=SCOPE_MODEL_PATH,
    PILLAR_MODEL_PATH=PILLAR_MODEL_PATH,
    THRESHOLD_PATH=THRESHOLD_PATH,
)
