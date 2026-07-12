"""
Memory Twin AI — LLM Loader (Qwen2.5-7B-Instruct)

Upgraded with verified best practices from QwenLM/Qwen3 official docs:
  - Correct sampling params: temperature=0.7, top_p=0.8, repetition_penalty=1.05
  - bf16 dtype + SDPA/Flash-Attention-2 attention
  - KV cache enabled (use_cache=True)
  - pad_token_id / eos_token_id set (prevents generation warnings/bugs)
  - Optional 4-bit quantization (bitsandbytes nf4) for low-memory devices
  - Streaming generation via TextIteratorStreamer
  - Retries with exponential backoff for transient OOM/Runtime errors
  - Circuit breaker to stop hammering a failing model
  - Sliding-window conversation memory (token-budgeted)

References:
  - QwenLM/Qwen3 docs/source/quantization/gptq.md (L77-117) — verified params
  - QwenLM/Qwen3 examples/demo/web_demo.py (L75-107) — streaming pattern
"""
import logging
import os
import time
import threading
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

from backend.config import LLM_MODEL_NAME, FORCE_CPU, MAX_NEW_TOKENS, ENABLE_4BIT_QUANT
from backend.models.model_registry import get_model_path

logger = logging.getLogger(__name__)

llm_model = None
llm_tokenizer = None


# Circuit breaker — stops repeated calls to a failing model
class _CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 60.0):
        self.failures = 0
        self.last_failure = 0.0
        self.threshold = failure_threshold
        self.reset_timeout = reset_timeout

    @property
    def is_open(self) -> bool:
        if self.failures >= self.threshold:
            if time.time() - self.last_failure > self.reset_timeout:
                # half-open: allow one trial
                self.failures = 0
                return False
            return True
        return False

    def record_failure(self):
        self.failures += 1
        self.last_failure = time.time()

    def record_success(self):
        self.failures = 0


_LLM_BREAKER = _CircuitBreaker()


def _build_quantization_config():
    """Build bitsandbytes 4-bit config if enabled and available."""
    if not ENABLE_4BIT_QUANT:
        return None
    try:
        from transformers import BitsAndBytesConfig
        cfg = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,  # nested quantization → more memory savings
        )
        logger.info("4-bit quantization enabled (bitsandbytes nf4).")
        return cfg
    except Exception as e:
        logger.warning(f"4-bit quantization requested but unavailable: {e}. Falling back to full precision.")
        return None


def _resolve_attention_impl() -> str:
    """Pick the best available attention implementation."""
    try:
        from transformers.utils import is_flash_attn_2_available
        if is_flash_attn_2_available():
            return "flash_attention_2"
    except Exception:
        pass
    # SDPA is always available in torch >= 2.0 and faster than eager
    return "sdpa"


def load_llm():
    """Load the LLM once at startup from the registry active path."""
    global llm_model, llm_tokenizer

    # Try single-registry path first, then fallback to config MODEL_CACHE_DIR
    try:
        model_path = get_model_path("llm")
    except KeyError:
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
    attn_impl = _resolve_attention_impl()
    quant_cfg = _build_quantization_config()
    dtype = torch.bfloat16 if not FORCE_CPU else torch.float32

    logger.info(f"Attention implementation: {attn_impl} | dtype: {dtype} | quant: {bool(quant_cfg)}")

    llm_tokenizer = AutoTokenizer.from_pretrained(
        LLM_MODEL_NAME,
        cache_dir=model_path,
        trust_remote_code=True,
        padding_side="left",  # required for correct generation with left-padding
    )
    # Ensure a pad token exists (Qwen uses eos as pad)
    if llm_tokenizer.pad_token is None:
        llm_tokenizer.pad_token = llm_tokenizer.eos_token

    load_kwargs = dict(
        cache_dir=model_path,
        torch_dtype=dtype,
        device_map=device_map,
        trust_remote_code=True,
        attn_implementation=attn_impl,
        use_cache=True,  # KV cache on
    )
    if quant_cfg is not None:
        load_kwargs["quantization_config"] = quant_cfg

    llm_model = AutoModelForCausalLM.from_pretrained(LLM_MODEL_NAME, **load_kwargs)

    if FORCE_CPU:
        llm_model = llm_model.to("cpu")

    llm_model.eval()
    logger.info("LLM loaded successfully.")
    return llm_model, llm_tokenizer


