from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import pandas as pd
import threading
import requests
import time
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import get_thread_key, num_threads


def fill_descriptions(df, base):

    def fetch_batch(symbols):
        api_key, wait = get_thread_key()
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
        for gene_name, info in summary_r.json().get("result", {}).items():
            if gene_name == "uids":
                continue
            batch_results.append({
                "gene_id":     "LOC" + gene_name,
                "symbol_ncbi": info.get("name"),
                "description": info.get("description")
            })
        time.sleep(wait)
        return batch_results

    loc_symbols = df[
        df["gene_name"].str.startswith("LOC") & 
        (df["gene_biotype"] == "protein_coding")
    ]["gene_name"].tolist()
    batch_size = 100
    total = len(loc_symbols)
    batches = [loc_symbols[i:i + batch_size] for i in range(0, total, batch_size)]

    results = []
    results_lock = threading.Lock()

    width = len(str(total))
    bar_format = f"{{desc}}: {{n:{width}d}}/{{total}} |{{bar:50}}|"
    with tqdm(total=total, desc="Searching for NCBI descriptions", unit="gene",
          bar_format=bar_format,
          ascii=" █", leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(fetch_batch, batch): len(batch) for batch in batches}
            for future in as_completed(futures):
                batch_len = futures[future]
                with results_lock:
                    results.extend(future.result())
                pbar.update(batch_len)
        pbar.n = pbar.total
        pbar.refresh()


    df_ncbi = pd.DataFrame(results)
    if df_ncbi.empty:
        if "description" not in df.columns:
            df["description"] = ""
        print("LOC genes descriptions obtained")
        return df
    id_to_desc = dict(zip(df_ncbi["gene_id"], df_ncbi["description"]))
    
    df["description"] = df["gene_name"].map(id_to_desc).fillna(df.get("description", ""))


    print(f"LOC genes descriptions obtained")

    return df