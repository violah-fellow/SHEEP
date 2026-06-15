## Training script: embed new training data and train LR classifiers (scope + pillar)
## All parameters that need to be changed are defined in the CONFIG section below.

import importlib.util, sys, os

# ============================================================
# CONFIG — edit these before running
# ============================================================

# --- Database ---
# path to DuckDB database
DB_PATH = 'publications_training.db'
# table containing new training data                 
TRAINING_TABLE = 'publications_training_new'         

# --- Columns ---
# columns concatenated for embedding (title, abstract)
TEXT_COLUMNS   = ('title', 'abstract')      
# column with scope labels ('in' / 'out')
SCOPE_COLUMN   = 'scope'             
# column with pillar labels       
PILLAR_COLUMN  = 'pillar'                   

# --- Embeddings ---
# checkpoint + final save path for embeddings
EMBEDDINGS_PATH = 'embeddings_training_new.npy'   

# --- Model save paths ---
SCOPE_MODEL_PATH   = 'Models/LR_scope.joblib'
PILLAR_MODEL_PATH  = 'Models/LR_pillar.joblib'
THRESHOLD_PATH     = 'Models/LR_scope_threshold.txt' 

# --- Classifier hyperparameters (passed as kwargs to train_scope / train_pillar) ---
SCOPE_MODEL_KWARGS  = {'C': 0.1, 'class_weight': 'balanced'}
PILLAR_MODEL_KWARGS = {'C': 0.1, 'class_weight': 'balanced'}

# ============================================================
# END CONFIG
# ============================================================


# --- Load ML_pipeline_functions from the same directory as this script ---
_script_dir = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    'ML_pipeline_functions',
    os.path.join(_script_dir, 'ML_pipeline_functions.py')
)
mlf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mlf)

import duckdb
import numpy as np

# --- 1. Load training data, removing entries already in publications_embeddings ---
print("Loading training data.")
db = duckdb.connect(database=DB_PATH)
data = db.sql(f"SELECT * FROM {TRAINING_TABLE}").df()
print(f"{len(data)} rows loaded from '{TRAINING_TABLE}'")

# Remove rows already present in publications_embeddings (if the table exists)
existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()
if 'publications_embeddings' in existing_tables:
    existing_ids = db.sql("SELECT id FROM publications_embeddings").df()['id']
    n_before = len(data)
    data = data[~data['id'].isin(existing_ids)].reset_index(drop=True)
    print(f"{n_before - len(data)} rows already in 'publications_embeddings', skipped.")
print(f"{len(data)} rows remaining for embedding and training.")

# Build text column from title + abstract
data['text'] = data[TEXT_COLUMNS[0]] + ' [SEP] ' + data[TEXT_COLUMNS[1]]

# Convert scope labels to binary integers
data['scope_binary'] = (data[SCOPE_COLUMN] == 'in').astype(int)
print(f"Scope label distribution:\n{data['scope_binary'].value_counts().to_string()}")
print(f"Pillar label distribution:\n{data[PILLAR_COLUMN].value_counts().to_string()}")

# --- 2. Load SPECTER2 model ---
print("\nLoading SPECTER2 model.")
model, tokenizer = mlf.load_specter()

# Check token sizes (adds 'truncated' column to data)
mlf.check_token_size(data, text_column='text', tokenizer=tokenizer, add_column=True)
print(f"Truncated entries: {data['truncated'].sum()}")

# --- 3. Compute embeddings ---
print("\nComputing embeddings.")
embeddings = mlf.get_embeddings(
    data,
    text_column='text',
    file_path=EMBEDDINGS_PATH,
    model=model,
    tokenizer=tokenizer,
    checkpoint=True
)

# --- 4. Train scope classifier (LR) ---
print("\nTraining scope classifier.")
scope_labels = data['scope_binary'].values
classifier_scope, threshold = mlf.train_scope(
    embeddings,
    scope_labels,
    model_path=SCOPE_MODEL_PATH,
    **SCOPE_MODEL_KWARGS
)

# Save threshold to file
with open(THRESHOLD_PATH, 'w') as f:
    f.write(str(threshold))
print(f"Scope model saved to: {SCOPE_MODEL_PATH}")
print(f"Threshold saved to: {THRESHOLD_PATH}  (value: {threshold:.3f})")

# --- 5. Train pillar classifier (LR) ---
print("\nTraining pillar classifier.")
pillar_labels = data[PILLAR_COLUMN].values
classifier_pillar = mlf.train_pillar(
    embeddings,
    pillar_labels,
    model_path=PILLAR_MODEL_PATH,
    **PILLAR_MODEL_KWARGS
)
print(f"Pillar model saved to: {PILLAR_MODEL_PATH}")

# --- 6. Append new rows (all columns + embeddings) to publications_embeddings ---
print("\nAppending to 'publications_embeddings' table.")

data['embeddings'] = list(embeddings)
db.register('data', data)

if 'publications_embeddings' in existing_tables:
    db.sql("INSERT INTO publications_embeddings SELECT * FROM data")
else:
    db.sql("CREATE TABLE publications_embeddings AS SELECT * FROM data")

print(f"{len(data)} rows appended to 'publications_embeddings'.")

db.close()
print("\nDone.")
