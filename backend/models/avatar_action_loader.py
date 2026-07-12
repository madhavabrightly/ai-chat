"""Optional ModelScope Qwen3-0.6B loader for structured avatar actions."""
import logging
import threading

import torch

from backend.config import AVATAR_ACTION_DEVICE, ENABLE_AVATAR_ACTION_MODEL
from backend.models.model_registry import get_model_path, model_is_loadable

logger = logging.getLogger(__name__)

_model = None
_tokenizer = None
_load_lock = threading.Lock()
_generation_lock = threading.Lock()


def load_avatar_action_model():
    """Load the local action model without downloading during app startup."""
    global _model, _tokenizer

    if not ENABLE_AVATAR_ACTION_MODEL:
        logger.info("Avatar action model disabled; instant rule director remains active.")
        return None, None
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    with _load_lock:
        if _model is not None and _tokenizer is not None:
            return _model, _tokenizer
        if not model_is_loadable("avatar_action"):
            logger.info("Qwen3 avatar action model is not local; using instant rule director.")
            return None, None

        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_path = get_model_path("avatar_action")
        use_gpu = torch.cuda.is_available() and AVATAR_ACTION_DEVICE != "cpu"
        supports_bf16 = use_gpu and getattr(torch.cuda, "is_bf16_supported", lambda: False)()
        dtype = torch.bfloat16 if supports_bf16 else (torch.float16 if use_gpu else torch.float32)
        device_map = "auto" if use_gpu else "cpu"
        logger.info("Loading ModelScope avatar action model from %s", model_path)

        _tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            local_files_only=True,
            trust_remote_code=True,
        )
        load_kwargs = {
            "local_files_only": True,
            "trust_remote_code": True,
            "torch_dtype": dtype,
            "device_map": device_map,
            "attn_implementation": "sdpa",
            "use_cache": True,
        }
        try:
            _model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)
        except (RuntimeError, torch.cuda.OutOfMemoryError) as exc:
            if not use_gpu:
                raise
            logger.warning("Avatar action GPU load failed; retrying on CPU: %s", exc)
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            load_kwargs.update(torch_dtype=torch.float32, device_map="cpu")
            _model = AutoModelForCausalLM.from_pretrained(model_path, **load_kwargs)
        _model.eval()
        logger.info("Qwen3 avatar action director loaded.")
        return _model, _tokenizer


def get_avatar_action_model():
    return _model, _tokenizer


def avatar_action_model_ready() -> bool:
    return _model is not None and _tokenizer is not None


def generate_avatar_action_json(messages: list[dict], max_new_tokens: int = 96) -> str:
    """Generate one compact non-thinking JSON response."""
    model, tokenizer = get_avatar_action_model()
    if model is None or tokenizer is None:
        raise RuntimeError("Avatar action model is not loaded")

    with _generation_lock:
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
        inputs = tokenizer([prompt], return_tensors="pt")
        device = next(model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}
        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                use_cache=True,
                pad_token_id=tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        input_length = inputs["input_ids"].shape[1]
        return tokenizer.decode(outputs[0][input_length:], skip_special_tokens=True).strip()
