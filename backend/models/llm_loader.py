import logging
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from backend.config import LLM_MODEL_NAME, FORCE_CPU, MAX_NEW_TOKENS
from backend.models.model_registry import get_model_path

logger = logging.getLogger(__name__)

llm_model = None
llm_tokenizer = None


def load_llm():
    """Load the LLM once at startup from the registry active path."""
    global llm_model, llm_tokenizer

    # Try single-registry path first, then fallback to config MODEL_CACHE_DIR
    try:
        model_path = get_model_path("llm")
    except KeyError:
        # Load from HF hub using model ID (will use existing cache)
        model_path = None

    logger.info(f"Loading LLM: {LLM_MODEL_NAME}")
    if model_path and os.path.isdir(model_path):
        logger.info(f"Loading from local path: {model_path}")
    else:
        logger.info(f"Loading from HuggingFace hub (cached in config path)")
        from backend.config import MODEL_CACHE_DIR
        model_path = None
        os.environ["TRANSFORMERS_CACHE"] = MODEL_CACHE_DIR

    device_map = "cpu" if FORCE_CPU else "auto"

    llm_tokenizer = AutoTokenizer.from_pretrained(
        LLM_MODEL_NAME,
        cache_dir=model_path,
        trust_remote_code=True,
    )
    llm_model = AutoModelForCausalLM.from_pretrained(
        LLM_MODEL_NAME,
        cache_dir=model_path,
        torch_dtype="auto",
        device_map=device_map,
        trust_remote_code=True,
    )

    if FORCE_CPU:
        llm_model = llm_model.to("cpu")

    logger.info("LLM loaded successfully.")
    return llm_model, llm_tokenizer


def get_llm():
    """Return the loaded LLM and tokenizer singletons."""
    if llm_model is None or llm_tokenizer is None:
        raise RuntimeError("LLM not loaded. Call load_llm() first.")
    return llm_model, llm_tokenizer


def generate_answer(system_prompt: str, history: list) -> str:
    """
    Generate a response using the LLM with full conversation context.
    """
    model, tokenizer = get_llm()

    messages = [{"role": "system", "content": system_prompt}] + history

    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            temperature=0.8,
            top_p=0.92,
            top_k=40,
            do_sample=True,
            repetition_penalty=1.1,
        )

    input_length = inputs["input_ids"].shape[1]
    response = tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
    return response.strip()
