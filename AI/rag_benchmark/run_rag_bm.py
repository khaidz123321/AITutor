"""
Script đánh giá RAG Embedding Model
So sánh 3 model: vietnamese-bi-encoder, multilingual-e5-large base, multilingual-e5-large finetuned
Metrics: Recall@K, MRR@K, NDCG@K
"""

import json
import os
import sys
import math
import unicodedata
import time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.config import settings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# ─── Config ────────────────────────────────────────────────────────────────────
BENCHMARK_FILE  = os.path.join(os.path.dirname(__file__), "data_bm_emb.json")
RESULTS_FILE    = os.path.join(os.path.dirname(__file__), "rag_benchmark_result.md")
VECTOR_DB_DIR   = os.path.join(settings.BASE_DIR, "data", "vector_db")
K_VALUES        = [1, 3, 5, 10]

MODELS = [
    {
        "name": "multilingual-e5-large (finetuned)",
        "model_path": os.path.join(settings.BASE_DIR, "multilingual-e5-large-finetuned"),
        "use_prefix": True,
        "use_cosine": True,
        "threshold_direction": "lower",
    },
]


# ─── Embedding classes ─────────────────────────────────────────────────────────

class E5Embeddings:
    def __init__(self, base: HuggingFaceEmbeddings):
        self.base = base

    def embed_documents(self, texts):
        return self.base.embed_documents(["passage: " + t for t in texts])

    def embed_query(self, text):
        return self.base.embed_query("query: " + text)


