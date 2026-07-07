"""
Relabel Cross-cutting → Agnostic for patents with no specific end product context.

These 206 records are currently labelled "Cross-cutting" in the training data but
describe general ingredients, processing equipment, extraction methods, or biomass
characterisation with no named end product type — matching the "Agnostic" definition.

Run with:  conda activate sheep && python relabel_crosscutting_to_agnostic.py
"""

import pandas as pd
import duckdb
from pathlib import Path

# ---------------------------------------------------------------------------
# IDs to reclassify from Cross-cutting → Agnostic
# ---------------------------------------------------------------------------

AGNOSTIC_IDS = [
    # Fermentation pillar — no food product context
    "US-12612592-B2", "US-20210340490-A1",       # algae biomass protein enrichment
    "US-12600940-B2", "US-20260062667-A1",        # Xanthobacter SCP/biomass
    "US-20230148627-A1", "EP-4114195-A1",         # microbial biomass pasteurisation
    "US-20250027033-A1", "GB-2595643-A",          # modified Chlorella vulgaris strains
    "EP-4522722-A1", "JP-2025520704-A",           # fungal medium from BSG
    "EP-4583714-A1", "JP-2025528558-A",           # fungal biomass granulate
    "EP-4615241-A1", "EP-4368027-A1",             # Crabtree-neg yeast; generic "food product"
    "DE-102022201682-B4", "DE-102022201682-A1",   # food from fermented by-products
    "EP-4754234-A1", "GB-2619425-A",              # Metschnikowia strain; lipid/alcohol/biomass
    "WO-2025056598-A1", "EP-4523544-A1",          # mycelium fermentation; generic edible composite
    "US-20250351856-A1", "JP-2025534794-A",       # fungal ingredients; vague "derived products"
    "EP-4608161-A1", "JP-2026513110-A",           # high-protein yeast; generic edible products
    "WO-2025088342-A1", "GB-2634922-A",           # SSF protein production; generic human food
    "WO-2025083422-A1",                           # co-culture methanotroph+methylotroph SCP
    "EP-4626251-A1", "FI-131623-B1",              # Trichocomaceae fungal biomass
    "WO-2025119806-A1",                           # recombinant patatin-2; vague product
    "US-20250338869-A1", "JP-2025517300-A",       # microbial functional proteins (reduced lipid)
    "US-20250197795-A1", "CN-120112181-A",        # microbial cell extract; vague uses
    "EP-4658754-A1",                              # algae biomass (defined colour)
    "EP-4658753-A1",                              # chlorophyll-deficient Chlorella
    "EP-4754772-A1", "KR-20260054052-A",          # prediction methods for fungal culture
    "WO-2025181163-A1", "NL-2037130-B1",          # microbial lipid; "use thereof"
    "EP-4661689-A1", "JP-2026509602-A",           # algal protein microparticles; "various applications"
    "EP-4649832-A1",                              # yeast SCP; human and animal nutrition
    "WO-2025061675-A1", "DE-102023125142-A1",     # cascade fermentation system
    "WO-2025229117-A1",                           # Yarrowia lipolytica for lipid production
    "WO-2025238246-A1",                           # microorganism protein isolate (yeast)
    "WO-2025242924-A1", "FR-3162341-A1",          # GABA-rich yeast extract; taste masking

    # Plant-based pillar — no food product context
    "US-20210244046-A1", "CN-112334010-B",        # non-vital wheat protein; functional characterisation
    "US-20210120857-A1", "JP-2024073533-A",       # peptidylarginine deiminase; generic "protein food"
    "US-20220192220-A1", "EP-3962288-A1",         # gelling leguminous plant protein
    "US-20220312794-A1", "EP-3989738-A1",         # method for producing leguminous proteins
    "US-12161144-B2", "US-20220007693-A1",        # process for preparation of cereal fractions
    "US-12342837-B2", "US-20220046950-A1",        # composition of textured leguminous proteins
    "US-20230106315-A1", "EP-4110079-A1",         # same family (textured leguminous proteins)
    "US-20220304331-A1", "AU-2020249498-B2",      # field bean protein composition
    "US-20220330571-A1", "AU-2020247127-B2",      # field bean protein (low-solubility variant)
    "EP-3520624-A1", "FI-128029-B",               # process for producing a plant protein ingredient
    "US-20220022490-A1", "EP-3893658-A1",         # low sodium protein isolate
    "US-12383881-B2", "US-20240216885-A1",        # coacervate core-shell microcapsules
    "US-20250000121-A1", "EP-4404766-A1",         # method for reducing bitterness of leguminous protein
    "EP-4604909-A1", "CN-120091807-A",            # lipid-based microcapsules; generic "flavoured consumer products"
    "EP-4615251-A1", "JP-2025539239-A",           # reduction of vicine/convicine in faba ingredients
    "US-20250127199-A1", "EP-4384027-A1",         # nutrient + taste modulator composition; generic
    "EP-4637390-A1", "CN-120475910-A",            # method and system for drying proteins
    "US-20250101233-A1",                          # stable natural colourant; generic food products
    "US-20250346640-A1", "EP-4444104-A1",         # water-soluble legume protein; ingredient only
    "US-20250107557-A1", "EP-4482327-A1",         # process for soybean flour with high solubility
    "EP-4651961-A2", "JP-2026503093-A",           # solid extraction process; generic fractionation
    "US-20250215412-A1", "EP-4490286-A1",         # fusion polypeptides with deamidase activity
    "US-20250134133-A1", "JP-2025504547-A",       # process for sunflower protein concentrate
    "US-20260083155-A1", "EP-4565077-A1",         # textured plant proteins; "use thereof"
    "EP-4612273-A2", "CN-120457196-A",            # plant protein isolate via microbial strain
    "EP-4701434-A1", "CN-121001578-A",            # bitter-masking of kaempferol; generic
    "EP-4518685-A1",                              # method of inhibiting Clostridium; no product context
    "EP-4626248-A1", "CN-120379545-A",            # wet-textured plant proteins; no product
    "EP-4742918-A1",                              # rapeseed protein hydrolysate; characterisation only
    "US-20260013527-A1", "EP-4525631-A1",         # low-lipid pea protein isolate; "uses thereof"
    "EP-4642241-A1", "CN-120826163-A",            # plant protein improved by whole-cell biomass
    "WO-2025056701-A1", "CN-121666449-A",         # stabilized deamidase compositions; enzyme
    "EP-4698139-A1", "JP-2026514896-A",           # stable emulsion by magnetic turbulence; no product
    "FR-3150933-A1",                              # functional fava bean protein; no specific product
    "US-20260123657-A1", "EP-4604742-A1",         # masking off-notes in consumables; generic
    "EP-4727364-A1", "CN-121772846-A",            # textured wheat proteins; "use thereof"
    "EP-4604740-A1", "CN-120076720-A",            # improving flavor in plant-based food; generic
    "US-20250338871-A1",                          # leguminous protein with acid-gelling; no product
    "US-20260103493-A1", "EP-4593625-A2",         # functional native potato protein; no product
    "WO-2025119976-A3", "EP-4567121-A1",          # combined bioethanol + oilseed protein; ingredient only
    "WO-2025073721-A1", "MX-2026003938-A",        # method for separating cereal material into fractions
    "US-20260096575-A1", "EP-4593623-A1",         # enzymatic method of producing plant protein extract
    "EP-4650443-A1",                              # stabilized liquid deamidase compositions
    "WO-2025239775-A1",                           # protein structuring module for generic "food product"
    "EP-4626242-A1", "CN-120659543-A",            # additive composition for generic "consumable"
    "EP-4680046-A1", "JP-2026507944-A",           # nutritional compositions; generic "plant protein products"
    "WO-2025093711-A1", "FR-3154573-A1",          # umami food ingredient from hemp; ingredient only
    "WO-2025154002-A1",                           # oleogel; "ingredient in a food preparation"
    "EP-4638703-A1", "FR-3144161-B1",             # novel Carnobacterium strain; generic food product
    "EP-4727369-A1", "CN-121843595-A",            # temperature-gelling pea proteins; no product
    "EP-4669132-A1",                              # ingredient composition in dry form; no product
    "WO-2025124742-A1", "FR-3156639-A1",          # wet legume protein concentrate; no product
    "WO-2025127935-A1",                           # coagulated tuber protein product; processing only
    "US-20250009003-A1",                          # plant-based hydrogels; generic "layered foods"
    "WO-2025140303-A1",                           # enzymatic treatment of corn protein; no product
    "WO-2025132803-A1",                           # 3-hydroxybenzoic acid; generic ingestible composition
    "WO-2025068049-A1",                           # reducing phytic acid; generic "plant-based consumables"
    "WO-2025073683-A1", "CN-122028804-A",         # flavanone flavor modifiers; generic ingestible
    "WO-2025172534-A1",                           # dearomatizing and debittering legumes; no product
    "WO-2025191050-A1",                           # lipid particles; generic "ingestible compositions"
    "WO-2025215260-A1",                           # pulse seed processing; no product context
    "US-20250359573-A1",                          # processing of starch-protein pulses; no product
    "WO-2025158084-A1",                           # pulse seed processing; no product context
    "WO-2025120178-A1",                           # Streptococcus thermophilus in soy; generic "fermented food"
    "WO-2025252271-A1",                           # food binder for non-animal foods; generic
    "EP-4723901-A1", "CN-121816119-A",            # functional fava bean protein; no specific product
    "WO-2026027746-A1", "FR-3165152-A3",          # pea lines with improved taste; "ingredients" only
    "WO-2026027749-A1", "FR-3165153-A3",          # pea lines (variant); "plant-based ingredient"
    "EP-4754112-A1", "AR-133439-A1",              # reducing off-flavours; "various alternative consumable applications"
    "WO-2025264773-A1",                           # functional extraction of soy protein; no product
    "PL-248004-B1", "PL-444467-A1",               # fermented protein extract from milk thistle; generic
    "WO-2025040716-A1",                           # potato starch composition; characterisation only
    "WO-2025040848-A1", "EP-4512250-A1",          # method for manufacturing protein powder; generic food
    "US-20260033515-A1", "CN-119486602-A",        # formulation (proteinaceous microgel); generic food

    # Cross-cutting pillar — equipment or no product context
    "US-20220213427-A1", "AU-2020269611-B2",      # bioreactor device; no food product
    "US-20240341343-A1", "EP-4376641-A1",         # system for continuous extrusion; generic "food product"
    "US-20250338870-A1", "CN-118434289-A",        # improving handling properties of protein ingredients
    "EP-4451923-A1", "FR-3130517-B1",             # extrusion nozzle; equipment, no product
    "EP-4333632-A1", "ES-3037858-T3",             # binder liquid agglomeration system; equipment
    "US-20250194649-A1", "JP-2025510215-A",       # fatty acid amides; generic ingestible composition
    "US-20260083159-A1", "EP-4522662-A1",         # sugar beet pulp ingredient; no product context
    "EP-4743572-A1", "CN-121794375-A",            # protein arginine deiminase; enzyme, no food product
    "WO-2025026693-A1",                           # bioreactor for educational/household use
    "WO-2025132527-A1", "EP-4574958-A1",          # bioreactor system; organism culturing, no product
    "WO-2025163483-A1", "EP-4597070-A1",          # device for generating microtissue fragments
    "WO-2025233614-A1", "GB-2640885-A",           # reactor apparatus; no food product
    "US-20250302085-A1", "EP-4623707-A1",         # extrusion die; equipment, no product
    "WO-2025153826-A1", "GB-202510750-D0",        # cell culture construct; no specific food product
    "US-20250367844-A1", "DE-102024110985-A1",    # slicing machine; no specific food product type
    "WO-2024261382-A1", "FI-131756-B1",           # oat-derived protein-rich composition; generic food
    "WO-2025201667-A1",                           # waste processing system; not AP food context
]

