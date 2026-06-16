## Query script: query dimensions and store queried data in database
## All parameters that need to be changed are defined in the CONFIG section below.

import os

# CONFIG 
# edit parameters for this run here

# Database
# path to DuckDB database
DB_PATH = 'ML/publications.db'
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
    from dimcli.utils import *
    import pandas as pd
    import seaborn as sns
    import duckdb

    # Login to the Dimensions API
    # this login requires a dsl.ini file stored on the computer
    dimcli.login()

    dsl = dimcli.Dsl()

    # Load search strings
    # here: read strings file
    # to test: 
    search_strings = [""" "\"meat substitute\" OR "\"meat analogue\" """, """ "\"vegan meat\" OR "\"meat alternative\" """]

    # Query dimensions
    query = []
    for i in search_strings:
        query.append(dsl.query(f"""search publications for "{dsl_escape(i)}"
                            where year={YEAR} 
                            return publications[id+title+abstract+year+type]
                            limit 100"""))

    # Convert to pandas dataframe and deduplicate by id    
    query_df = pd.concat([q.as_dataframe() for q in query], ignore_index=True)
    query_df = query_df.drop_duplicates(subset="id").reset_index(drop=True)

    # Connect to SQL database
    db = duckdb.connect(database=DB_PATH)

    # Create run table and add queries
    db.sql(f"CREATE OR REPLACE TABLE {RUN_TABLE} AS SELECT * FROM query_df")

    # Close connection 
    db.close()


if __name__ == '__main__':
    main()
