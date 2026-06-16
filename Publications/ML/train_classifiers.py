## Training script: embed new training data and train LR classifiers (scope + pillar)
## Can be run standalone (uses CONFIG defaults) or imported and called as main().

import importlib.util, sys, os

# CONFIG 
# edit parameters for this run here

# --- Database ---
# path to DuckDB database
DB_PATH = 'publications_training.db'
# table containing new training data
TRAINING_TABLE = 'publications_new_training'

# --- Columns ---
# columns concatenated for embedding (title, abstract)
TEXT_COLUMNS = ('title', 'abstract')
# column with scope labels ('in' / 'out')
SCOPE_COLUMN = 'scope'
# column with pillar labels
PILLAR_COLUMN = 'pillar'

# --- Embeddings ---
# checkpoint + final save path for embeddings
EMBEDDINGS_PATH = 'embeddings_new_training.npy'

# --- Model save paths ---
SCOPE_MODEL_PATH  = 'Models/LR_scope.joblib'
PILLAR_MODEL_PATH = 'Models/LR_pillar.joblib'
THRESHOLD_PATH    = 'Models/LR_scope_threshold.txt'

# --- Classifier hyperparameters (passed as kwargs to train_scope / train_pillar) ---
SCOPE_MODEL_KWARGS  = {'C': 0.1, 'class_weight': 'balanced'}
PILLAR_MODEL_KWARGS = {'C': 0.1, 'class_weight': 'balanced'}

# START OF SCRIPT


def main(
    DB_PATH=DB_PATH,
    TRAINING_TABLE=TRAINING_TABLE,
    TEXT_COLUMNS=TEXT_COLUMNS,
    SCOPE_COLUMN=SCOPE_COLUMN,
    PILLAR_COLUMN=PILLAR_COLUMN,
    EMBEDDINGS_PATH=EMBEDDINGS_PATH,
    SCOPE_MODEL_PATH=SCOPE_MODEL_PATH,
    PILLAR_MODEL_PATH=PILLAR_MODEL_PATH,
    THRESHOLD_PATH=THRESHOLD_PATH,
    SCOPE_MODEL_KWARGS=SCOPE_MODEL_KWARGS,
    PILLAR_MODEL_KWARGS=PILLAR_MODEL_KWARGS,
):
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

    existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()
    if 'publications_embeddings' in existing_tables:
        existing_ids = db.sql("SELECT id FROM publications_embeddings").df()['id']
        n_before = len(data)
        data = data[~data['id'].isin(existing_ids)].reset_index(drop=True)
        print(f"{n_before - len(data)} rows already in 'publications_embeddings', skipped.")
    print(f"{len(data)} rows remaining for embedding.")

    # Build text column from title + abstract
    data['text'] = data[TEXT_COLUMNS[0]].fillna('') + ' [SEP] ' + data[TEXT_COLUMNS[1]].fillna('')

    # --- 2. Load SPECTER2 model ---
    print("\nLoading SPECTER2 model.")
    model, tokenizer = mlf.load_specter()

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

    # --- 4. Append new rows to publications_embeddings ---
    print("\nAppending to 'publications_embeddings' table.")

    EMBEDDINGS_COLUMNS = ['id', 'title', 'abstract', 'year', 'scope', 'pillar', 'research_category', 'truncated', 'embedding']

    data['embedding'] = list(embeddings)
    db.register('df_new', data[EMBEDDINGS_COLUMNS])

    if 'publications_embeddings' in existing_tables:
        db.sql("INSERT INTO publications_embeddings SELECT * FROM df_new")
    else:
        db.sql("CREATE TABLE publications_embeddings AS SELECT * FROM df_new")

    print(f"{len(data)} rows appended to 'publications_embeddings'.")

    # --- 5. Load all data from publications_embeddings for training ---
    print("\nLoading all training data from 'publications_embeddings'.")
    all_data = db.sql("SELECT * FROM publications_embeddings").df()
    print(f"{len(all_data)} rows loaded for training.")

    all_embeddings = np.array(all_data['embedding'].tolist())
    all_data['scope_binary'] = (all_data[SCOPE_COLUMN] == 'in').astype(int)
    print(f"Scope label distribution:\n{all_data['scope_binary'].value_counts().to_string()}")
    print(f"Pillar label distribution:\n{all_data[PILLAR_COLUMN].value_counts().to_string()}")

    # --- 6. Train scope classifier (LR) ---
    print("\nTraining scope classifier.")
    classifier_scope, threshold = mlf.train_scope(
        all_embeddings,
        all_data['scope_binary'].values,
        model_path=SCOPE_MODEL_PATH,
        **SCOPE_MODEL_KWARGS
    )

    with open(THRESHOLD_PATH, 'w') as f:
        f.write(str(threshold))
    print(f"Scope model saved to: {SCOPE_MODEL_PATH}")
    print(f"Threshold saved to: {THRESHOLD_PATH}  (value: {threshold:.3f})")

    # --- 7. Train pillar classifier (LR) ---
    print("\nTraining pillar classifier.")
    mlf.train_pillar(
        all_embeddings,
        all_data[PILLAR_COLUMN].values,
        model_path=PILLAR_MODEL_PATH,
        **PILLAR_MODEL_KWARGS
    )
    print(f"Pillar model saved to: {PILLAR_MODEL_PATH}")

    db.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
