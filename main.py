from ensembl import is_ensembl, ensembl_to_loc
from taxon import taxon_id
import pandas as pd
import os


TAXON_REF = "Homo sapiens"
NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNIPROT = "https://rest.uniprot.org/uniprotkb/search"


def run(TAXON, FILE, output_format="txt", out_dir=None):
    from api import num_threads

    if FILE.endswith(".xlsx") or FILE.endswith(".xls"):
        df = pd.read_excel(FILE)
    else:
        df = pd.read_csv(FILE, sep="\t")

    df["gene_id"] = df["gene_id"].astype(str)
    df["gene_name"] = df["gene_name"].astype(str)

    if "gene_name" not in df.columns:
        if "gene_id" not in df.columns:
            raise ValueError(f"gene_name or gene_id column required")
        else:
            df["gene_name"] = df["gene_id"]
    if "gene_id" not in df.columns:
        df["gene_id"] = df["gene_name"]

    meta_cols = {"gene_id", "gene_name", "gene_biotype", "gene_symbol", "description",
                 "baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj"}
    if "baseMean" not in df.columns:
        count_cols = [c for c in df.columns if c not in meta_cols and pd.api.types.is_numeric_dtype(df[c])]
        if count_cols:
            df["baseMean"] = df[count_cols].mean(axis=1)
            print(f"baseMean calculated from {len(count_cols)} count columns")

    if "baseMean" in df.columns:
        before = len(df)
        df = df[df["baseMean"] >= 10]
        print(f"Low expression genes removed ({before - len(df)} removed, baseMean < 10)")

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

    base_name = os.path.splitext(os.path.basename(FILE))[0]
    if out_dir:
        out_base = os.path.join(out_dir, base_name)
    else:
        out_base = os.path.splitext(FILE)[0]

    if output_format == "xlsx":
        df.to_excel(out_base + "_completed.xlsx", index=False)
    else:
        df.to_csv(out_base + "_completed.txt", sep="\t", index=False)

    print(f"File saved: {out_base}_completed.{output_format}")