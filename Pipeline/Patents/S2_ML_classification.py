## Classification script: embed new input data and run through trained classifiers
## Can be run standalone (uses CONFIG defaults) or imported and called as main().

import importlib.util, os

# CONFIG
# edit parameters for this run here

# Database
# path to DuckDB database
DB_PATH = 'patents.db'
# table containing the new input data to classify with run date as name
RUN_TABLE = 'data_run_test'
# table for embeddings
EMBEDDINGS_TABLE = 'patents_embeddings'
# table for final classifications
CLASSIFICATION_TABLE = 'patents_classified'

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
    EMBEDDINGS_TABLE=EMBEDDINGS_TABLE,
    TEXT_COLUMNS=TEXT_COLUMNS,
    EMBEDDINGS_PATH=EMBEDDINGS_PATH,
    SCOPE_MODEL_PATH=SCOPE_MODEL_PATH,
    PILLAR_MODEL_PATH=PILLAR_MODEL_PATH,
    THRESHOLD_PATH=THRESHOLD_PATH,
):
    # 1. Load ML_pipeline_functions from the same directory as this script
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _spec = importlib.util.spec_from_file_location(
        'ML_pipeline_patents_functions',
        os.path.join(_script_dir, 'ML_pipeline_patents_functions.py')
    )
    mlf = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(mlf)

    import duckdb
    import numpy as np
    import pandas as pd

    # 2. Load input data
    db = duckdb.connect(database=DB_PATH)
    data = db.sql(f"SELECT * FROM {RUN_TABLE}").df()
    original_columns = list(data.columns)
    print(f"{len(data)} rows loaded from '{RUN_TABLE}'")

    # Prediction columns to be added to RUN_TABLE
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

    # 3. Split into known families (already classified) and new families
    existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()

    if CLASSIFICATION_TABLE in existing_tables:
        known_family_ids = db.sql(
            f"SELECT DISTINCT family_id FROM {CLASSIFICATION_TABLE}"
        ).df()['family_id']
        known_mask = data['family_id'].isin(known_family_ids)
        known_data = data[known_mask].copy()
        new_data = data[~known_mask].reset_index(drop=True)
        print(
            f"{len(known_data)} rows from {known_data['family_id'].nunique()} known families, "
            f"predictions will be added from {CLASSIFICATION_TABLE}.\n"
            f"{len(new_data)} rows from {new_data['family_id'].nunique()} new families, "
            f"will be embedded and classified."
        )
    else:
        known_data = pd.DataFrame()
        new_data = data.copy()
        print(f"No existing classification table. All {len(new_data)} rows treated as new.")

    # 4. Known families: propagate pred_combined and pred_pillar from classification table
    if not known_data.empty:
        print(f"\nPropagating predictions for known families.")

        # pred_combined is stored as 'in'/'out' in CLASSIFICATION_TABLE — convert back to int
        family_preds = db.sql(f"""
            SELECT DISTINCT ON (family_id)
                family_id,
                proba_scope,
                pred_pillar,
                CASE WHEN pred_combined = 'in' THEN 1 ELSE 0 END AS pred_combined
            FROM {CLASSIFICATION_TABLE}
        """).df()

        known_data = known_data.merge(family_preds, on='family_id', how='left')

        db.register('known_update', known_data[['id', 'proba_scope', 'pred_combined', 'pred_pillar']])
        db.sql(f"""
            UPDATE {RUN_TABLE}
            SET proba_scope   = known_update.proba_scope,
                pred_combined = known_update.pred_combined,
                pred_pillar   = known_update.pred_pillar
            FROM known_update
            WHERE {RUN_TABLE}.id = known_update.id
        """)
        print(f"{len(known_data)} rows updated in '{RUN_TABLE}'.")

        # Append new patents from known families to CLASSIFICATION_TABLE
        # (the family is known but these specific patents weren't seen before)
        output_columns = db.sql(f"SELECT * FROM {CLASSIFICATION_TABLE} LIMIT 0").df().columns.tolist()
        known_classified = known_data[output_columns].copy()
        known_classified['pred_combined'] = known_classified['pred_combined'].map({1: 'in', 0: 'out'})
        db.register('known_classified', known_classified)
        db.sql(f"INSERT INTO {CLASSIFICATION_TABLE} SELECT * FROM known_classified")
        print(f"{len(known_classified)} rows from known families appended to {CLASSIFICATION_TABLE}.")

    # 5. New families: select representative per family, embed, classify, propagate
    if not new_data.empty:

        # Select one representative per family for embedding
        def select_patent(group):
            preferred_jurisdictions = ['WO', 'EP', 'US']
            has_content = group[
                group['title'].notna() & group['abstract'].notna() &
                (group['title'] != '') & (group['abstract'] != '')
            ].copy()

            # if no patent with title or abstract exists in the family: choose the newest
            if has_content.empty:
                return group.sort_values('publication_year', ascending=False).head(1)
            
            # in patents with title and abstract, choose the one from the preferred jurisdictions and newest publication date
            has_content['_preferred'] = has_content['jurisdiction'].isin(preferred_jurisdictions)
            has_content = has_content.sort_values(
                ['_preferred', 'publication_year'], ascending=[False, False]
            )
            return has_content.drop_duplicates(subset=['title', 'abstract']).head(1).drop(columns='_preferred')

        reps = new_data.groupby('family_id', group_keys=True).apply(select_patent).reset_index(level=0).reset_index(drop=True)
        print(f"\n{len(reps)} representative patents selected from {new_data['family_id'].nunique()} new families.")

        reps['text'] = reps[TEXT_COLUMNS[0]].fillna('') + ' [SEP] ' + reps[TEXT_COLUMNS[1]].fillna('')

        # Load PatentSBERTa model and check token sizes
        print("\nLoading PatentSBERTa model.")
        model = mlf.load_patentsberta()
        mlf.check_token_size(reps, text_column='text', model=model, add_column=True)

        # Compute embeddings
        print("\nComputing embeddings.")
        embeddings = mlf.get_embeddings(
            reps,
            text_column='text',
            file_path=EMBEDDINGS_PATH,
            model=model,
            checkpoint=True
        )
        print(f"Embeddings shape: {embeddings.shape}")
        reps['embeddings'] = list(embeddings)

        # Save representative embeddings to database
        print(f"\nAppending to {EMBEDDINGS_TABLE} table.")
        data_embeddings = reps[['id', 'embeddings']]
        db.register('data_embeddings', data_embeddings)
        if EMBEDDINGS_TABLE in existing_tables:
            db.sql(f"INSERT INTO {EMBEDDINGS_TABLE} SELECT * FROM data_embeddings")
        else:
            db.sql(f"CREATE TABLE {EMBEDDINGS_TABLE} AS SELECT * FROM data_embeddings")

        # Run scope classifier
        print("\nRunning scope classifier.")
        with open(THRESHOLD_PATH, 'r') as f:
            threshold = float(f.read().strip())
        print(f"Scope threshold: {threshold:.3f}")

        proba_scope, pred_scope = mlf.scope_classification(embeddings, SCOPE_MODEL_PATH, threshold=threshold)
        reps['proba_scope']     = proba_scope
        reps['pred_scope']      = pred_scope
        reps['threshold_scope'] = threshold

        # Run pillar classifier
        print("Running pillar classifier.")
        proba_pillar, pred_pillar = mlf.pillar_classification(embeddings, PILLAR_MODEL_PATH)
        reps['proba_pillar'] = proba_pillar
        reps['pred_pillar']  = pred_pillar

        # Combine predictions
        reps['pred_combined'] = mlf.combine_classifications(pred_scope, pred_pillar)
        in_scope_n = reps['pred_combined'].sum()
        print(f"Predicted in scope: {in_scope_n} / {len(reps)} ({in_scope_n / len(reps):.1%})")

        # Propagate predictions from representative to all members of the same family
        pred_cols = [c for c in new_columns if c in reps.columns]
        new_data = new_data.merge(reps[['family_id'] + pred_cols], on='family_id', how='left')

        # Update RUN_TABLE for new families
        print(f"\nUpdating '{RUN_TABLE}' with predictions for new families.")
        available_cols = [c for c in new_columns if c in new_data.columns]
        db.register('new_update', new_data[['id'] + available_cols])
        set_clause = ", ".join(f"{c} = new_update.{c}" for c in available_cols)
        db.sql(f"""
            UPDATE {RUN_TABLE}
            SET {set_clause}
            FROM new_update
            WHERE {RUN_TABLE}.id = new_update.id
        """)

        # Append new families to CLASSIFICATION_TABLE
        print(f"\nAppending to {CLASSIFICATION_TABLE} table.")
        existing_tables_now = db.sql("SHOW TABLES").df()['name'].tolist()
        if CLASSIFICATION_TABLE in existing_tables_now:
            output_columns = db.sql(f"SELECT * FROM {CLASSIFICATION_TABLE} LIMIT 0").df().columns.tolist()
        else:
            output_columns = original_columns + ['proba_scope', 'pred_combined', 'pred_pillar']

        data_classified = new_data[output_columns].copy()
        data_classified['pred_combined'] = data_classified['pred_combined'].map({1: 'in', 0: 'out'})
        db.register('data_classified', data_classified)

        if CLASSIFICATION_TABLE in existing_tables_now:
            db.sql(f"INSERT INTO {CLASSIFICATION_TABLE} SELECT * FROM data_classified")
        else:
            db.sql(f"CREATE TABLE {CLASSIFICATION_TABLE} AS SELECT * FROM data_classified")

        print(f"{len(data_classified)} rows appended to {CLASSIFICATION_TABLE}.")

    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
