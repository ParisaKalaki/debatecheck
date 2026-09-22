"""
Step 1: Search PubMed for a health claim and get back paper IDs.
"""

from Bio import Entrez
import os
from dotenv import load_dotenv

load_dotenv()

Entrez.email = os.getenv("NCBI_EMAIL", "your_email@example.com")


def search_pubmed(query: str, retmax: int = 10) -> list[str]:
    """
    Search PubMed for a query string, return a list of PubMed IDs (PMIDs).
    """
    handle = Entrez.esearch(db="pubmed", term=query, retmax=retmax)
    record = Entrez.read(handle)
    handle.close()
    return record["IdList"]


if __name__ == "__main__":
    # quick manual test
    test_claim = "intermittent fasting longevity"
    ids = search_pubmed(test_claim)
    print(f"Found {len(ids)} papers for '{test_claim}':")
    print(ids)