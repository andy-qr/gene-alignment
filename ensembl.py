from tqdm import tqdm
import requests
import mygene


def is_ensembl(df):
    sample = df["gene_id"].dropna().head(100)
    return sample.str.match(r"^ENS[A-Z]*G\d+").any()


def ensembl_to_loc(df):
    mg = mygene.MyGeneInfo()
    
    ensembl_mask = df["gene_id"].str.match(r"^ENS[A-Z]*G\d+").values
    ensembl_ids = df.loc[ensembl_mask, "gene_id"].tolist()

    ensembl_to_ncbi = {}
    ensembl_to_biotype = {}
    ensembl_to_symbol = {}
    ensembl_to_description = {}

    with tqdm(total=3, desc="Converting Ensembl to NCBI IDs",
              bar_format="{desc}: {n}/3 |{bar:30}|",
              ascii=" █", leave=False) as pbar:

        pbar.set_description("Querying MyGene.info")
        results = mg.querymany(
            ensembl_ids,
            scopes="ensembl.gene",
            fields="entrezgene,type_of_gene,symbol,name",
            species="all",
            returnall=True,
            verbose=False
        )
        for r in results.get("out", []):
            eid = r.get("query")
            ncbi = r.get("entrezgene")
            biotype = r.get("type_of_gene", "")
            symbol = r.get("symbol", "")
            name = r.get("name", "")
            if ncbi and eid not in ensembl_to_ncbi:
                ensembl_to_ncbi[eid] = f"LOC{int(ncbi)}"
            if biotype and eid not in ensembl_to_biotype:
                ensembl_to_biotype[eid] = biotype
            if symbol and eid not in ensembl_to_symbol:
                ensembl_to_symbol[eid] = symbol.upper()
            if name and eid not in ensembl_to_description:
                ensembl_to_description[eid] = name
        pbar.update(1)

        pbar.set_description("Ensembl lookup fallback")
        not_converted = [eid for eid in ensembl_ids if eid not in ensembl_to_ncbi]

        for i in range(0, len(not_converted), 1000):
            batch = not_converted[i:i+1000]
            for attempt in range(3):
                try:
                    response = requests.post(
                        "https://rest.ensembl.org/lookup/id",
                        headers={"Content-Type": "application/json", "Accept": "application/json"},
                        json={"ids": batch, "expand": 0},
                        timeout=60
                    )
                    if response.status_code == 200:
                        for eid, info in response.json().items():
                            if not info:
                                continue
                            biotype = info.get("biotype", "")
                            display = info.get("display_name", "")
                            if biotype and eid not in ensembl_to_biotype:
                                ensembl_to_biotype[eid] = biotype
                            if display and eid not in ensembl_to_symbol:
                                ensembl_to_symbol[eid] = display.upper()
                    break
                except Exception:
                    if attempt == 2:
                        print(f"  Ensembl lookup indisponible pour {len(batch)} gènes")
                    else:
                        import time
                        time.sleep(2)
        pbar.update(1)

        pbar.set_description("Mapping IDs")

        biotype_map = {
            "protein-coding": "protein_coding",
            "0": "unknown",
            "1": "protein_coding",
            "2": "pseudo",
            "3": "rRNA",
            "4": "tRNA",
            "5": "snRNA",
            "6": "snoRNA",
            "7": "microRNA",
            "8": "ncRNA",
            "9": "scRNA",
            "10": "other"
        }

        if "gene_symbol" not in df.columns:
            df["gene_symbol"] = ""
        if "description" not in df.columns:
            df["description"] = ""
        if "gene_biotype" not in df.columns:
            df["gene_biotype"] = ""

        df.loc[ensembl_mask, "gene_biotype"] = df.loc[ensembl_mask, "gene_id"].map(
            lambda x: ensembl_to_biotype.get(x, "")
        )
        df.loc[ensembl_mask, "gene_symbol"] = df.loc[ensembl_mask, "gene_id"].map(
            lambda x: ensembl_to_symbol.get(x, "") if ensembl_to_biotype.get(x, "") == "protein_coding" else ""
        )
        df.loc[ensembl_mask, "description"] = df.loc[ensembl_mask, "gene_id"].map(
            lambda x: ensembl_to_description.get(x, "") if ensembl_to_biotype.get(x, "") == "protein_coding" else ""
        )
        df.loc[ensembl_mask, "ncbi_id"] = df.loc[ensembl_mask, "gene_id"].map(
            lambda x: ensembl_to_ncbi.get(x, "").replace("LOC", "") if ensembl_to_ncbi.get(x, "") else ""
        )
        df.loc[ensembl_mask, "gene_id"] = df.loc[ensembl_mask, "gene_id"].map(
            lambda x: ensembl_to_ncbi.get(x, x)
        )
        # Remplacer gene_name par LOC+ncbi si gene_name est encore un ID Ensembl et gene_id a été converti
        ensembl_name_mask = ensembl_mask & df["gene_id"].str.startswith("LOC") & df["gene_name"].str.match(r"^ENS[A-Z]*G\d+")
        df.loc[ensembl_name_mask, "gene_name"] = df.loc[ensembl_name_mask, "gene_id"]

        df["gene_biotype"] = df["gene_biotype"].astype(str).map(
            lambda x: biotype_map.get(x, x)
        )
        pbar.update(1)

    matched = df.loc[ensembl_mask, "gene_id"].str.startswith("LOC").sum()
    print(f"✓ {matched}/{len(ensembl_ids)} IDs convertis, "
          f"{df.loc[ensembl_mask, 'gene_symbol'].astype(bool).sum()} symbols, "
          f"{df.loc[ensembl_mask, 'description'].astype(bool).sum()} descriptions")

    return df