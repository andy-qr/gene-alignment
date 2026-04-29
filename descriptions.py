from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import pandas as pd
import threading
import requests
import time
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import api_keys, wait

thread_local = threading.local()

def get_thread_key():
    if not hasattr(thread_local, "api_key"):
        idx = int(threading.current_thread().name.split("_")[-1]) % len(api_keys)
        thread_local.api_key = api_keys[idx]
    return thread_local.api_key


def fill_descriptions(df, base):

    def fetch_batch(symbols):
        api_key = get_thread_key()
        ids_numeriques = [s.replace("LOC", "") for s in symbols]
        summary_r = requests.get(f"{base}/esummary.fcgi", params={
            "db":      "gene",
            "id":      ",".join(ids_numeriques),
            "retmode": "json",
            "api_key": api_key
        })
        if summary_r.status_code != 200 or not summary_r.text.strip():
            tqdm.write(f"  Erreur: {summary_r.status_code} — {summary_r.text[:200]}")
            return []
        batch_results = []
        for gene_id, info in summary_r.json().get("result", {}).items():
            if gene_id == "uids":
                continue
            batch_results.append({
                "gene_id":     "LOC" + gene_id,
                "symbol_ncbi": info.get("name"),
                "description": info.get("description")
            })
        time.sleep(wait)
        return batch_results

    loc_symbols = df[df["gene_symbol"] == ""]["gene_id"].tolist()
    batch_size = 100
    total = len(loc_symbols)
    batches = [loc_symbols[i:i + batch_size] for i in range(0, total, batch_size)]

    results = []
    results_lock = threading.Lock()

    with tqdm(total=total, desc="Searching for NCBI descriptions", unit="gene",
              bar_format="{desc}: {n}/{total} |{bar}|",
              ascii="░▒▓█", leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=len(api_keys)) as executor:
            for batch_result in executor.map(fetch_batch, batches):
                with results_lock:
                    results.extend(batch_result)
                pbar.update(batch_size)

    tqdm.write("\r" + " " * 80 + "\r", end="")
    print("✓ Descriptions des LOCs récupérées")

    df_ncbi = pd.DataFrame(results)
    df = df.merge(df_ncbi[["gene_id", "symbol_ncbi", "description"]], on="gene_id", how="left")

    df["gene_symbol"] = df.apply(
        lambda r: r["symbol_ncbi"] if r["gene_symbol"] == "" and pd.notna(r["symbol_ncbi"]) else r["gene_symbol"],
        axis=1
    )
    df.drop(columns="symbol_ncbi", inplace=True)

    cols = df.columns.tolist()
    cols.remove("description")
    cols.insert(4, "description")
    df = df[cols]

    return df