# ─── Normalize: bỏ dấu, lowercase, strip — dùng để so sánh mờ ────────────────
def normalize(text: str) -> str:
    """Bỏ dấu tiếng Việt, lowercase, strip để so sánh không phân biệt dấu."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()


# ─── Metrics ───────────────────────────────────────────────────────────────────
def is_match(retrieved_meta: dict, case: dict) -> bool:
    """
    Kiểm tra chunk có phải ground truth không.
    So sánh source chính xác, section dùng normalize để bỏ qua
    khác biệt dấu tiếng Việt giữa benchmark cũ và vector DB mới.
    """
    src = os.path.basename(retrieved_meta.get("source", "")).replace(".txt", "")
    sec = retrieved_meta.get("section", "")

    src_match = (src == case["relevant_source"])
    sec_match = (normalize(sec) == normalize(case["relevant_section"]))

    return src_match and sec_match


# ─── Đánh giá 1 model ──────────────────────────────────────────────────────────
def evaluate_model(model_cfg, benchmark_cases):
    print(f"\n{'='*60}")
    print(f"  Đang đánh giá: {model_cfg['name']}")
    print(f"{'='*60}")

    # Khởi tạo embeddings
    if model_cfg["use_prefix"]:
        base = HuggingFaceEmbeddings(
            model_name=model_cfg["model_path"],
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        embeddings = E5Embeddings(base)
    else:
        embeddings = HuggingFaceEmbeddings(
            model_name=model_cfg["model_path"],
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )

    # Metrics storage
    recall   = {k: [] for k in K_VALUES}
    ndcg     = {k: [] for k in K_VALUES}
    mrr_list = []
    errors   = 0

    for i, case in enumerate(benchmark_cases):
        subject = case["subject"]
        query   = case["query"]

        try:
            collection_meta = {"hnsw:space": "cosine"} if model_cfg["use_cosine"] else {}
            vector_db = Chroma(
                persist_directory=VECTOR_DB_DIR,
                embedding_function=embeddings,
                collection_name=f"subject_{subject}",
                collection_metadata=collection_meta
            )

            results = vector_db.similarity_search_with_score(query, k=max(K_VALUES))

            # Lấy danh sách metadata theo thứ tự
            retrieved_metas = [doc.metadata for doc, _ in results]

            # Tính match theo source (chính xác) + section (normalize)
            is_relevant = [is_match(m, case) for m in retrieved_metas]

            # MRR
            rr = 0.0
            for rank, rel in enumerate(is_relevant, 1):
                if rel:
                    rr = 1.0 / rank
                    break
            mrr_list.append(rr)

            # Recall@K và NDCG@K
            for k in K_VALUES:
                hit = any(is_relevant[:k])
                recall[k].append(1.0 if hit else 0.0)

                dcg = sum(
                    1.0 / math.log2(rank + 1)
                    for rank, rel in enumerate(is_relevant[:k], 1)
                    if rel
                )
                idcg = 1.0 / math.log2(2)
                ndcg[k].append(dcg / idcg if idcg > 0 else 0.0)

            status = "✅" if any(is_relevant[:5]) else "❌"
            print(f"  [{i+1:03d}] {status} MRR={rr:.2f} | {query[:50]}")

        except Exception as e:
            print(f"  [{i+1:03d}] ERROR: {str(e)[:60]}")
            errors += 1
            mrr_list.append(0.0)
            for k in K_VALUES:
                recall[k].append(0.0)
                ndcg[k].append(0.0)

    # Tổng hợp
    n = len(benchmark_cases)
    result = {
        "model": model_cfg["name"],
        "total_cases": n,
        "errors": errors,
        "MRR": sum(mrr_list) / n,
        "Recall": {k: sum(recall[k]) / n for k in K_VALUES},
        "NDCG":   {k: sum(ndcg[k]) / n   for k in K_VALUES},
    }

    print(f"\n  MRR:       {result['MRR']:.4f}")
    for k in K_VALUES:
        print(f"  Recall@{k}:  {result['Recall'][k]:.4f} | NDCG@{k}: {result['NDCG'][k]:.4f}")

    return result


# ─── Xuất báo cáo Markdown ─────────────────────────────────────────────────────
def write_report(all_results, benchmark_cases):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    from collections import Counter
    subjects = Counter(c["subject"] for c in benchmark_cases)

    lines = [
        "# Báo Cáo Benchmark — RAG Embedding Model",
        f"\n**Thời gian:** {now}",
        f"**Dataset:** {len(benchmark_cases)} cases",
        f"**Phân bổ:** " + ", ".join(f"{s}: {n}" for s, n in subjects.items()),
        "",
        "---",
        "",
        "## I. Kết Quả Tổng Quan — MRR",
        "",
        "| Model | MRR | Recall@1 | Recall@3 | Recall@5 | Recall@10 |",
        "|---|---|---|---|---|---|",
    ]

    for r in all_results:
        lines.append(
            f"| {r['model']} | **{r['MRR']:.4f}** | "
            f"{r['Recall'][1]:.4f} | {r['Recall'][3]:.4f} | "
            f"{r['Recall'][5]:.4f} | {r['Recall'][10]:.4f} |"
        )

    lines += [
        "",
        "## II. NDCG@K",
        "",
        "| Model | NDCG@1 | NDCG@3 | NDCG@5 | NDCG@10 |",
        "|---|---|---|---|---|",
    ]

    for r in all_results:
        lines.append(
            f"| {r['model']} | {r['NDCG'][1]:.4f} | {r['NDCG'][3]:.4f} | "
            f"{r['NDCG'][5]:.4f} | {r['NDCG'][10]:.4f} |"
        )

    best = max(all_results, key=lambda x: x["MRR"])
    lines += [
        "",
        "## III. Nhận Xét",
        "",
        f"**Model tốt nhất:** {best['model']} với MRR = {best['MRR']:.4f}",
        "",
    ]

    for r in all_results:
        diff = r["MRR"] - best["MRR"]
        if r["model"] != best["model"]:
            lines.append(f"- **{r['model']}** thấp hơn {abs(diff):.4f} so với model tốt nhất")

    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n📄 Báo cáo đã lưu tại: {RESULTS_FILE}")


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  RAG BENCHMARK — So sánh Embedding Models")
    print(f"  Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    with open(BENCHMARK_FILE, encoding="utf-8") as f:
        benchmark_cases = json.load(f)

    print(f"\n[INFO] Tổng cases: {len(benchmark_cases)}")
    print(f"[INFO] Đánh giá {len(MODELS)} models: {[m['name'] for m in MODELS]}")

    all_results = []
    for model_cfg in MODELS:
        result = evaluate_model(model_cfg, benchmark_cases)
        all_results.append(result)

    # In bảng tóm tắt
    print(f"\n{'='*60}")
    print("  TỔNG KẾT")
    print(f"{'='*60}")
    print(f"{'Model':<40} {'MRR':>8} {'R@1':>6} {'R@5':>6} {'R@10':>6}")
    print("-" * 70)
    for r in all_results:
        print(f"{r['model']:<40} {r['MRR']:>8.4f} {r['Recall'][1]:>6.4f} {r['Recall'][5]:>6.4f} {r['Recall'][10]:>6.4f}")

    # Lưu JSON
    results_json = os.path.join(os.path.dirname(__file__), "rag_benchmark_result.json")
    with open(results_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    write_report(all_results, benchmark_cases)


if __name__ == "__main__":
    main()