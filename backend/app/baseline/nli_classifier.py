"""
Traditional baseline: keyword retrieval + pretrained NLI classifier + majority vote.

No LLM agents, no prompting — just a pretrained entailment model deciding
whether each evidence snippet supports, contradicts, or is neutral toward
the claim. This is the "traditional" side of the traditional-vs-agentic
comparison.
"""

from transformers import pipeline

# Zero-shot NLI pipeline — treats stance as entailment/contradiction/neutral
nli_classifier = pipeline(
    "zero-shot-classification",
    model="cross-encoder/nli-deberta-v3-xsmall"
)


def classify_stance_nli(claim: str, snippet_text: str) -> str:
    """
    Uses a pretrained NLI model to classify one snippet's stance toward
    the claim, without any LLM prompting — just entailment scoring.
    """
    candidate_labels = ["supports the claim", "contradicts the claim", "unrelated to the claim"]

    result = nli_classifier(snippet_text, candidate_labels, hypothesis_template=f"This evidence {{}} that {claim}.")

    top_label = result["labels"][0]

    if "supports" in top_label:
        return "support"
    elif "contradicts" in top_label:
        return "contradict"
    else:
        return "neutral"


def majority_vote_verdict(snippets_with_stance: list[dict]) -> dict:
    """
    Simple majority vote across all snippets — NO quality weighting.
    This is intentionally naive: it just counts support vs contradict,
    treating every snippet equally regardless of study design or
    sample size. This is the key limitation the agentic system improves on.
    """
    support_count = sum(1 for s in snippets_with_stance if s["stance"] == "support")
    contradict_count = sum(1 for s in snippets_with_stance if s["stance"] == "contradict")
    neutral_count = sum(1 for s in snippets_with_stance if s["stance"] == "neutral")

    total_relevant = support_count + contradict_count

    if total_relevant == 0:
        verdict = "insufficient evidence"
    elif support_count > contradict_count:
        verdict = "leans true"
    elif contradict_count > support_count:
        verdict = "leans false"
    else:
        verdict = "mixed"

    return {
        "verdict": verdict,
        "support_count": support_count,
        "contradict_count": contradict_count,
        "neutral_count": neutral_count,
    }


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).resolve().parents[1] / "retrieval"))
    
    from evidence_pipeline import get_evidence_for_claim

    claim = "vitamin D supplements prevent respiratory infections"

    # Reuse the same retrieval pipeline, but ignore its LLM-based stance —
    # we classify stance ourselves with the NLI model instead
    evidence = get_evidence_for_claim(claim, retmax=10)

    print(f"Classifying {len(evidence)} snippets with NLI baseline...\n")

    baseline_results = []
    for e in evidence:
        nli_stance = classify_stance_nli(claim, e.text)
        baseline_results.append({"id": e.id, "stance": nli_stance, "text": e.text})
        print(f"[{e.id}] NLI stance={nli_stance}")

    verdict = majority_vote_verdict(baseline_results)
    print(f"\n--- BASELINE VERDICT ---")
    print(verdict)