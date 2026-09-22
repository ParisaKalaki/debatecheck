"""
Step 2: Fetch abstract text for a list of PubMed IDs.
"""

from Bio import Entrez
import os
from dotenv import load_dotenv

load_dotenv()

Entrez.email = os.getenv("NCBI_EMAIL", "your_email@example.com")


def fetch_abstracts(pmids: list[str]) -> list[dict]:
    """
    Given a list of PubMed IDs, fetch each paper's title, abstract, and
    publication date. Returns a list of dicts — one per paper.
    """
    handle = Entrez.efetch(db="pubmed", id=",".join(pmids), rettype="abstract", retmode="xml")
    records = Entrez.read(handle)
    handle.close()

    papers = []
    for article in records["PubmedArticle"]:
        medline = article["MedlineCitation"]
        article_data = medline["Article"]

        pmid = str(medline["PMID"])
        title = article_data.get("ArticleTitle", "")

        # abstract text can be split into multiple labeled sections
        abstract_parts = article_data.get("Abstract", {}).get("AbstractText", [])
        abstract_text = " ".join(str(part) for part in abstract_parts)

        pub_date = article_data.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
        year = pub_date.get("Year", pub_date.get("MedlineDate", "Unknown"))
        if not year:
            year = "Unknown"

                # Pull PubMed's own official study-design classification
        pub_types = article_data.get("PublicationTypeList", [])
        pub_types = [str(pt) for pt in pub_types]

        papers.append({
            "pmid": pmid,
            "title": str(title),
            "abstract": abstract_text,
            "pub_date": str(year),
            "pubmed_types": pub_types,   # <-- new field
        })

    return papers


if __name__ == "__main__":
    from pubmed_search import search_pubmed

    test_claim = "intermittent fasting longevity"
    ids = search_pubmed(test_claim, retmax=10)  # keep small for testing
    papers = fetch_abstracts(ids)

    for p in papers:
        print(f"\nPMID: {p['pmid']} ({p['pub_date']})")
        print(f"Title: {p['title']}")
        print(f"Abstract: {p['abstract'][:200]}...")  # first 200 chars only