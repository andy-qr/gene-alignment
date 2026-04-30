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
        print("Unexistant taxon - Check if you've made any mistake")
        return False
    return results[0].get('taxonId')