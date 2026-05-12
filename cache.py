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


def fill_cache(df, taxon, not_found):
    os.makedirs(CACHE_DIR, exist_ok=True)

    symbol_mask = (
        df["gene_symbol"].astype(bool) &
        (df["gene_symbol"] != not_found) &
        (df["ncbi_id"].astype(bool) | df["gene_id"].str.match(r"^ENS[A-Z]*G\d+"))
    )

    new = df.loc[symbol_mask, ["gene_id", "ncbi_id", "gene_symbol"]].copy()
    new["ensembl_id"] = new["gene_id"].where(
        new["gene_id"].str.match(r"^ENS[A-Z]*G\d+"), ""
    )
    new = new[["gene_symbol", "ensembl_id", "ncbi_id"]]

    cache = load_cache(taxon)
    new = new[~new["gene_symbol"].isin(cache["gene_symbol"])]

    if not new.empty:
        merged = pd.concat([cache, new], ignore_index=True)
        merged = merged.sort_values("gene_symbol", key=lambda s: s.str.lower())
        merged.to_csv(_cache_path(taxon), sep="\t", index=False)
    print(f"Cache: {len(new)} correspondences logged")


def use_cache(df, taxon):
    df_cache = load_cache(taxon)
    print("Using cache")

    df_cache["loc_id"] = df_cache["ncbi_id"].apply(
        lambda x: f"LOC{x}" if x else ""
    )

    loc_map = df_cache.set_index("loc_id")["gene_symbol"].to_dict()
    loc_map.pop("", None)
    ensembl_map = df_cache.set_index("ensembl_id")["gene_symbol"].to_dict()
    ensembl_map.pop("", None)

    combined_map = {**ensembl_map, **loc_map}

    sample_loc_keys = list(loc_map.keys())[:5]
    sample_gene_ids = df[df["gene_id"].str.startswith("LOC")]["gene_id"].head(5).tolist()

    

    df["gene_symbol"] = df["gene_id"].map(combined_map).fillna("")

    cache_found = df["gene_symbol"].astype(bool).sum()
    print(f"Cache hit: {cache_found}/{len(df)} genes resolved")
    return df