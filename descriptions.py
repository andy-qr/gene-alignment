from tqdm import tqdm
import pandas as pd
import requests
import time
import os
 
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import get_next_key, wait
 
 
def fill_descriptions(df, base):
 
    def fetch_batch(symbols):
        ids_numeriques = [s.replace("LOC", "") for s in symbols]
        summary_r = requests.get(f"{base}/esummary.fcgi", params={
            "db":      "gene",
            "id":      ",".join(ids_numeriques),
            "retmode": "json",
            "api_key": get_next_key()
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
        return batch_results
 
    loc_symbols = df[df["gene_symbol"] == ""]["gene_id"].tolist()
    batch_size = 100
    total = len(loc_symbols)
    results = []
 
    with tqdm(total=total, desc="Searching for NCBI descriptions", unit="gene",
              bar_format="{desc}: {n}/{total} |{bar}|",
              ascii="░▒▓█", leave=False) as pbar:
        for i in range(0, total, batch_size):
            batch = loc_symbols[i:i + batch_size]
            results.extend(fetch_batch(batch))
            pbar.update(len(batch))
            time.sleep(wait)
 
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
    cols.insert(3, "description")
    df = df[cols]
 
    return df
