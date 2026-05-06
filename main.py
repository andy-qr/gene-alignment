from ensembl import is_ensembl, ensembl_to_loc
from taxon import taxon_id
import pandas as pd
import re


TAXON_REF = "Homo sapiens"
NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNIPROT = "https://rest.uniprot.org/uniprotkb/search"



def run(TAXON, FILE, output_format="txt"):
    from api import num_threads

    if FILE.endswith(".xlsx") or FILE.endswith(".xls"):
        df = pd.read_excel(FILE)
    else:
        df = pd.read_csv(FILE, sep="\t")


    if "gene_name" not in df.columns:
        if "gene_id" not in df.columns:
            raise ValueError(f"gene_name or gene_id column required")
        else:
            df["gene_name"] = df["gene_id"]
    if "gene_id" not in df.columns:
            df["gene_id"] = df["gene_name"]

    print(f"Using {num_threads} threads")
    print(f"Source file obtained")
    
    if is_ensembl(df):
        df = ensembl_to_loc(df)
    else:
        from all_ids import fill_all_ids
        df = fill_all_ids(df, NCBI, TAXON)
    
    from descriptions import fill_descriptions
    df = fill_descriptions(df, NCBI)

    from symbols import fill_symbols
    df = fill_symbols(df, UNIPROT, taxon_id(TAXON_REF)[1])

    df["gene_id"] = df["ncbi_id"]
    df.drop(columns="ncbi_id", inplace=True)
    fixed_cols = ["gene_id", "gene_name", "gene_biotype", "gene_symbol", "description"]
    other_cols = [c for c in df.columns if c not in fixed_cols]
    df = df[fixed_cols + other_cols]

    base_name = FILE.rsplit(".", 1)[0]
    if output_format=="xlsx":
        df.to_excel(base_name+"_completed.xlsx", index=False)
    else:
        df.to_csv(base_name+"_completed.txt", sep="\t", index=False)
    
    print("File saved")