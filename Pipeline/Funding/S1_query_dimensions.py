## Query script: query Dimensions for grants and store queried data in database
## All parameters that need to be changed are defined in the CONFIG section below.

import os

# CONFIG
# edit parameters for this run here

# Dimensions API
# path to API key
KEY_PATH = '../../.env'

# Database
# path to DuckDB database (kept in place in SHEEP/Funding/ - not duplicated here)
DB_PATH = '../../Funding/funding.db'
# table to store the new run data
RUN_TABLE = 'data_run_test'
# table for final classifications
CLASSIFICATION_TABLE = 'funding_classified'

# Queries
# path to txt file with search strings
STRINGS_FILE = 'dimensions_search_funding.txt'
# Other parameters for search
YEAR = 2025
# ...

# START OF SCRIPT

def main(
    KEY_PATH=KEY_PATH,
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    CLASSIFICATION_TABLE=CLASSIFICATION_TABLE,
    STRINGS_FILE=STRINGS_FILE,
    YEAR=YEAR,
):
    # import packages
    from dotenv import load_dotenv
    from datetime import datetime
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

        # only pull 100 grants per search term for testing
        # note: grants are filtered on start_year (not year, as for publications/patents)
        query.append(dsl.query(f"""search grants in title_abstract_only for "{dsl_escape(query_string)}"
                            where start_year={YEAR}
                            return grants[id+title+original_title+abstract+start_date+start_year+end_date+
                            funder_orgs+funder_org_name+funder_org_countries+funder_org_cities+
                            funding_usd+funding_eur+funding_gbp+funding_currency+funding_schemes+
                            research_orgs+research_org_names+research_org_countries+research_org_cities+
                            researchers+investigators+keywords+linkout+dimensions_url+
                            category_for_2020+category_sdg]
                            limit 10"""))

        # query.append(dsl.query_iterative(f"""search grants in title_abstract_only for "{dsl_escape(query_string)}"
        #                     where start_year={YEAR}
        #                     return grants[id+title+original_title+abstract+start_date+start_year+end_date+
        #                     funder_orgs+funder_org_name+funder_org_countries+funder_org_cities+
        #                     funding_usd+funding_eur+funding_gbp+funding_currency+funding_schemes+
        #                     research_orgs+research_org_names+research_org_countries+research_org_cities+
        #                     researchers+investigators+keywords+linkout+dimensions_url+
        #                     category_for_2020+category_sdg]"""))

    # Convert to pandas dataframe and deduplicate by id
    query_df = pd.concat([q.as_dataframe() for q in query], ignore_index=True)
    print(f"\n{len(query_df)} grants retrieved from dimensions.")

    query_df = query_df.drop_duplicates(subset="id").reset_index(drop=True)
    query_df['date_dimensions'] = datetime.today().strftime('%y%m%d')

    print(f"\n{len(query_df)} grants remain after deduplication.")

    # Filter grants that already are in the final database
    # Connect to SQL database
    db = duckdb.connect(database=DB_PATH)

    existing_tables = db.sql("SHOW TABLES").df()['name'].tolist()
    if CLASSIFICATION_TABLE in existing_tables:
        existing_ids = db.sql(f"SELECT id FROM {CLASSIFICATION_TABLE}").df()['id']
        n_before = len(query_df)
        query_df = query_df[~query_df['id'].isin(existing_ids)].reset_index(drop=True)
        print(f"{n_before - len(query_df)} rows already in {CLASSIFICATION_TABLE}.")

    # Reorder columns to match funding_classified if it exists
    # excludes columns computed later in the pipeline (S3_LLM_scope.py)
    if CLASSIFICATION_TABLE in existing_tables:
        expected_cols = [c for c in db.sql(f"SELECT * FROM {CLASSIFICATION_TABLE} LIMIT 0").df().columns.tolist()
                         if c not in ('scope_LLM', 'confidence_LLM', 'pillar_LLM',
                                      'plant_based_LLM', 'fermentation_LLM', 'cultivated_LLM', 'cross_cutting_LLM',
                                      'status_LLM', 'stop_reason_LLM', 'date_LLM')]
        query_df = query_df.reindex(columns=expected_cols)

    # 4. Add the queries to the database
    # Create run table and add queries
    print(f"\nStoring grants in database as {RUN_TABLE}")

    db.sql(f"CREATE OR REPLACE TABLE {RUN_TABLE} AS SELECT * FROM query_df")
    print(f"{len(query_df)} rows appended to {RUN_TABLE}.")

    # Close connection
    db.close()

    print("Done!")


if __name__ == '__main__':
    main()
