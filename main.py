from taxon import taxon_id
import pandas as pd


TAXON_REF = "Homo sapiens"
NCBI = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UNIPROT = "https://rest.uniprot.org/uniprotkb/search"

def run(TAXON, FILE):
    from api import num_threads

    df = pd.read_csv(FILE, sep="\t")
    df.drop(columns="gene_name", inplace=True)

    cols = df.columns.tolist()
    missing = [c for c in ["gene_id", "gene_biotype"] if c not in cols]
    if missing:
        raise ValueError(f"Colonnes manquantes : {', '.join(missing)}")

    print(f"Using {num_threads} threads")
    print(f"Source file obtained")

    from descriptions import fill_descriptions
    df = fill_descriptions(df, NCBI)

    from symbols import fill_symbols
    df = fill_symbols(df, UNIPROT, taxon_id(TAXON_REF)[0])

    from all_ids import fill_all_ids
    df = fill_all_ids(df, NCBI, TAXON)


    df = df[["gene_id", "ncbi_id", "gene_symbol", "gene_biotype", "description", "baseMean", "log2FoldChange", "lfcSE", "stat", "pvalue", "padj"]]

    df.to_csv(FILE+"_final.txt", sep="\t", index=False)