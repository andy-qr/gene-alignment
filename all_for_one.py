import pandas as pd
import requests
import time
import re

df = pd.read_csv("S:/INSERM/Pipeline/Blasto_vs_fibro.txt", sep="\t")
df.drop(columns="gene_name", inplace=True)

df["gene_symbol"] = df.apply(
    lambda r:
    "" if r["gene_id"][:3] == "LOC" and r["gene_biotype"] == "protein_coding"
    else "uncharacterized " + r["gene_id"] if r["gene_id"][:3] == "LOC"
    else r["gene_id"],
    axis=1
)
df["ncbi_id"] = df.apply(
    lambda r:
    r["gene_id"].replace("LOC", "") if r["gene_id"][:3] == "LOC"
    else "",
    axis = 1
)
cols = df.columns.tolist()
cols.remove("ncbi_id")
cols.insert(1, "ncbi_id")
df = df[cols]

cols = df.columns.tolist()
cols.remove("gene_symbol")
cols.insert(2, "gene_symbol")
df = df[cols]

loc_symbols = df[df["gene_symbol"] == ""]["gene_id"]

API_KEY = "6aa784ef049697c8d1801ce03dd5b1344908"
BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

def fetch_batch(symbols):
    ids_numeriques = [s.replace("LOC", "") for s in symbols]
    summary_r = requests.get(f"{BASE}/esummary.fcgi", params={
        "db":      "gene",
        "id":      ",".join(ids_numeriques),
        "retmode": "json",
        "api_key": API_KEY
    })
    if summary_r.status_code != 200 or not summary_r.text.strip():
        print(f"  Erreur: {summary_r.status_code} — {summary_r.text[:200]}")
        return []
    batch_results = []
    for gene_id, info in summary_r.json().get("result", {}).items():
        if gene_id == "uids":
            continue
        batch_results.append({
            "gene_id":     "LOC" + gene_id,  # pour matcher df
            "symbol_ncbi": info.get("name"),
            "description": info.get("description")
        })
    return batch_results

results = []
batch_size = 100
total = len(loc_symbols)
for i in range(0, total, batch_size):
    batch = loc_symbols[i:i + batch_size]
    print(f"Batch {i // batch_size + 1}/{-(-total // batch_size)} — {len(batch)} symboles")
    results.extend(fetch_batch(batch))
    time.sleep(0.11)

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

df.to_csv("S:/INSERM/Pipeline/Blasto_vs_fibro_descriptions.txt", sep="\t", index=False)

TAXON_REF = "Homo sapiens"

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

def get_symbol_from_description(description, taxon=TAXON_REF):
    if not description or "uncharacterized" in description.lower():
        return ""

    # Détecter un symbol dans la description (mot en majuscules+chiffres)
    symbol_match = re.search(r'\b([A-Z][A-Z0-9]{1,9})\b', description)
    if symbol_match:
        candidate = symbol_match.group(1)
        search_r = requests.get(f"{BASE}/esearch.fcgi", params={
            "db":      "gene",
            "term":    f'{candidate}[Gene Name] AND "{taxon}"[Organism]',
            "retmax":  1,
            "retmode": "json",
            "api_key": API_KEY
        }, timeout=10)
        ids = search_r.json().get("esearchresult", {}).get("idlist", [])
        if ids:
            summary_r = requests.get(f"{BASE}/esummary.fcgi", params={
                "db":      "gene",
                "id":      ids[0],
                "retmode": "json",
                "api_key": API_KEY
            }, timeout=10)
            info = summary_r.json().get("result", {}).get(ids[0], {})
            symbol = info.get("name", "")
            if symbol and not symbol.startswith("LOC"):
                return symbol

    # Sinon chercher par description
    clean = clean_description(description)
    try:
        for term in [
            f'"{clean}"[Description] AND "{taxon}"[Organism]',
        ]:
            search_r = requests.get(f"{BASE}/esearch.fcgi", params={
                "db":      "gene",
                "term":    term,
                "retmax":  1,
                "retmode": "json",
                "api_key": API_KEY
            }, timeout=10)
            ids = search_r.json().get("esearchresult", {}).get("idlist", [])
            if ids:
                break

        if not ids:
            return ""

        summary_r = requests.get(f"{BASE}/esummary.fcgi", params={
            "db":      "gene",
            "id":      ids[0],
            "retmode": "json",
            "api_key": API_KEY
        }, timeout=10)
        info = summary_r.json().get("result", {}).get(ids[0], {})
        symbol = info.get("name", "")
        return "" if symbol.startswith("LOC") else symbol

    except Exception as e:
        print(f"  Erreur: {e}")
        return ""

mask = df["gene_symbol"].str.startswith("LOC") & ~df["description"].str.startswith("uncharacterized")
total = mask.sum()
desc_unique = df.loc[mask, "description"].dropna().unique()
print(f"{total} gènes dont {len(desc_unique)} descriptions uniques à résoudre")

cache = {}
for i, desc in enumerate(desc_unique):
    cache[desc] = get_symbol_from_description(desc)
    print(f"  {i+1}/{len(desc_unique)} | {desc[:40]:<40} → {cache[desc] or '(vide)'}")
    time.sleep(0.11)

    if (i + 1) % 100 == 0:
        df.loc[mask, "gene_symbol"] = df.loc[mask, "description"].map(cache)
        df["gene_symbol"] = df["gene_symbol"].fillna("")
        df.to_csv("S:/INSERM/Pipeline/Blasto_vs_fibro_symbols_temp.txt", sep="\t", index=False)

df.loc[mask, "gene_symbol"] = df.loc[mask, "description"].map(cache)
df["gene_symbol"] = df["gene_symbol"].fillna("")

df.to_csv("S:/INSERM/Pipeline/Blasto_vs_fibro_symbols.txt", sep="\t", index=False)

mask_missing = df["ncbi_id"] == ""
non_loc_symbols = df.loc[mask_missing, "gene_id"].tolist()

TAXON = "Columba livia"

def fetch_ids_batch(symbols):
    query = " OR ".join([f"{s}[Gene Name]" for s in symbols])
    query += f' AND "{TAXON}"[Organism]'

    search_r = requests.get(f"{BASE}/esearch.fcgi", params={
        "db":      "gene",
        "term":    query,
        "retmax":  len(symbols),
        "retmode": "json",
        "api_key": API_KEY
    }, timeout=10)

    ids = search_r.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        return {}

    summary_r = requests.get(f"{BASE}/esummary.fcgi", params={
        "db":      "gene",
        "id":      ",".join(ids),
        "retmode": "json",
        "api_key": API_KEY
    }, timeout=10)

    symbol_to_id = {}
    for gene_id, info in summary_r.json().get("result", {}).items():
        if gene_id == "uids":
            continue
        symbol_to_id[info.get("name", "")] = gene_id
    return symbol_to_id

symbol_to_id = {}
for i in range(0, len(non_loc_symbols), 100):
    batch = non_loc_symbols[i:i + 100]
    print(f"Batch {i // 100 + 1}/{-(-len(non_loc_symbols) // 100)} — {len(batch)} symboles")
    symbol_to_id.update(fetch_ids_batch(batch))
    time.sleep(0.2)

df.loc[mask_missing, "ncbi_id"] = df.loc[mask_missing, "gene_id"].map(symbol_to_id)
df.to_csv("S:/INSERM/Pipeline/Blasto_vs_fibro_symbols.txt", sep="\t", index=False)