def get_llm():
    """Return the loaded LLM and tokenizer singletons."""
    if llm_model is None or llm_tokenizer is None:
        raise RuntimeError("LLM not loaded. Call load_llm() first.")
    return llm_model, llm_tokenizer


def llm_circuit_open() -> bool:
    """Check if the LLM circuit breaker is open (too many recent failures)."""
    return _LLM_BREAKER.is_open


# Verified Qwen2.5-7B-Instruct sampling params (from QwenLM/Qwen3 docs)
_GEN_DEFAULTS = dict(
    max_new_tokens=MAX_NEW_TOKENS,
    temperature=0.7,
    top_p=0.8,
    top_k=20,
    do_sample=True,
    repetition_penalty=1.05,
    use_cache=True,
)


def generate_answer(system_prompt: str, history: list, **overrides) -> str:
    """
    Generate a response using the LLM with full conversation context.

    Uses verified Qwen2.5 sampling params (temperature=0.7, top_p=0.8,
    repetition_penalty=1.05) and retries with exponential backoff on
    transient errors. Protected by a circuit breaker.
    """
    if _LLM_BREAKER.is_open:
        raise RuntimeError("LLM circuit breaker open — too many recent failures.")

    model, tokenizer = get_llm()

    # Sliding-window conversation memory (token-budgeted)
    from backend.services.conversation_memory import trim_history
    history = trim_history(history, tokenizer)

    messages = [{"role": "system", "content": system_prompt}] + history
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    gen_kwargs = {**_GEN_DEFAULTS, **overrides}
    gen_kwargs.update(
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

    # Retry with exponential backoff on transient errors
    last_err = None
    for attempt in range(3):
        try:
            with torch.no_grad():
                outputs = model.generate(**inputs, **gen_kwargs)
            input_length = inputs["input_ids"].shape[1]
            response = tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True)
            _LLM_BREAKER.record_success()
            return response.strip()
        except (torch.cuda.OutOfMemoryError, RuntimeError) as e:
            last_err = e
            logger.warning(f"LLM generate attempt {attempt+1} failed: {e}")
            # Clear cache and retry after backoff
            try:
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            time.sleep(min(2 ** attempt, 4))
        except Exception as e:
            last_err = e
            break

    _LLM_BREAKER.record_failure()
    raise RuntimeError(f"LLM generation failed after retries: {last_err}")


def generate_answer_stream(system_prompt: str, history: list, **overrides):
    """
    Stream tokens as they are generated (generator yielding str chunks).

    Uses TextIteratorStreamer + background thread (official Qwen demo pattern).
    """
    if _LLM_BREAKER.is_open:
        raise RuntimeError("LLM circuit breaker open — too many recent failures.")

    model, tokenizer = get_llm()

    from backend.services.conversation_memory import trim_history
    history = trim_history(history, tokenizer)

    messages = [{"role": "system", "content": system_prompt}] + history
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer([text], return_tensors="pt").to(model.device)

    streamer = TextIteratorStreamer(
        tokenizer=tokenizer, skip_prompt=True, timeout=60.0, skip_special_tokens=True
    )
    gen_kwargs = {**_GEN_DEFAULTS, **overrides}
    gen_kwargs.update(
        streamer=streamer,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )

    thread = threading.Thread(target=model.generate, kwargs=gen_kwargs)
    thread.start()

    try:
        for new_text in streamer:
            yield new_text
        _LLM_BREAKER.record_success()
    except Exception:
        _LLM_BREAKER.record_failure()
        raise
    finally:
        thread.join()
