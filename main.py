dev = False

get_descriptions = True
get_symbols = True
get_all_ids = True


import pandas as pd
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from taxon import taxon_id
from api import num_threads



TAXON_REF = "Homo sapiens"
NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNIPROT = "https://rest.uniprot.org/uniprotkb/search"

if dev:
    TAXON = "Columba livia"
    FILE = "blasto_vs_fibro"
else:
    TAXON = input("Studied taxon (ex: Columba livia) : ").strip()
    while not taxon_id(TAXON):
        TAXON = input("Studied taxon (ex: Columba livia) : ").strip()
    FILE = input("Source file name (ex: blasto_vs_fibro) : ").strip()



df = pd.read_csv(FILE+".txt", sep="\t")
df.drop(columns="gene_name", inplace=True)

df["gene_symbol"] = df.apply(
    lambda r:
    "" if r["gene_id"][:3] == "LOC" and r["gene_biotype"] == "protein_coding"
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

print(f"Using {num_threads} threads")
print(f"Source file obtained")

if get_descriptions:
    from descriptions import fill_descriptions
    df = fill_descriptions(df, NCBI)
    print(f"LOC genes descriptions obtained")
    if dev:
        df.to_csv("S:/INSERM/Pipeline/"+FILE+"_descriptions.txt", sep="\t", index=False)
else:
    df = pd.read_csv(FILE+"_descriptions.txt", sep="\t", dtype={"ncbi_id": str})

if get_symbols:
    from symbols import fill_symbols
    df = fill_symbols(df, UNIPROT, taxon_id(TAXON_REF))
    print(f"LOC genes symbols obtained")
    if dev:
        df.to_csv("S:/INSERM/Pipeline/"+FILE+"_symbols.txt", sep="\t", index=False)
else :
    df = pd.read_csv(FILE+"_symbols.txt", sep="\t", dtype={"ncbi_id": str})

if get_all_ids:
    from all_ids import fill_all_ids
    df = fill_all_ids(df, NCBI, TAXON)
    print(f"All NCBI gene ids obtained")
    df.to_csv("S:/INSERM/Pipeline/"+FILE+"_final.txt", sep="\t", index=False)