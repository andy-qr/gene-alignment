from tqdm import tqdm
import requests
import time
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import get_next_key, wait


def fill_all_ids(df, base, taxon):
    df["ncbi_id"] = df["ncbi_id"].fillna("").astype(str)
    mask_missing = (df["ncbi_id"] == "")
    non_loc_symbols = df.loc[mask_missing, "gene_id"].tolist()

    def fetch_ids_batch(symbols):
        query = " OR ".join([f"{s}[Gene Name]" for s in symbols])
        query += f' AND "{taxon}"[Organism]'
        search_r = requests.get(f"{base}/esearch.fcgi", params={
            "db":      "gene",
            "term":    query,
            "retmax":  len(symbols),
            "retmode": "json",
            "api_key": get_next_key()
        }, timeout=10)
        ids = search_r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return {}
        summary_r = requests.get(f"{base}/esummary.fcgi", params={
            "db":      "gene",
            "id":      ",".join(ids),
            "retmode": "json",
            "api_key": get_next_key()
        }, timeout=10)
        symbol_to_id = {}
        for gene_id, info in summary_r.json().get("result", {}).items():
            if gene_id == "uids":
                continue
            symbol_to_id[info.get("name", "")] = gene_id
        return symbol_to_id
    symbol_to_id = {}
    with tqdm(total=len(non_loc_symbols), desc="Searching for NCBI ids", unit="gene",
            bar_format="{desc}: {n}/{total} |{bar}|",
            ascii="░▒▓█", leave=False) as pbar:
        for i in range(0, len(non_loc_symbols), 100):
            batch = non_loc_symbols[i:i + 100]
            symbol_to_id.update(fetch_ids_batch(batch))
            pbar.update(len(batch))
            time.sleep(wait)
    df.loc[mask_missing, "ncbi_id"] = df.loc[mask_missing, "gene_id"].map(symbol_to_id)
    return df