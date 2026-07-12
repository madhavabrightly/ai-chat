"""
Memory Twin AI — Reranker Service (Qwen3-Reranker-0.6B)

CRITICAL FIX: Qwen3-Reranker is a CAUSAL LM (not SequenceClassification).
The old code used AutoModelForSequenceClassification which produced garbage.
This version uses the verified pattern from QwenLM/Qwen3-Embedding examples:
  - AutoModelForCausalLM with yes/no token logits
  - log_softmax([false, true])[:, 1].exp() -> calibrated probability in [0,1]
  - Official prefix/suffix tokens with the ChatML judge prompt
  - Min-max score normalization + relevance threshold (CRAG-inspired gating)

References:
  - QwenLM/Qwen3-Embedding examples/qwen3_reranker_transformers.py (L29-103)
  - QwenLM/Qwen3-Embedding README.md (L216-283)
"""
import logging
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

from backend.config import ENABLE_RERANKER
from backend.models.model_registry import model_exists_locally

logger = logging.getLogger(__name__)

reranker_model = None
reranker_tokenizer = None
_token_false_id = None
_token_true_id = None
_prefix_tokens = None
_suffix_tokens = None

# Verified prefix/suffix from QwenLM/Qwen3-Embedding examples (L36-L44)
_RERANK_PREFIX = (
    '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query '
    "and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n"
    '<|im_start|>user\n'
)
_RERANK_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n\n\n\n\n'

_DEFAULT_INSTRUCTION = "Given a user's question, retrieve the most relevant personal memory that answers it."


def load_reranker():
    """Load reranker model if available (as a causal LM, not sequence classifier)."""
    global reranker_model, reranker_tokenizer, _token_false_id, _token_true_id
    global _prefix_tokens, _suffix_tokens

    if not ENABLE_RERANKER:
        logger.info("Reranker disabled (ENABLE_RERANKER=false).")
        return None
    if not model_exists_locally("reranker"):
        logger.info("Reranker model not found locally. Using embedding-only retrieval.")
        return None
    try:
        from backend.models.model_registry import get_model_path
        path = get_model_path("reranker")
        logger.info(f"Loading reranker (causal LM) from: {path}")
        reranker_tokenizer = AutoTokenizer.from_pretrained(
            path, trust_remote_code=True, padding_side="left"
        )
        # MUST be AutoModelForCausalLM - Qwen3-Reranker outputs yes/no tokens
        reranker_model = AutoModelForCausalLM.from_pretrained(
            path,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True,
        ).eval()

        _token_false_id = reranker_tokenizer.convert_tokens_to_ids("no")
        _token_true_id = reranker_tokenizer.convert_tokens_to_ids("yes")
        _prefix_tokens = reranker_tokenizer.encode(_RERANK_PREFIX, add_special_tokens=False)
        _suffix_tokens = reranker_tokenizer.encode(_RERANK_SUFFIX, add_special_tokens=False)

        logger.info("Reranker loaded successfully (causal LM, yes/no logits).")
        return reranker_model
    except Exception as e:
        logger.warning(f"Reranker load failed: {e}. Using embedding-only retrieval.")
        reranker_model = None
        return None


def _format_pair(query: str, doc: str, instruction: str = _DEFAULT_INSTRUCTION) -> str:
    """Format a query-document pair with the official Qwen3-Reranker template."""
    return f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {doc}"


def _process_inputs(pairs: list, max_length: int = 2048):
    """Tokenize pairs with prefix/suffix tokens (verified pattern)."""
    out = reranker_tokenizer(
        pairs,
        padding=False,
        truncation="longest_first",
        return_attention_mask=False,
        max_length=max_length - len(_prefix_tokens) - len(_suffix_tokens),
    )
    for i, ele in enumerate(out["input_ids"]):
        out["input_ids"][i] = _prefix_tokens + ele + _suffix_tokens
    out = reranker_tokenizer.pad(out, padding=True, return_tensors="pt", max_length=max_length)
    for key in out:
        out[key] = out[key].to(reranker_model.device)
    return out


def _compute_logits(inputs) -> list:
    """
    Compute calibrated yes-probability scores in [0, 1].

    Pattern: take last-token logits, extract yes/no columns, log_softmax,
    exp -> P(yes). Verified from qwen3_reranker_transformers.py L86-103.
    """
    with torch.no_grad():
        batch_scores = reranker_model(**inputs).logits[:, -1, :]  # last token logits
        true_vector = batch_scores[:, _token_true_id]
        false_vector = batch_scores[:, _token_false_id]
        batch_scores = torch.stack([false_vector, true_vector], dim=1)
        batch_scores = torch.nn.functional.log_softmax(batch_scores, dim=1)
        scores = batch_scores[:, 1].exp().tolist()  # P(yes) in [0, 1]
    if not isinstance(scores, list):
        scores = [scores]
    return scores


def rerank(query: str, documents: list, min_score: float = 0.3) -> list:
    """
    Re-rank documents by relevance to the query.

    Returns documents sorted by calibrated relevance score (P(yes) in [0,1]).
    Drops documents below min_score (CRAG-inspired confidence gating), but
    always keeps at least one result. Falls back to original order on error.
    """
    if reranker_model is None or reranker_tokenizer is None:
        return documents

    try:
        pairs = [
            _format_pair(query, d.get("full_text", d.get("text", "")))
            for d in documents
        ]
        inputs = _process_inputs(pairs)
        scores = _compute_logits(inputs)

        # Min-max normalize to [0,1] for cross-query comparability
        smin, smax = min(scores), max(scores)
        rng = (smax - smin) or 1.0
        norm = [(s - smin) / rng for s in scores]

        for i, doc in enumerate(documents):
            doc["relevance_score"] = round(norm[i], 4)
            doc["raw_reranker_score"] = round(float(scores[i]), 4)

        documents.sort(key=lambda d: d.get("relevance_score", 0), reverse=True)

        # CRAG-inspired: drop low-relevance docs, but keep at least one
        filtered = [d for d in documents if d["relevance_score"] >= min_score]
        return filtered if filtered else documents[:1]
    except Exception as e:
        logger.warning(f"Reranker inference failed: {e}")
        return documents
