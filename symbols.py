from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from tqdm import tqdm
import threading
import requests
import time
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import num_threads, default_wait

THRESHOLD = 0.25
SIZE = 5


def fill_symbols(df, base, taxon_ref):


    if "gene_symbol" not in df.columns:
        df["gene_symbol"] = ""

    df["gene_symbol"] = df.apply(
        lambda r:
        r["gene_symbol"] if r["gene_symbol"]
        else "" if r["gene_name"][:3] == "LOC" and r["gene_biotype"] == "protein_coding"
        else r["gene_name"],
        axis=1
    )

    def similarity(a, b):
        a = a.lower().replace("-", " ")
        b = b.lower().replace("-", " ")
        return SequenceMatcher(None, a, b).ratio()

    def clean_description(description):
        suffixes = ["associated","like", "related","probable"]
        for suffix in suffixes:
            description = description.replace(suffix, "")
        words = description.split()
        cleaned_words = []
        for word in words:
            if "-" in word:
                parts = word.split("-")
                if parts[-1].lower() in suffixes:
                    word = "-".join(parts[:-1])
            cleaned_words.append(word)
        return " ".join(cleaned_words).strip()

    def _rematch(description, results):
        best_symbol = ""
        best_score = 0
        for symbol, all_names in results:
            for name in all_names:
                score = similarity(description, name)
                if score > best_score:
                    best_score = score
                    best_symbol = symbol
        return best_symbol if best_score >= THRESHOLD else ""
    
    def _fetch(description, exact=True):
        try:
            q = f'protein_name:"{description}"' if exact else f'protein_name:{description}'
            query = f'{q} AND reviewed:true AND organism_id:{taxon_ref}'
            response = requests.get(base, params={
                "query":  query,
                "fields": "gene_names,protein_name",
                "format": "json",
                "size":   SIZE
            }, timeout=10)
            results = response.json().get("results", [])

            best_symbol = ""
            best_score = 0
            results_cache = []  # [(symbol, [noms])]

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

                results_cache.append((symbol, all_names))

                for name in all_names:
                    score = similarity(description, name)
                    if score > best_score:
                        best_score = score
                        best_symbol = symbol

            return best_symbol if best_score >= THRESHOLD else "", results_cache

        except Exception as e:
            print(f"  Erreur: {e}")
            return "", []


    def fetch_single(description):
        symbol, results_cache = _fetch(description, exact=True)
        clean = clean_description(description)

        if not symbol:
            if clean != description:
                symbol, results_cache = _fetch(clean, exact=True)

        if not symbol:
            symbol, results_cache = _fetch(clean, exact=False)

        if not symbol and results_cache:
            symbol = _rematch(clean, results_cache)
        
        time.sleep(default_wait)
        return symbol

    mask = (df["gene_symbol"] == "") & ~df["description"].str.startswith("uncharacterized")
    desc_unique = df.loc[mask, "description"].dropna().astype(str).unique()

    cache = {}
    cache_lock = threading.Lock()

    def process_desc(desc):
        symbol = fetch_single(desc)
        with cache_lock:
            cache[desc] = symbol
        return bool(symbol)

    width = len(str(len(desc_unique)))
    bar_format = f"{{desc}}: {{n:{width}d}}/{{total}} |{{bar:50}}|"
    with tqdm(total=len(desc_unique), desc="Searching for UniProt symbols", unit="description",
              bar_format=bar_format,
              ascii=" █", leave=False) as pbar:
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = {executor.submit(process_desc, desc): desc for desc in desc_unique}
            for future in as_completed(futures):
                pbar.update(1)
        pbar.n = pbar.total
        pbar.refresh()

    df.loc[mask, "gene_symbol"] = df.loc[mask, "description"].map(cache).fillna("")
    df["gene_symbol"] = df.apply(
        lambda r: r["gene_symbol"] if r["gene_symbol"] else r["gene_name"],
        axis=1
    )

    print(f"LOC gene symbols obtained")

    return df