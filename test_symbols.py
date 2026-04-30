import requests
import random
import pandas as pd
import time
import os
from difflib import SequenceMatcher

os.chdir(os.path.dirname(os.path.abspath(__file__)))

UNIPROT_URL = "https://rest.uniprot.org/uniprotkb/search"
N = 50
WAIT = 0.5
THRESHOLD = 0.35
SIZE = 5
SEED = 112

def similarity(a, b):
    a = a.lower().replace("-", " ")
    b = b.lower().replace("-", " ")
    return SequenceMatcher(None, a, b).ratio()

def fetch_single(description):
    symbol, score, matched_name, results_cache = _fetch(description, exact=True)
    
    if not symbol:
        clean = clean_description(description)
        if clean != description:
            print(f"  [clean]   '{description[:40]}' → '{clean[:40]}'")
            symbol, score, matched_name, results_cache = _fetch(clean, exact=True)

    if not symbol:
        symbol, score, matched_name, results_cache = _fetch(clean, exact=False)

    if not symbol and results_cache:
        symbol, score, matched_name = _rematch(clean, results_cache)

    return symbol, score, matched_name

def clean_description(description):
    suffixes = ["associated","like", "related"]
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
    best_name = ""
    for symbol, all_names in results:
        for name in all_names:
            score = similarity(description, name)
            if score > best_score:
                best_score = score
                best_symbol = symbol
                best_name = name
    return best_symbol if best_score >= THRESHOLD else "", best_score, best_name

def _fetch(description, exact=True):
    try:
        q = f'protein_name:"{description}"' if exact else f'protein_name:{description}'
        query = f'{q} AND reviewed:true AND organism_id:9606'
        response = requests.get(UNIPROT_URL, params={
            "query":  query,
            "fields": "gene_names,protein_name",
            "format": "json",
            "size":   SIZE
        }, timeout=10)
        results = response.json().get("results", [])

        best_symbol = ""
        best_score = 0
        best_name = ""
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
                    best_name = name

        return best_symbol if best_score >= THRESHOLD else "", best_score, best_name, results_cache

    except Exception as e:
        print(f"  Erreur: {e}")
        return "", 0, "", []

FILE = "blasto_vs_fibro_descriptions"
df = pd.read_csv(FILE + ".txt", sep="\t", dtype={"ncbi_id": str})

# Filtrer les LOC protein_coding avec description
mask = (
    df["gene_symbol"].str.startswith("LOC") &
    ~df["description"].str.startswith("uncharacterized") &
    df["description"].notna()
)
candidates = df.loc[mask, ["gene_id", "description"]].drop_duplicates(subset="description")

sample = candidates.sample(min(N, len(candidates)), random_state=SEED)

print(f"\n{'Description':<50} {'Symbol':<12} {'Score':<6} {'Nom UniProt'}")
print("-" * 110)

results = []
for _, row in sample.iterrows():
    desc = row["description"]
    symbol, score, matched_name = fetch_single(desc)
    print(f"{desc[:50]:<50} {symbol:<12} {score:.2f}   {matched_name[:40]}")
    results.append({
        "gene_id":      row["gene_id"],
        "description":  desc,
        "symbol":       symbol,
        "score":        round(score, 3),
        "matched_name": matched_name
    })
    time.sleep(WAIT)

df_results = pd.DataFrame(results)
df_results.to_csv("test_symbols_results.txt", sep="\t", index=False)
print(f"\n✓ {df_results['symbol'].astype(bool).sum()}/{N} matchés — résultats dans test_symbols_results.txt")
print(f"Ajuste THRESHOLD (actuellement {THRESHOLD}) et SIZE (actuellement {SIZE}) selon les résultats")