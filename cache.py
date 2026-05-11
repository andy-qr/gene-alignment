import os
import sys
import pandas as pd

def get_base_path():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CACHE_DIR = os.path.join(get_base_path(), "gene_cache")

def _cache_path(taxon):
    return os.path.join(CACHE_DIR, f"{taxon.replace(' ', '_')}.txt")

def load_cache(taxon):
    path = _cache_path(taxon)
    if not os.path.isfile(path):
        return pd.DataFrame(columns=["gene_symbol", "ensembl_id", "ncbi_id"])
    return pd.read_csv(path, sep="\t", dtype=str).fillna("")

def fill_cache(df, taxon):
    os.makedirs(CACHE_DIR, exist_ok=True)

    symbol_mask = (
        df["gene_symbol"].astype(bool) &
        ~df["gene_symbol"].str.startswith("LOC") &
        ~df["gene_symbol"].str.match(r"^ENS[A-Z]*G\d+")
    )

    new = df.loc[symbol_mask, ["gene_name", "gene_id", "gene_symbol"]].copy()
    new["ensembl_id"] = new["gene_name"].where(
        new["gene_name"].str.match(r"^ENS[A-Z]*G\d+"), ""
    )
    new["ncbi_id"] = new["gene_id"].fillna("")
    new = new[["gene_symbol", "ensembl_id", "ncbi_id"]]

    cache = load_cache(taxon)
    new = new[~new["gene_symbol"].isin(cache["gene_symbol"])]

    if not new.empty:
        merged = pd.concat([cache, new], ignore_index=True)
        merged = merged.sort_values("gene_symbol", key=lambda s: s.str.lower())
        merged.to_csv(_cache_path(taxon), sep="\t", index=False)
        print(f"Cache: {len(new)} correspondences logged")
    else:
        print("Cache: 0 correspondences logged")