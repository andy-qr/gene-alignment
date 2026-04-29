API_KEY = "6aa784ef049697c8d1801ce03dd5b1344908"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TAXON = "Columba livia"
TAXON_REF = "Homo sapiens"

get_descriptions = True
get_symbols = False
get_all_ids = True

import os
import pandas as pd
os.chdir(os.path.dirname(os.path.abspath(__file__)))


df = pd.read_csv("blasto_vs_fibro.txt", sep="\t")
df.drop(columns="gene_name", inplace=True)

df["gene_symbol"] = df.apply(
    lambda r:
    "" if r["gene_id"][:3] == "LOC" and r["gene_biotype"] == "protein_coding"
    else "uncharacterized " + r["gene_id"] if r["gene_id"][:3] == "LOC"
    else r["gene_id"],
    axis=1
)

df["ncbi_id"] = df.apply(
    lambda r:
    r["gene_id"].replace("LOC", "") if r["gene_id"][:3] == "LOC"
    else "",
    axis = 1
).astype(str)

cols = df.columns.tolist()
cols.remove("ncbi_id")
cols.remove("gene_symbol")
cols.insert(1, "ncbi_id")
cols.insert(3, "gene_symbol")
df = df[cols]

print(f"Source file obtained")

if get_descriptions:
    from descriptions import fill_descriptions
    df = fill_descriptions(df, BASE)
    print(f"LOC genes descriptions obtained")
    df.to_csv("S:/INSERM/Pipeline/blasto_vs_fibro_descriptions.txt", sep="\t", index=False)
else:
    df = pd.read_csv("blasto_vs_fibro_descriptions.txt", sep="\t", dtype={"ncbi_id": str})

if get_symbols:
    from symbols import fill_symbols
    df = fill_symbols(df, BASE, TAXON_REF)
    print(f"LOC genes symbols obtained")
    df.to_csv("S:/INSERM/Pipeline/blasto_vs_fibro_symbols.txt", sep="\t", index=False)
else :
    df = pd.read_csv("blasto_vs_fibro_symbols.txt", sep="\t", dtype={"ncbi_id": str})

if get_all_ids:
    from all_ids import fill_all_ids
    df = fill_all_ids(df, BASE, TAXON)
    print(f"All gene NCBI ids obtained")
    df.to_csv("S:/INSERM/Pipeline/Blasto_vs_fibro_final.txt", sep="\t", index=False)