## Query script: query dimensions and store queried data in database
## All parameters that need to be changed are defined in the CONFIG section below.

import os

# CONFIG 
# edit parameters for this run here

# Database
# path to DuckDB database
DB_PATH = 'publications.db'
# table to store the new run data
RUN_TABLE = 'data_run_test'

# Queries
# path to txt file with search strings
STRINGS_FILE = 'dimensions_search_publications.txt'
# Other parameters for search
YEAR = 2025
# ...

# START OF SCRIPT

def main(
    DB_PATH=DB_PATH,
    RUN_TABLE=RUN_TABLE,
    STRINGS_FILE=STRINGS_FILE,
    YEAR=YEAR,
):
    # import packages
    import dimcli
    from dimcli.utils import dsl_escape
    import pandas as pd
    import seaborn as sns
    import duckdb

    # 1. Load Dimensions API and search strings
    # Login to dimensions API requires a dsl.ini file stored on the computer
    print("\nConnecting to the Dimensions API")
    
    dimcli.login()
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
                            return publications[id+title+abstract+year+type]
                            limit 100"""))
        
        # query.append(dsl.query_iterative(f"""search publications for "{dsl_escape(query_string)}"
        #                     where year={YEAR} 
        #                     return publications[id+title+abstract+year+type]"""))

    # Convert to pandas dataframe and deduplicate by id    
    query_df = pd.concat([q.as_dataframe() for q in query], ignore_index=True)
    query_df = query_df.drop_duplicates(subset="id").reset_index(drop=True)

    # 3. Add the queries to the database
    # Connect to SQL database
    db = duckdb.connect(database=DB_PATH)

    # Create run table and add queries
    print(f"\nStoring publications in database as {RUN_TABLE}")

    db.sql(f"CREATE OR REPLACE TABLE {RUN_TABLE} AS SELECT * FROM query_df")

    # Close connection 
    db.close()

    print("Done!")


if __name__ == '__main__':
    main()
