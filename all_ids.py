from tqdm import tqdm
import requests
import time
import os
from concurrent.futures import ThreadPoolExecutor
import threading

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import api_keys, wait

thread_local = threading.local()

def get_thread_key():
    if not hasattr(thread_local, "api_key"):
        idx = int(threading.current_thread().name.split("_")[-1]) % len(api_keys)
        thread_local.api_key = api_keys[idx]
    return thread_local.api_key


def fill_all_ids(df, base, taxon):
    df["ncbi_id"] = df["ncbi_id"].fillna("").astype(str)
    mask_missing = (df["ncbi_id"] == "")
    non_loc_symbols = df.loc[mask_missing, "gene_id"].tolist()

    # Découper en batches
    batches = [non_loc_symbols[i:i + 100] for i in range(0, len(non_loc_symbols), 100)]

    def fetch_ids_batch(symbols):
        api_key = get_thread_key()
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
        with ThreadPoolExecutor(max_workers=len(api_keys)) as executor:
            for batch_result in executor.map(fetch_ids_batch, batches):
                with result_lock:
                    symbol_to_id.update(batch_result)
                pbar.update(100)

    df.loc[mask_missing, "ncbi_id"] = df.loc[mask_missing, "gene_id"].map(symbol_to_id)
    df["ncbi_id"] = df["ncbi_id"].fillna("").astype(str)
    return df