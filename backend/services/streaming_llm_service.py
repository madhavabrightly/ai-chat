"""Unified streaming LLM service — vLLM preferred, Transformers fallback."""
import asyncio
import logging
import time
from typing import AsyncIterator, Optional, List, Dict

logger = logging.getLogger(__name__)

# Config
NORMAL_MAX_NEW_TOKENS = 80
EXACT_MAX_NEW_TOKENS = 120
FIRST_TOKEN_TIMEOUT_S = 15.0


async def try_init_vllm() -> tuple:
    """Try to connect to vLLM server. Returns (available, client)."""
    try:
        import httpx
        from backend.config import VLLM_URL
        client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=2.0))
        # Quick health check
        try:
            resp = await client.get(f"{VLLM_URL}/models", timeout=2.0)
            if resp.status_code == 200:
                logger.info(f"vLLM available at {VLLM_URL}")
                return True, client
        except Exception:
            pass
        await client.aclose()
        return False, None
    except Exception as e:
        logger.info(f"vLLM init failed: {e}")
        return False, None


async def stream_vllm(
    messages: List[Dict],
    max_new_tokens: int = NORMAL_MAX_NEW_TOKENS,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Stream from vLLM server."""
    from backend.config import VLLM_URL, VLLM_MODEL_NAME
    from backend.core.service_container import ServiceContainer

    container = ServiceContainer.get()
    client = container.vllm_client
    if client is None:
        raise RuntimeError("vLLM client not initialized")

    payload = {
        "model": VLLM_MODEL_NAME,
        "messages": messages,
        "max_tokens": max_new_tokens,
        "temperature": temperature,
        "stream": True,
    }

    async with client.stream("POST", f"{VLLM_URL}/chat/completions", json=payload, timeout=60.0) as resp:
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    import json
                    obj = json.loads(data)
                    delta = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if delta:
                        yield delta
                except Exception:
                    pass


async def stream_transformers(
    messages: List[Dict],
    max_new_tokens: int = NORMAL_MAX_NEW_TOKENS,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Stream from local Transformers model using TextIteratorStreamer."""
    from backend.core.service_container import ServiceContainer
    from threading import Thread
    from transformers import TextIteratorStreamer

    container = ServiceContainer.get()
    model = container.llm_model
    tokenizer = container.llm_tokenizer

    if model is None or tokenizer is None:
        raise RuntimeError("LLM not loaded")

    # Apply chat template
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    gen_kwargs = dict(
        **inputs,
        max_new_tokens=max_new_tokens,
        temperature=max(temperature, 0.01),
        do_sample=temperature > 0,
        streamer=streamer,
        pad_token_id=tokenizer.eos_token_id,
    )

    thread = Thread(target=model.generate, kwargs=gen_kwargs)
    thread.start()

    loop = asyncio.get_event_loop()
    first_token = True
    t_start = time.time()

    while True:
        try:
            token = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: next(streamer, None)),
                timeout=FIRST_TOKEN_TIMEOUT_S if first_token else 30.0,
            )
        except asyncio.TimeoutError:
            logger.warning(f"Stream timeout (first_token={first_token})")
            break

        if token is None:
            break

        if first_token:
            first_token = False
            logger.debug(f"First token in {(time.time() - t_start)*1000:.1f}ms")

        yield token


async def stream_chat(
    messages: List[Dict],
    max_new_tokens: int = NORMAL_MAX_NEW_TOKENS,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    """Unified streaming interface — prefers vLLM, falls back to Transformers."""
    from backend.core.service_container import ServiceContainer

    container = ServiceContainer.get()

    if container.vllm_available and container.vllm_client is not None:
        try:
            async for token in stream_vllm(messages, max_new_tokens, temperature):
                yield token
            return
        except Exception as e:
            logger.warning(f"vLLM stream failed, falling back to Transformers: {e}")

    async for token in stream_transformers(messages, max_new_tokens, temperature):
        yield token
