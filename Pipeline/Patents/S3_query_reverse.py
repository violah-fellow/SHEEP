## Query script: query dimensions and store queried data in database
## All parameters that need to be changed are defined in the CONFIG section below.

import os

# CONFIG 
# edit parameters for this run here

# Dimensions API
# path to API key
KEY_PATH = '../.env'

# Database
# path to DuckDB database
DB_PATH = 'patents.db'
# table where run queries were stored
RUN_TABLE = 'data_run_test'
REVERSE_TABLE = RUN_TABLE + '_reverse'
# table for final classifications
CLASSIFICATION_TABLE = 'patents_classified'

# Queries
# Other parameters for search
YEAR = 2025
# ...

# START OF SCRIPT

def main(
    KEY_PATH,
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    REVERSE_TABLE=REVERSE_TABLE,
    CLASSIFICATION_TABLE=CLASSIFICATION_TABLE,
    YEAR=YEAR,
):
    # import packages
    from dotenv import load_dotenv
    import dimcli
    from dimcli.utils import dsl_escape
    import pandas as pd
    import duckdb
    import json

    # 1. Load Dimensions API and search strings
    # Login to dimensions API requires a dsl.ini file stored on the computer
    print("\nConnecting to the Dimensions API")
    
    load_dotenv(KEY_PATH) 
    dimcli.login(key=os.getenv("DIMENSIONS_API_KEY"))
    dsl = dimcli.Dsl()

    # 2. Extract family ID's
    # Connect to SQL database
    db = duckdb.connect(database=DB_PATH)

    # Retrieve run table and convert to pandas dataframe
    run_data = db.sql(f"SELECT * FROM {RUN_TABLE}").df()

    # Filter for in scope patents and retrieve family ID's
    run_data = run_data[run_data['pred_combined'] == 1] 
    family_ids = run_data['family_id'].tolist()

    # Function to batch family ID's    
    def chunks(list, n):
        for i in range(0, len(list), n):
            yield list[i:i + n]

    # 3. Query dimensions with family ID's
    print("\nStart reverse query")

    # only pull 100 publications per search term for testing
    query = []
    for batch in chunks(family_ids, 500):
        ids_batch = json.dumps(batch)  
        q = dsl.query(f"""search patents
          where family_id in {json.dumps(ids_batch)}
          return patents[id+family_id+application_number+title+abstract+cpc+jurisdiction+year+priority_year+
                        publication_year+granted_year+filing_status+legal_status+inventor_names+original_assignee_names+current_assignee_names+
                        assignee_names+assignee_cities+assignee_countries+associated_grant_ids+funders+funder_countries+federal_support+
                        publications+researchers+times_cited+family_count]
          limit 100 """)
        query.append(q)

    # full query
    # query = []
    # for batch in chunks(family_ids, 500):
    #     ids_batch = json.dumps(batch)  
    #     q = dsl.query_iterative(f"""search patents
    #       where family_id in {json.dumps(ids_batch)}
    #       return patents[id+family_id+application_number+title+abstract+cpc+jurisdiction+year+priority_year+
    #                      publication_year+granted_year+filing_status+legal_status+inventor_names+original_assignee_names+current_assignee_names+
    #                      assignee_names+assignee_cities+assignee_countries+associated_grant_ids+funders+funder_countries+federal_support+
    #                      publications+researchers+times_cited+family_count]
    #       """)
    #     query.append(q)

    # Convert to pandas dataframe and deduplicate by id    
    query_df = pd.concat([q.as_dataframe() for q in query], ignore_index=True)
    query_df = query_df.drop_duplicates(subset="id").reset_index(drop=True)

    # Filter publications that already are in the final database
    # Connect to SQL database
    db = duckdb.connect(database=DB_PATH)

    existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()
    if CLASSIFICATION_TABLE in existing_tables:
        existing_ids = db.sql(f"SELECT id FROM {CLASSIFICATION_TABLE}").df()['id']
        n_before = len(query_df)
        query_df = query_df[~query_df['id'].isin(existing_ids)].reset_index(drop=True)
        print(f"{n_before - len(query_df)} rows already in {CLASSIFICATION_TABLE}.")

    # Reorder columns to match patents_classified
    expected_cols = [c for c in db.sql(f"SELECT * FROM {CLASSIFICATION_TABLE} LIMIT 0").df().columns.tolist()
                     if c not in ('pred_combined', 'pred_pillar')]
    query_df = query_df.reindex(columns=expected_cols)

    # 4. Add the queries to the database
    # Create reverse run table and add queries
    print(f"\nStoring publications in database as {REVERSE_TABLE}")

    db.sql(f"CREATE OR REPLACE TABLE {REVERSE_TABLE} AS SELECT * FROM query_df")
    print(f"{len(query_df)} rows appended to {REVERSE_TABLE}.")

    # 5. Add scope and pillar information from patents of the same family
    print(f"\nUpdating '{REVERSE_TABLE}' in database with prediction columns.")

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
        db.sql(f"ALTER TABLE {REVERSE_TABLE} ADD COLUMN IF NOT EXISTS {col} {dtype}")

    # make sure there is only one patent per family ID
    run_data = run_data.drop_duplicates(subset="family_id").reset_index(drop=True)

    db.register('data', run_data[['family_id'] + list(new_columns.keys())])
    db.sql(f"""
        UPDATE {REVERSE_TABLE}
        SET proba_scope     = data.proba_scope,
            pred_scope      = data.pred_scope,
            threshold_scope = data.threshold_scope,
            proba_pillar    = data.proba_pillar,
            pred_pillar     = data.pred_pillar,
            pred_combined   = data.pred_combined,
            embeddings      = data.embeddings
        FROM data
        WHERE {REVERSE_TABLE}.family_id = data.family_id
    """)

    # 6. Append to patents_classified
    print(f"\nAppending to {CLASSIFICATION_TABLE} table.")

    # get output columns for CLASSIFICATION_TABLE
    output_columns = db.sql(f"SELECT * FROM {CLASSIFICATION_TABLE} LIMIT 0").df().columns.tolist()
    
    # get data with predictions from reverse_table
    data = db.sql(f"SELECT * FROM {REVERSE_TABLE}").df()

    # convert prediction in / out and add to CLASSIFICATION_TABLE
    data_classified = data[output_columns].copy()
    data_classified['pred_combined'] = data_classified['pred_combined'].map({1: 'in', 0: 'out'})
    db.register('data_classified', data_classified)

    db.sql(f"INSERT INTO {CLASSIFICATION_TABLE} SELECT * FROM data_classified")
    
    print(f"{len(data_classified)} rows appended to {CLASSIFICATION_TABLE}.")

    # Close connection 
    db.close()

    print("Done!")


if __name__ == '__main__':
    main()
