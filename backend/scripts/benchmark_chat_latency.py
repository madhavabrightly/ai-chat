"""
Benchmark chat latency — measures p50/p95 for embedding, retrieval, first token, full response.

Usage:
    python backend/scripts/benchmark_chat_latency.py
    python backend/scripts/benchmark_chat_latency.py --queries 10
"""
import argparse
import json
import os
import sys
import time
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

# Test queries
CASUAL_QUERIES = ["hi", "hello", "how are you?", "thanks", "good morning", "hey", "ok", "bye"]
NORMAL_QUERIES = [
    "Tell me about your childhood",
    "What advice would you give me?",
    "What made you proud?",
    "Tell me a funny story",
    "What do you believe about life?",
    "Tell me about your family",
    "How was your first love?",
    "What is your career story?",
    "Tell me about kindness",
    "What do you remember about Grandma?",
    "What made you happy?",
    "Tell me about learning to ride a bike",
    "What was the promotion about?",
    "What did your grandfather say?",
    "Tell me a joke",
    "What was the bus fare story?",
    "How did you learn to ride?",
    "What happened at the library?",
    "What advice under the stars?",
    "Tell me about the parrot joke",
]
EXACT_QUERIES = [
    "what did she say exactly about the stars?",
    "quote the grandfather's advice exactly",
    "what did Grandma say about the table?",
    "exact words from the bus fare story",
    "what did the mentor say exactly?",
]
REPEATED_QUERIES = ["hi", "hello", "Tell me about your childhood", "What advice would you give me?"]


def measure(time_fn, label, results):
    t0 = time.perf_counter()
    try:
        time_fn()
        elapsed = (time.perf_counter() - t0) * 1000
        results.append(elapsed)
        status = "✓"
    except Exception as e:
        elapsed = 0
        status = f"✗ {e}"
    print(f"  {status} {label}: {elapsed:.1f}ms")
    return elapsed


def run_benchmark(queries, label, fn):
    print(f"\n=== {label} ({len(queries)} queries) ===")
    times = []
    for q in queries:
        measure(lambda q=q: fn(q), q[:40], times)
    if times:
        times.sort()
        p50 = times[len(times) // 2]
        p95 = times[int(len(times) * 0.95)]
        print(f"  ── p50: {p50:.1f}ms  p95: {p95:.1f}ms")
    return times


def main():
    parser = argparse.ArgumentParser(description="Benchmark chat latency")
    parser.add_argument("--queries", type=int, default=5, help="Queries per category")
    args = parser.parse_args()

    print("=" * 50)
    print("Memory Twin AI — Latency Benchmark")
    print("=" * 50)
    print(f"PyTorch: {__import__('torch').__version__}")
    print(f"CUDA: {__import__('torch').cuda.is_available()}")
    if __import__('torch').cuda.is_available():
        print(f"Device: {__import__('torch').cuda.get_device_name(0)}")

    # Import backend modules
    from backend.models.embedding_loader import load_embedder, embed_query
    from backend.models.llm_loader import load_llm, generate_answer
    from backend.rag.memory_store import build_vector_store
    from backend.rag.retriever import retrieve_memories
    from backend.config import SYSTEM_PROMPT

    # Load models once
    print("\n[setup] Loading embedding model...")
    load_embedder()
    print("[setup] Loading LLM...")
    load_llm()
    print("[setup] Building ChromaDB...")
    build_vector_store()

    # Warmup
    print("[setup] Warmup...")
    embed_query("warmup")
    generate_answer(SYSTEM_PROMPT, [{"role": "user", "content": "Say OK."}])

    all_results = {}

    # 1. Embedding latency
    emb_times = []
    print(f"\n=== Embedding ({len(NORMAL_QUERIES)} queries) ===")
    for q in NORMAL_QUERIES[:args.queries]:
        t0 = time.perf_counter()
        embed_query(q)
        emb_times.append((time.perf_counter() - t0) * 1000)
    emb_times.sort()
    all_results["embedding_ms"] = {
        "p50": round(emb_times[len(emb_times)//2], 1),
        "p95": round(emb_times[int(len(emb_times)*0.95)], 1),
        "samples": len(emb_times),
    }
    print(f"  p50: {all_results['embedding_ms']['p50']}ms  p95: {all_results['embedding_ms']['p95']}ms")

    # 2. Retrieval latency
    ret_times = []
    print(f"\n=== Retrieval ({len(NORMAL_QUERIES)} queries) ===")
    for q in NORMAL_QUERIES[:args.queries]:
        t0 = time.perf_counter()
        retrieve_memories(q)
        ret_times.append((time.perf_counter() - t0) * 1000)
    ret_times.sort()
    all_results["retrieval_ms"] = {
        "p50": round(ret_times[len(ret_times)//2], 1),
        "p95": round(ret_times[int(len(ret_times)*0.95)], 1),
        "samples": len(ret_times),
    }
    print(f"  p50: {all_results['retrieval_ms']['p50']}ms  p95: {all_results['retrieval_ms']['p95']}ms")

    # 3. Full chat latency (first few tokens)
    chat_times = []
    short_queries = NORMAL_QUERIES[:min(args.queries, 5)]
    print(f"\n=== Full chat ({len(short_queries)} queries) ===")
    query_count = 0
    for q in short_queries:
        retrieved = retrieve_memories(q)
        ctx = "\n\n".join([f"[Mem {i+1}]\n{m['full_text']}" for i, m in enumerate(retrieved[:3])])
        user_msg = f"Relevant memories:\n{ctx}\n\nUser: {q}\n\nRespond warmly and briefly."
        t0 = time.perf_counter()
        answer = generate_answer(SYSTEM_PROMPT, [{"role": "user", "content": user_msg}])
        elapsed = (time.perf_counter() - t0) * 1000
        chat_times.append(elapsed)
        query_count += 1
        print(f"  ✓ {q[:40]:40s} {elapsed:7.1f}ms  ({len(answer)} chars)")

    chat_times.sort()
    all_results["full_chat_ms"] = {
        "p50": round(chat_times[len(chat_times)//2], 1),
        "p95": round(chat_times[int(len(chat_times)*0.95)], 1),
        "samples": len(chat_times),
    }
    print(f"  ── p50: {all_results['full_chat_ms']['p50']}ms  p95: {all_results['full_chat_ms']['p95']}ms")

    # 4. Cache hit simulation (repeated query)
    cache_times = []
    print(f"\n=== Cache hit (repeated) ===")
    q = "Tell me about your childhood"
    for i in range(3):
        t0 = time.perf_counter()
        retrieve_memories(q)
        cache_times.append((time.perf_counter() - t0) * 1000)
    cache_times.sort()
    all_results["cache_retrieval_ms"] = {
        "p50": round(cache_times[len(cache_times)//2], 1),
        "p95": round(cache_times[-1], 1),
        "samples": len(cache_times),
    }
    print(f"  p50: {all_results['cache_retrieval_ms']['p50']}ms  p95: {all_results['cache_retrieval_ms']['p95']}ms")

    # Print summary
    print("\n" + "=" * 50)
    print("BENCHMARK RESULTS")
    print("=" * 50)
    for k, v in all_results.items():
        print(f"  {k:25s}  p50={v['p50']:>7.1f}ms  p95={v['p95']:>7.1f}ms  (n={v['samples']})")

    print("\n" + "=" * 50)
    print("Done.")
    print("=" * 50)

    # Save results
    output = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": all_results}
    os.makedirs("benchmark_results", exist_ok=True)
    path = f"benchmark_results/latency_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved: {path}")


if __name__ == "__main__":
    main()
