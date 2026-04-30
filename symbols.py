from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from difflib import SequenceMatcher
import threading
import requests
import time
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import num_threads, default_wait

UNIPROT_URL = "https://rest.uniprot.org/uniprotkb/search"
BATCH_SIZE = 20

def fill_symbols(df, base, taxon_ref):
    total_matched = 0
    matched_lock = threading.Lock()

    def similarity(a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def fetch_single(description):
        try:
            response = requests.get(UNIPROT_URL, params={
                "query":  f'protein_name:"{description}" AND reviewed:true AND organism_id:9606',
                "fields": "gene_names,protein_name",
                "format": "json",
                "size":   5
            }, timeout=10)
            results = response.json().get("results", [])
            
            best_symbol = ""
            best_score = 0

            for r in results:
                if r.get("entryType") != "UniProtKB reviewed (Swiss-Prot)":
                    continue
                genes = r.get("genes", [])
                symbol = genes[0].get("geneName", {}).get("value", "").upper() if genes else ""
                if not symbol or symbol.startswith("LOC"):
                    continue

                all_names = []
                desc = r.get("proteinDescription", {})
                rec = desc.get("recommendedName", {})
                if rec:
                    all_names.append(rec.get("fullName", {}).get("value", ""))
                for alt in desc.get("alternativeNames", []):
                    all_names.append(alt.get("fullName", {}).get("value", ""))

                # Prendre le meilleur score de similarité parmi tous les noms
                score = max((similarity(description, name) for name in all_names), default=0)
                if score > best_score:
                    best_score = score
                    best_symbol = symbol

            time.sleep(default_wait)
            # Seuil minimum de similarité
            return best_symbol if best_score >= 0.4 else "", best_score

        except Exception as e:
            tqdm.write(f"  Erreur: {e}")
            time.sleep(default_wait)
            return "", 0

    mask = df["gene_symbol"].str.startswith("LOC") & ~df["description"].str.startswith("uncharacterized")
    desc_unique = df.loc[mask, "description"].dropna().astype(str).unique()

    cache = {}
    cache_lock = threading.Lock()

    def process_desc(args):
        i, desc = args
        symbol, score = fetch_single(desc)
        with cache_lock:
            cache[desc] = symbol
        return i, bool(symbol)

    with tqdm(total=len(desc_unique), desc="Searching UniProt symbols", unit="description",
              bar_format="{desc}: {n}/{total} |{bar}|",
              ascii="░▒▓█", leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(process_desc, args): args for args in enumerate(desc_unique)}
            for future in as_completed(futures):
                i, matched = future.result()
                with matched_lock:
                    total_matched += matched
                pbar.update(1)
        pbar.n = pbar.total
        pbar.refresh()

    print(f"✓ {total_matched}/{len(desc_unique)} symbols résolus via UniProt Swiss-Prot")

    df.loc[mask, "gene_symbol"] = df.loc[mask, "description"].map(cache).fillna("")
    df["gene_symbol"] = df.apply(
        lambda r: r["gene_symbol"] if r["gene_symbol"] else r["gene_id"],
        axis=1
    )
    return df