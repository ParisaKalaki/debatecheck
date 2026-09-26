"""
Step 3: Split abstracts into short evidence snippets, each with a unique ID.
Also cleans up HTML-style tags PubMed sometimes embeds in structured abstracts.
"""

import re
import uuid


def clean_text(text: str) -> str:
    """Strip HTML-style tags (e.g. <i>Background:</i>) from abstract text."""
    return re.sub(r"<[^>]+>", "", text).strip()


def chunk_abstract(paper: dict, max_sentences_per_chunk: int = 2) -> list[dict]:
    """
    Split one paper's abstract into short snippets.
    Each snippet gets a unique ID and carries the paper's metadata along with it.
    """
    abstract = clean_text(paper["abstract"])
    if not abstract:
        return []

    # naive sentence split — good enough for now, can improve later with nltk/spacy
    sentences = re.split(r"(?<=[.!?])\s+", abstract)

    snippets = []
    for i in range(0, len(sentences), max_sentences_per_chunk):
        chunk_text = " ".join(sentences[i:i + max_sentences_per_chunk]).strip()
        if not chunk_text:
            continue

        snippet_id = f"E-{paper['pmid']}-{i // max_sentences_per_chunk}"

        snippets.append({
            "id": snippet_id,
            "text": chunk_text,
            "pmid": paper["pmid"],
            "title": paper["title"],
            "pub_date": paper["pub_date"],
            # stance and quality metadata get filled in at later steps
            "stance": None,
            "study_design": None,
            "sample_size": None,
            "source_credibility": None,
        })

    return snippets


if __name__ == "__main__":
    from app.retrieval.pubmed_search import search_pubmed
    from app.retrieval.pubmed_fetch import fetch_abstracts

    test_claim = "intermittent fasting longevity"
    ids = search_pubmed(test_claim, retmax=2)
    papers = fetch_abstracts(ids)

    all_snippets = []
    for paper in papers:
        snippets = chunk_abstract(paper)
        all_snippets.extend(snippets)

    print(f"Generated {len(all_snippets)} snippets from {len(papers)} papers:\n")
    for s in all_snippets:
        print(f"[{s['id']}] {s['text']}\n")