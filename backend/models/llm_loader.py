import logging
import os
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from backend.config import LLM_MODEL_NAME, MODEL_CACHE_DIR, FORCE_CPU

logger = logging.getLogger(__name__)

# Global singletons — loaded once at startup
llm_model = None
llm_tokenizer = None


def load_llm():
    """Load the LLM and tokenizer once and cache globally."""
    global llm_model, llm_tokenizer

    cache_path = os.path.join(MODEL_CACHE_DIR, LLM_MODEL_NAME.replace("/", "_"))

    logger.info(f"Loading LLM: {LLM_MODEL_NAME}")
    logger.info(f"Model cache path: {cache_path}")
    logger.info(f"FORCE_CPU = {FORCE_CPU}")

    device_map = "cpu" if FORCE_CPU else "auto"

    llm_tokenizer = AutoTokenizer.from_pretrained(
        LLM_MODEL_NAME,
        cache_dir=cache_path,
        trust_remote_code=True,
    )
    llm_model = AutoModelForCausalLM.from_pretrained(
        LLM_MODEL_NAME,
        cache_dir=cache_path,
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


def generate_answer(system_prompt: str, user_prompt: str) -> str:
    """
    Generate a warm response using the LLM.

    Parameters:
        system_prompt: The system instruction (e.g., "You are Memory Twin AI...")
        user_prompt:  Full user message including memory context and question.

    Returns:
        Generated answer text.
    """
    model, tokenizer = get_llm()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
        )

    input_length = inputs["input_ids"].shape[1]
    response = tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
    return response.strip()
