from tqdm import tqdm
import requests
import time
import os
import re

os.chdir(os.path.dirname(os.path.abspath(__file__)))
from api import get_next_key, wait


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
            return ""
        symbol_match = re.search(r'\b([A-Z][A-Z0-9]{1,9})\b', description)
        if symbol_match:
            candidate = symbol_match.group(1)
            search_r = requests.get(f"{base}/esearch.fcgi", params={
                "db":      "gene",
                "term":    f'{candidate}[Gene Name] AND "{taxon}"[Organism]',
                "retmax":  1,
                "retmode": "json",
                "api_key": get_next_key()
            }, timeout=10)
            ids = search_r.json().get("esearchresult", {}).get("idlist", [])
            if ids:
                summary_r = requests.get(f"{base}/esummary.fcgi", params={
                    "db":      "gene",
                    "id":      ids[0],
                    "retmode": "json",
                    "api_key": get_next_key()
                }, timeout=10)
                info = summary_r.json().get("result", {}).get(ids[0], {})
                symbol = info.get("name", "")
                if symbol and not symbol.startswith("LOC"):
                    return symbol
        clean = clean_description(description)
        try:
            search_r = requests.get(f"{base}/esearch.fcgi", params={
                "db":      "gene",
                "term":    f'"{clean}"[Gene Description] AND "{taxon}"[Organism]',
                "retmax":  1,
                "retmode": "json",
                "api_key": get_next_key()
            }, timeout=10)
            ids = search_r.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return ""
            summary_r = requests.get(f"{base}/esummary.fcgi", params={
                "db":      "gene",
                "id":      ids[0],
                "retmode": "json",
                "api_key": get_next_key()
            }, timeout=10)
            info = summary_r.json().get("result", {}).get(ids[0], {})
            symbol = info.get("name", "")
            return "" if symbol.startswith("LOC") else symbol
        except Exception as e:
            tqdm.write(f"  Erreur: {e}")
            return ""

    mask = df["gene_symbol"].str.startswith("LOC") & ~df["description"].str.startswith("uncharacterized")
    desc_unique = df.loc[mask, "description"].dropna().unique()

    cache = {}
    with tqdm(total=len(desc_unique), desc="Searching for NCBI symbols", unit="description",
            bar_format="{desc}: {n}/{total} |{bar}|",
            ascii="░▒▓█", leave=False) as pbar:
        for i, desc in enumerate(desc_unique):
            cache[desc] = get_symbol_from_description(desc)
            pbar.update(1)
            time.sleep(wait)
            if (i + 1) % 100 == 0:
                df.loc[mask, "gene_symbol"] = df.loc[mask, "description"].map(cache)
                df["gene_symbol"] = df["gene_symbol"].fillna("")
                df.to_csv("S:/INSERM/Pipeline/blasto_vs_fibro_symbols_temp.txt", sep="\t", index=False)

    tqdm.write("\r" + " " * 80 + "\r", end="")
    print("✓ Symbols résolus via descriptions")

    df.loc[mask, "gene_symbol"] = df.loc[mask, "description"].map(cache)
    df["gene_symbol"] = df.apply(
        lambda r:
        r["gene_symbol"] if r["gene_symbol"] else r["gene_id"],
        axis = 1
    )
    
    return df