AGNOSTIC_IDS = list(dict.fromkeys(AGNOSTIC_IDS))  # deduplicate, preserve order
print(f"Total IDs to reclassify: {len(AGNOSTIC_IDS)}")

# ---------------------------------------------------------------------------
# 1. Update pandas DataFrame
# ---------------------------------------------------------------------------

def update_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with Cross-cutting → Agnostic for the listed IDs."""
    df = df.copy()
    mask = df["id"].isin(AGNOSTIC_IDS) & (df["endproduct"] == "Cross-cutting")
    n = mask.sum()
    df.loc[mask, "endproduct"] = "Agnostic"
    print(f"DataFrame: updated {n} rows → Agnostic")
    return df


# Example usage:
#   df = pd.read_csv("patents_training_data.csv")
#   df_updated = update_dataframe(df)

# ---------------------------------------------------------------------------
# 2. Update DuckDB table
# ---------------------------------------------------------------------------

DB_PATH = Path("../../patents_training.db")   # adjust if running from a different directory

def update_duckdb(db_path: Path = DB_PATH) -> None:
    """Update patents_raw.endproduct in DuckDB for the listed IDs."""
    con = duckdb.connect(str(db_path))

    # Verify table and column exist
    tables = con.sql("SHOW TABLES").df()["name"].tolist()
    assert "patents_raw" in tables, f"Table 'patents_raw' not found. Available: {tables}"

    cols = con.sql("DESCRIBE patents_raw").df()["column_name"].tolist()
    assert "endproduct" in cols, f"Column 'endproduct' not found. Columns: {cols}"

    # Build parameterised query
    placeholders = ", ".join(f"'{id_}'" for id_ in AGNOSTIC_IDS)
    query = f"""
        UPDATE patents_raw
        SET endproduct = 'Agnostic'
        WHERE id IN ({placeholders})
          AND endproduct = 'Cross-cutting'
    """
    con.execute(query)

    # Verify
    n = con.sql(
        f"SELECT COUNT(*) AS n FROM patents_raw WHERE id IN ({placeholders}) AND endproduct = 'Agnostic'"
    ).df()["n"].iloc[0]
    print(f"DuckDB: {n} rows now labelled Agnostic")

    # Show updated distribution
    dist = con.sql(
        "SELECT endproduct, COUNT(*) AS n FROM patents_raw GROUP BY endproduct ORDER BY n DESC"
    ).df()
    print("\nUpdated endproduct distribution:")
    print(dist.to_string(index=False))

    con.close()


if __name__ == "__main__":
    # ---- DataFrame update (demo — reads from CSV) ----
    csv_path = Path("../../../Patents data 2026 - ALL patents 2015-2025.csv")
    if csv_path.exists():
        df = pd.read_csv(csv_path)
        df_updated = update_dataframe(df)
    else:
        print(f"CSV not found at {csv_path} — skipping DataFrame demo")

    # ---- DuckDB update ----
    if DB_PATH.exists():
        update_duckdb(DB_PATH)
    else:
        print(f"DuckDB not found at {DB_PATH} — skipping database update")
        print("Run update_duckdb(Path('<path-to-db>')) with the correct path.")
