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
DB_PATH = 'publications.db'
# table to store the new run data
RUN_TABLE = 'data_run_test'
# table for final classifications
CLASSIFICATION_TABLE = 'publications_classified'

# Queries
# path to txt file with search strings
STRINGS_FILE = 'dimensions_search_publications.txt'
# Other parameters for search
YEAR = 2025
# ...

# START OF SCRIPT

def main(
    KEY_PATH=KEY_PATH,    
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    STRINGS_FILE=STRINGS_FILE,
    YEAR=YEAR,
):
    # import packages
    from dotenv import load_dotenv
    import dimcli
    from dimcli.utils import dsl_escape
    import pandas as pd
    import duckdb

    # 1. Load Dimensions API and search strings
    # Login to dimensions API requires a dsl.ini file stored on the computer
    print("\nConnecting to the Dimensions API")
    
    load_dotenv(KEY_PATH) 
    dimcli.login(key=os.getenv("DIMENSIONS_API_KEY"))
    dsl = dimcli.Dsl()

    # Load search strings by reading the txt file
    with open(STRINGS_FILE, 'r') as f:
        search_strings = [line.strip() for line in f if line.strip()]

    # 2. Query dimensions
    print("\nStart query")

    query = []
    for i in search_strings:
        query_string = i.replace('\\"', '\"')
        
        # only pull 100 publications per search term for testing
        query.append(dsl.query(f"""search publications for "{dsl_escape(query_string)}"
                            where year={YEAR} 
                            return publications[id+title+abstract+year+type+authors+concepts_relevant+date+funders+
                            funder_countries+journal+open_access+research_org_names+research_org_countries+research_org_cities+times_cited]
                            limit 10"""))
        
        # query.append(dsl.query_iterative(f"""search publications for "{dsl_escape(query_string)}"
        #                     where year={YEAR} 
        #                     return publications[id+title+abstract+year+type+authors+concepts_relevant+date+funders+
        #                     funder_countries+journal+open_access+research_org_names+research_org_countries+research_org_cities+times_cited]"""))

    # Convert to pandas dataframe and deduplicate by id    
    query_df = pd.concat([q.as_dataframe() for q in query], ignore_index=True)
    query_df = query_df.drop_duplicates(subset="id").reset_index(drop=True)

    # 3. Filter articles
    # Filter for articles
    query_df = query_df[query_df['type'] == 'article']

    # Filter publications that already are in the final database
    # Connect to SQL database
    db = duckdb.connect(database=DB_PATH)

    existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()
    if CLASSIFICATION_TABLE in existing_tables:
        existing_ids = db.sql(f"SELECT id FROM {CLASSIFICATION_TABLE}").df()['id']
        n_before = len(query_df)
        query_df = query_df[~query_df['id'].isin(existing_ids)].reset_index(drop=True)
        print(f"{n_before - len(query_df)} rows already in {CLASSIFICATION_TABLE}.")

    # Reorder columns to match publications_classified if it exists
    if CLASSIFICATION_TABLE in existing_tables:
        expected_cols = [c for c in db.sql(f"SELECT * FROM {CLASSIFICATION_TABLE} LIMIT 0").df().columns.tolist()
                         if c not in ('pred_combined', 'pred_pillar')]
        query_df = query_df.reindex(columns=expected_cols)

    # 4. Add the queries to the database
    # Create run table and add queries
    print(f"\nStoring publications in database as {RUN_TABLE}")

    db.sql(f"CREATE OR REPLACE TABLE {RUN_TABLE} AS SELECT * FROM query_df")
    print(f"{len(query_df)} rows appended to {RUN_TABLE}.")

    # Close connection 
    db.close()

    print("Done!")


if __name__ == '__main__':
    main()
