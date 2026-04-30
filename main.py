dev = False


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


print(f"Using {num_threads} threads")
print(f"Source file obtained")

from descriptions import fill_descriptions
df = fill_descriptions(df, NCBI)

from symbols import fill_symbols
df = fill_symbols(df, UNIPROT, taxon_id(TAXON_REF))

from all_ids import fill_all_ids
df = fill_all_ids(df, NCBI, TAXON)


df = df[["gene_id", "ncbi_id", "gene_symbol", "gene_biotype", "description", "baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj"]]

df.to_csv("S:/INSERM/Pipeline/"+FILE+"_final.txt", sep="\t", index=False)