## Classification script: embed new input data and run through trained classifiers
## Can be run standalone (uses CONFIG defaults) or imported and called as main().

import importlib.util, os

# CONFIG 
# edit parameters for this run here

# Database
# path to DuckDB database
DB_PATH = 'publications.db'
# table containing the new input data to classify with run date as name
RUN_TABLE = 'data_run_test'
# table for embeddings
EMBEDDINGS_TABLE = 'publications_embedding'
# table for final classifications
CLASSIFICATION_TABLE = 'publications_classified'

# Columns
# columns concatenated for embedding (title, abstract)
TEXT_COLUMNS = ('title', 'abstract')

# Embeddings
# save path for embeddings (checkpoint + final)
EMBEDDINGS_PATH = 'embeddings_run_test.npy'

# Model paths
SCOPE_MODEL_PATH  = 'Models/LR_scope.joblib'
PILLAR_MODEL_PATH = 'Models/LR_pillar.joblib'
THRESHOLD_PATH    = 'Models/LR_scope_threshold.txt'

# START OF SCRIPT

def main(
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    TEXT_COLUMNS=TEXT_COLUMNS,
    EMBEDDINGS_PATH=EMBEDDINGS_PATH,
    SCOPE_MODEL_PATH=SCOPE_MODEL_PATH,
    PILLAR_MODEL_PATH=PILLAR_MODEL_PATH,
    THRESHOLD_PATH=THRESHOLD_PATH,
):
    # 1. Load ML_pipeline_functions from the same directory as this script
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _spec = importlib.util.spec_from_file_location(
        'ML_pipeline_publications_functions',
        os.path.join(_script_dir, 'ML_pipeline_publications_functions.py')
    )
    mlf = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(mlf)

    import duckdb
    import numpy as np

    # 2. Load input data
    db = duckdb.connect(database=DB_PATH)
    data = db.sql(f"SELECT * FROM {RUN_TABLE}").df()

    # store original columns for saving the table later
    original_columns = list(data.columns)
    print(f"{len(data)} rows loaded from '{RUN_TABLE}'")

    # remove entries with existing embedding
    existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()
    if EMBEDDINGS_TABLE in existing_tables:
        existing_ids = db.sql(f"SELECT id FROM {EMBEDDINGS_TABLE}").df()['id']
        n_before = len(data)
        data = data[~data['id'].isin(existing_ids)].reset_index(drop=True)
        print(f"{n_before - len(data)} rows already in {EMBEDDINGS_TABLE}, skipped.")
    
    print(f"{len(data)} rows remaining for embedding.")

    # Build text column from title + abstract
    data['text'] = data[TEXT_COLUMNS[0]].fillna('') + ' [SEP] ' + data[TEXT_COLUMNS[1]].fillna('')

    # Load SPECTER2 model and check token sizes
    print("\nLoading SPECTER2 model.")

    model, tokenizer = mlf.load_specter()
    mlf.check_token_size(data, text_column='text', tokenizer=tokenizer, add_column=True)

    # 3. Compute embeddings
    print("\nComputing embeddings.")

    embeddings = mlf.get_embeddings(
        data,
        text_column='text',
        file_path=EMBEDDINGS_PATH,
        model=model,
        tokenizer=tokenizer,
        checkpoint=True
    )
    print(f"Embeddings shape: {embeddings.shape}")

    data['embeddings'] = list(embeddings)

    # Save embeddings to database
    print(f"\nAppending to {EMBEDDINGS_TABLE} table.")

    data_embeddings = data[['id', 'embeddings']]
    db.register('data_embeddings', data_embeddings)

    existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()
    if EMBEDDINGS_TABLE in existing_tables:
        db.sql(f"INSERT INTO {EMBEDDINGS_TABLE} SELECT * FROM data_embeddings")
    else:
        db.sql(f"CREATE TABLE {EMBEDDINGS_TABLE} AS SELECT * FROM data_embeddings")

    # 4. Run scope classifier
    print("\nRunning scope classifier.")

    with open(THRESHOLD_PATH, 'r') as f:
        threshold = float(f.read().strip())
    print(f"Scope threshold: {threshold:.3f}")

    proba_scope, pred_scope = mlf.scope_classification(embeddings, SCOPE_MODEL_PATH, threshold=threshold)

    data['proba_scope']     = proba_scope
    data['pred_scope']      = pred_scope
    data['threshold_scope'] = threshold

    # 5. Run pillar classifier
    print("Running pillar classifier.")

    proba_pillar, pred_pillar = mlf.pillar_classification(embeddings, PILLAR_MODEL_PATH)

    data['proba_pillar'] = proba_pillar
    data['pred_pillar']  = pred_pillar

    # 6. Combine predictions
    data['pred_combined'] = mlf.combine_classifications(pred_scope, pred_pillar)

    in_scope_n = data['pred_combined'].sum()

    print(f"Predicted in scope: {in_scope_n} / {len(data)} ({in_scope_n / len(data):.1%})")

    # 7. Update RUN_TABLE in database with new prediction columns
    print(f"\nUpdating '{RUN_TABLE}' in database with prediction columns.")

    new_columns = {
        'embeddings':      'DOUBLE[]',
        'truncated':       'BOOLEAN',
        'proba_scope':     'DOUBLE',
        'pred_scope':      'INTEGER',
        'threshold_scope': 'DOUBLE',
        'proba_pillar':    'DOUBLE',
        'pred_pillar':     'VARCHAR',
        'pred_combined':   'INTEGER',
    }
    for col, dtype in new_columns.items():
        db.sql(f"ALTER TABLE {RUN_TABLE} ADD COLUMN IF NOT EXISTS {col} {dtype}")

    db.register('data', data[['id'] + list(new_columns.keys())])
    db.sql(f"""
        UPDATE {RUN_TABLE}
        SET proba_scope     = data.proba_scope,
            pred_scope      = data.pred_scope,
            threshold_scope = data.threshold_scope,
            proba_pillar    = data.proba_pillar,
            pred_pillar     = data.pred_pillar,
            pred_combined   = data.pred_combined,
            embeddings      = data.embeddings
        FROM data
        WHERE {RUN_TABLE}.id = data.id
    """)

    # 8. Append to publications_classified
    print(f"\nAppending to {CLASSIFICATION_TABLE} table.")

    # get output columns for CLASSIFICATION_TABLE
    existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()
    if CLASSIFICATION_TABLE in existing_tables:
        output_columns = db.sql(f"SELECT * FROM {CLASSIFICATION_TABLE} LIMIT 0").df().columns.tolist()
    else:
        output_columns = original_columns + ['pred_combined', 'pred_pillar']

    # convert prediction in / out and add to CLASSIFICATION_TABLE
    data_classified = data[output_columns].copy()
    data_classified['pred_combined'] = data_classified['pred_combined'].map({1: 'in', 0: 'out'})
    db.register('data_classified', data_classified)

    if CLASSIFICATION_TABLE in existing_tables:
        db.sql(f"INSERT INTO {CLASSIFICATION_TABLE} SELECT * FROM data_classified")
    else:
        db.sql(f"CREATE TABLE {CLASSIFICATION_TABLE} AS SELECT * FROM data_classified")

    print(f"{len(data_classified)} rows appended to {CLASSIFICATION_TABLE}.")

    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
