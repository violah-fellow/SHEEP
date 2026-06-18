import duckdb
con = duckdb.connect('publications.db', read_only=True)
r = con.sql("SELECT scope, pillar, COUNT(*) as n FROM publications_raw WHERE scope='in' GROUP BY scope, pillar ORDER BY pillar").df()
print(r)
con.close()
