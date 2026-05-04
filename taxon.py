import requests

def taxon_id(taxon):
    response = requests.get(
        "https://rest.uniprot.org/taxonomy/search",
        params={
            "query": taxon,
            "format": "json",
            "size": 3
        },
        timeout=10
    )
    results = response.json().get("results", [])
    if not results:
        return False
    
    # Vérifier que le premier résultat correspond exactement
    first = results[0]
    scientific = first.get("scientificName", "").lower()
    common = first.get("commonName", "").lower()
    
    if taxon.lower() == scientific or taxon.lower() == common:
        return first.get("scientificName"), first.get("taxonId")
    
    return False

def taxon_suggestions(taxon):
    response = requests.get(
        "https://rest.uniprot.org/taxonomy/search",
        params={"query": taxon, "format": "json", "size": 3},
        timeout=10
    )
    results = response.json().get("results", [])
    return [r.get("scientificName") for r in results if r.get("scientificName")]