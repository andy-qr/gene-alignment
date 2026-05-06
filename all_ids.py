from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import threading
import requests
import time
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import get_thread_key, num_threads



def fill_all_ids(df, base, taxon):

    if "gene_biotype" not in df.columns:
        df["gene_biotype"] = ""
        
        loc_ids = df[df["gene_name"].str.startswith("LOC")]["gene_name"].tolist()
        loc_batches = [loc_ids[i:i+100] for i in range(0, len(loc_ids), 100)]
        
        def fetch_biotype_batch(symbols):
            api_key, wait = get_thread_key()
            ids_numeriques = [s.replace("LOC", "") for s in symbols]
            summary_r = requests.get(f"{base}/esummary.fcgi", params={
                "db":      "gene",
                "id":      ",".join(ids_numeriques),
                "retmode": "json",
                "api_key": api_key
            }, timeout=10)
            result = {}
            for gene_id, info in summary_r.json().get("result", {}).items():
                if gene_id == "uids":
                    continue
                biotype = info.get("type", "")
                result["LOC" + gene_id] = biotype
            time.sleep(wait)
            return result
        
        id_to_biotype = {}
        for batch in loc_batches:
            id_to_biotype.update(fetch_biotype_batch(batch))
        
        df.loc[df["gene_name"].str.startswith("LOC"), "gene_biotype"] = df.loc[df["gene_id"].str.startswith("LOC"), "gene_name"].map(id_to_biotype)
        
        df.loc[~df["gene_name"].str.startswith("LOC"), "gene_biotype"] = "protein_coding"


    df["ncbi_id"] = df.apply(
        lambda r:
        r["gene_name"].replace("LOC", "") if r["gene_id"][:3] == "LOC"
        else "",
        axis = 1
    ).astype(str)

    df["ncbi_id"] = df["ncbi_id"].fillna("").astype(str)
    mask_missing = (df["ncbi_id"] == "")
    non_loc_symbols = df.loc[mask_missing, "gene_name"].tolist()

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

    width = len(str(len(non_loc_symbols)))
    bar_format = f"{{desc}}: {{n:{width}d}}/{{total}} |{{bar:50}}|"
    with tqdm(total=len(non_loc_symbols), desc="Searching for NCBI ids", unit="gene",
          bar_format=bar_format,
          ascii=" █", leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(fetch_ids_batch, batch): len(batch) for batch in batches}
            for future in as_completed(futures):
                batch_len = futures[future]
                with result_lock:
                    symbol_to_id.update(future.result())
                pbar.update(batch_len)
        pbar.n = pbar.total
        pbar.refresh()
        
    df.loc[mask_missing, "ncbi_id"] = df.loc[mask_missing, "gene_id"].map(symbol_to_id).fillna("").astype(str)
    df["ncbi_id"] = df["ncbi_id"].fillna("").astype(str)
    
    print(f"All NCBI gene ids obtained")
    
    return df