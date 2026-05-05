from tqdm import tqdm
import requests
import mygene


def is_ensembl(df):
    sample = df["gene_id"].dropna().head(100)
    return sample.str.match(r"^ENS[A-Z]*G\d+").any()


def ensembl_to_loc(df):
    mg = mygene.MyGeneInfo()
    ensembl_ids = df["gene_id"].tolist()

    ensembl_to_ncbi = {}
    ensembl_to_biotype = {}
    ensembl_to_description = {}

    with tqdm(total=3, desc="Converting Ensembl to NCBI IDs",
              bar_format="{desc}: {n}/3 |{bar:30}|",
              ascii=" █", leave=False) as pbar:

        # Étape 1 : MyGene.info
        pbar.set_description("Querying MyGene.info")
        results = mg.querymany(
            ensembl_ids,
            scopes="ensembl.gene",
            fields="entrezgene,type_of_gene,name",
            species="all",
            returnall=True,
            verbose=False
        )
        for r in results.get("out", []):
            eid = r.get("query")
            ncbi = r.get("entrezgene")
            biotype = r.get("type_of_gene", "")
            name = r.get("name", "")
            if ncbi and eid not in ensembl_to_ncbi:
                ensembl_to_ncbi[eid] = f"LOC{int(ncbi)}"
            if biotype and eid not in ensembl_to_biotype:
                ensembl_to_biotype[eid] = biotype
            if name and eid not in ensembl_to_description:
                biotype = ensembl_to_biotype.get(eid, "")
                if biotype == "protein_coding" or biotype == "1":
                    ensembl_to_description[eid] = name
        pbar.update(1)

        # Étape 2 : fallback Ensembl lookup/id pour les non convertis
        pbar.set_description("Ensembl lookup fallback")
        not_converted = [eid for eid in ensembl_ids if eid not in ensembl_to_ncbi]

        for i in range(0, len(not_converted), 1000):
            batch = not_converted[i:i+1000]
            try:
                response = requests.post(
                    "https://rest.ensembl.org/lookup/id",
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    json={"ids": batch, "expand": 0},
                    timeout=30
                )
                if response.status_code == 200:
                    for eid, info in response.json().items():
                        if not info:
                            continue
                        biotype = info.get("biotype", "")
                        name = info.get("display_name", "")
                        if biotype and eid not in ensembl_to_biotype:
                            ensembl_to_biotype[eid] = biotype
                        if name and eid not in ensembl_to_description:
                            ensembl_to_description[eid] = name
            except Exception as e:
                print(f"  Ensembl lookup erreur: {e}")
        pbar.update(1)

        # Étape 3 : mapping
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

        df["gene_biotype"] = df["gene_id"].map(lambda x: ensembl_to_biotype.get(x, ""))
        df["description"] = df["gene_id"].map(lambda x: ensembl_to_description.get(x, ""))
        df["gene_id"] = df["gene_id"].map(lambda x: ensembl_to_ncbi.get(x, x))
        df["ncbi_id"] = df["gene_id"].apply(
            lambda x: x.replace("LOC", "") if x.startswith("LOC") else ""
        )
        if df["gene_name"].dropna().head(10).str.match(r"^ENS[A-Z]*G\d+").any():
            df["gene_name"] = df["gene_id"]

        df["gene_biotype"] = df["gene_biotype"].astype(str).map(
            lambda x: biotype_map.get(x, x)
        )
        pbar.update(1)

    matched = df["gene_id"].str.startswith("LOC").sum()
    print(f"✓ {matched}/{len(df)} IDs convertis, "
          f"{df['description'].astype(bool).sum()} descriptions, "
          f"{df['gene_biotype'].astype(bool).sum()} biotypes")

    return df