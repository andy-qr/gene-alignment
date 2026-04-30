from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import threading
import requests
import time
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import get_thread_key, num_threads


def fill_all_ids(df, base, taxon):

    df["ncbi_id"] = df.apply(
        lambda r:
        r["gene_id"].replace("LOC", "") if r["gene_id"][:3] == "LOC"
        else "",
        axis = 1
    ).astype(str)

    df["ncbi_id"] = df["ncbi_id"].fillna("").astype(str)
    mask_missing = (df["ncbi_id"] == "")
    non_loc_symbols = df.loc[mask_missing, "gene_id"].tolist()

    # Découper en batches
    batches = [non_loc_symbols[i:i + 100] for i in range(0, len(non_loc_symbols), 100)]

    def fetch_ids_batch(symbols):
        api_key, wait = get_thread_key()
        query = " OR ".join([f"{s}[Gene Name]" for s in symbols])
        query += f' AND "{taxon}"[Organism]'
        search_r = requests.get(f"{base}/esearch.fcgi", params={
            "db":      "gene",
            "term":    query,
            "retmax":  len(symbols),
            "retmode": "json",
            "api_key": api_key
        }, timeout=10)
        ids = search_r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return {}
        summary_r = requests.get(f"{base}/esummary.fcgi", params={
            "db":      "gene",
            "id":      ",".join(ids),
            "retmode": "json",
            "api_key": api_key
        }, timeout=10)
        symbol_to_id = {}
        for gene_id, info in summary_r.json().get("result", {}).items():
            if gene_id == "uids":
                continue
            symbol_to_id[info.get("name", "")] = gene_id
        time.sleep(wait)
        return symbol_to_id

    symbol_to_id = {}
    result_lock = threading.Lock()

    with tqdm(total=len(non_loc_symbols), desc="Searching for NCBI ids", unit="gene",
          bar_format="{desc}: {n}/{total} |{bar}|",
          ascii="░▒▓█", leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(fetch_ids_batch, batch): len(batch) for batch in batches}
            for future in as_completed(futures):
                batch_len = futures[future]
                with result_lock:
                    symbol_to_id.update(future.result())
                pbar.update(batch_len)
        pbar.n = pbar.total
        pbar.refresh()
    
    df.loc[mask_missing, "ncbi_id"] = df.loc[mask_missing, "gene_id"].map(symbol_to_id)
    df["ncbi_id"] = df["ncbi_id"].fillna("").astype(str)
    
    print(f"All NCBI gene ids obtained")
    
    return df