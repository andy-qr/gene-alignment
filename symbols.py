from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import threading
import requests
import time
import os
import re

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import get_thread_key, num_threads


def fill_symbols(df, base, taxon_ref):

    def clean_description(description):
        suffixes_espaces = [" homolog", " ortholog"]
        suffixes_tiret = ["like", "related"]
        
        for suffix in suffixes_espaces:
            description = description.replace(suffix, "")
        
        words = description.split()
        cleaned_words = []
        for word in words:
            if "-" in word:
                parts = word.split("-")
                if parts[-1].lower() in suffixes_tiret:
                    word = "-".join(parts[:-1])
            cleaned_words.append(word)
        
        return " ".join(cleaned_words).strip()

    def get_symbol_from_description(description, taxon=taxon_ref):
        if not description or "uncharacterized" in description.lower():
            return "", 0
        api_key, wait = get_thread_key()
        clean = clean_description(description)

        symbol_match = re.search(r'\b([A-Z][A-Z0-9]{1,9})\b', description)
        if symbol_match:
            candidate = symbol_match.group(1)
            try:
                search_r = requests.get(f"{base}/esearch.fcgi", params={
                    "db":      "gene",
                    "term":    f'{candidate}[Gene Name] AND "{taxon}"[Organism]',
                    "retmax":  1,
                    "retmode": "json",
                    "api_key": api_key
                }, timeout=10)
                ids = search_r.json().get("esearchresult", {}).get("idlist", [])
                if ids:
                    summary_r = requests.get(f"{base}/esummary.fcgi", params={
                        "db":      "gene",
                        "id":      ids[0],
                        "retmode": "json",
                        "api_key": api_key
                    }, timeout=10)
                    info = summary_r.json().get("result", {}).get(ids[0], {})
                    symbol = info.get("name", "")
                    if symbol and not symbol.startswith("LOC"):
                        return symbol, wait
            except Exception:
                pass

        try:
            search_r = requests.get(f"{base}/esearch.fcgi", params={
                "db":      "gene",
                "term":    f'"{clean}"[Gene Description] AND "{taxon}"[Organism]',
                "retmax":  1,
                "retmode": "json",
                "api_key": api_key
            }, timeout=10)
            ids = search_r.json().get("esearchresult", {}).get("idlist", [])
            if ids:
                summary_r = requests.get(f"{base}/esummary.fcgi", params={
                    "db":      "gene",
                    "id":      ids[0],
                    "retmode": "json",
                    "api_key": api_key
                }, timeout=10)
                info = summary_r.json().get("result", {}).get(ids[0], {})
                symbol = info.get("name", "")
                if symbol and not symbol.startswith("LOC"):
                    return symbol, wait
        except Exception:
            pass

        try:
            search_r = requests.get(f"{base}/esearch.fcgi", params={
                "db":      "gene",
                "term":    f'"{clean}"[All Fields] AND "{taxon}"[Organism]',
                "retmax":  1,
                "retmode": "json",
                "api_key": api_key
            }, timeout=10)
            ids = search_r.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return "", 0
            summary_r = requests.get(f"{base}/esummary.fcgi", params={
                "db":      "gene",
                "id":      ids[0],
                "retmode": "json",
                "api_key": api_key
            }, timeout=10)
            info = summary_r.json().get("result", {}).get(ids[0], {})
            symbol = info.get("name", "")
            return ("", 0) if symbol.startswith("LOC") else (symbol, wait)
        except Exception as e:
            tqdm.write(f"  Erreur: {e}")
            return "", 0

    mask = df["gene_symbol"].str.startswith("LOC") & ~df["description"].str.startswith("uncharacterized")
    desc_unique = df.loc[mask, "description"].dropna().unique()

    cache = {}
    cache_lock = threading.Lock()

    def process_desc(args):
        i, desc = args
        symbol, wait = get_symbol_from_description(desc)
        time.sleep(wait)
        with cache_lock:
            cache[desc] = symbol
        return i

    with tqdm(total=len(desc_unique), desc="Searching for NCBI symbols", unit="description",
            bar_format="{desc}: {n}/{total} |{bar}|",
            ascii="░▒▓█", leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            for i in executor.map(process_desc, enumerate(desc_unique)):
                pbar.update(1)
                if (i + 1) % 100 == 0:
                    with cache_lock:
                        df.loc[mask, "gene_symbol"] = df.loc[mask, "description"].map(cache)
                    df["gene_symbol"] = df["gene_symbol"].fillna("")
                    df.to_csv("S:/INSERM/Pipeline/blasto_vs_fibro_symbols_temp.txt", sep="\t", index=False)


    df.loc[mask, "gene_symbol"] = df.loc[mask, "description"].map(cache)
    df["gene_symbol"] = df.apply(
        lambda r:
        r["gene_symbol"] if r["gene_symbol"] else r["gene_id"],
        axis=1
    )

    return df