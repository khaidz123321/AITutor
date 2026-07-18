"""
Script finetune multilingual-e5-large với training data từ giáo trình PTIT
Chạy trên GPU server (RTX 4090)
"""

import json
import os
import torch
from sentence_transformers import SentenceTransformer, InputExample, losses, evaluation
from torch.utils.data import DataLoader
from datetime import datetime

# ─── Config ────────────────────────────────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH      = os.path.join(BASE_DIR, "models", "multilingual-e5-large")
OUTPUT_PATH     = os.path.join(BASE_DIR, "models", "multilingual-e5-large-finetuned")
DATA_PATH       = os.path.join(BASE_DIR, "training_data.json")

EPOCHS          = 3
BATCH_SIZE      = 16   # RTX 4090 24GB VRAM → batch 16 thoải mái
WARMUP_STEPS    = 100
EVAL_RATIO      = 0.1  # 10% data dùng để evaluate


# ─── Load data ─────────────────────────────────────────────────────────────────
def load_data(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"[DATA] Tổng pairs: {len(data)}")

    from collections import Counter
    subjects = Counter(d["subject"] for d in data)
    for subj, count in subjects.items():
        print(f"  {subj}: {count} pairs")

    return data


# ─── Tạo train/eval split ──────────────────────────────────────────────────────
def create_examples(data: list):
    import random
    random.seed(42)
    random.shuffle(data)

    split = int(len(data) * (1 - EVAL_RATIO))
    train_data = data[:split]
    eval_data  = data[split:]

    train_examples = [
        InputExample(texts=["query: " + d["query"], "passage: " + d["positive"]])
        for d in train_data
    ]

    # Evaluator dùng để theo dõi quality trong quá trình train
    eval_queries   = {str(i): "query: " + d["query"]    for i, d in enumerate(eval_data)}
    eval_corpus    = {str(i): "passage: " + d["positive"] for i, d in enumerate(eval_data)}
    eval_relevant  = {str(i): {str(i)}      for i in range(len(eval_data))}

    print(f"[DATA] Train: {len(train_examples)} | Eval: {len(eval_data)}")
    return train_examples, eval_queries, eval_corpus, eval_relevant


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  FINETUNE multilingual-e5-large")
    print(f"  Thời gian bắt đầu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Kiểm tra GPU
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n[GPU] Device: {device}")
    if device == "cuda":
        print(f"[GPU] {torch.cuda.get_device_name(0)}")
        print(f"[GPU] VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # Load model
    print(f"\n[MODEL] Loading từ {MODEL_PATH}...")
    model = SentenceTransformer(MODEL_PATH, device=device)
    print(f"[MODEL] Load xong!")

    # Load và chuẩn bị data
    print(f"\n[DATA] Loading {DATA_PATH}...")
    data = load_data(DATA_PATH)
    train_examples, eval_queries, eval_corpus, eval_relevant = create_examples(data)

    # DataLoader
    train_dataloader = DataLoader(
        train_examples,
        shuffle=True,
        batch_size=BATCH_SIZE
    )

    # Loss — MultipleNegativesRankingLoss tốt nhất cho RAG
    train_loss = losses.MultipleNegativesRankingLoss(model)

    # Evaluator
    evaluator = evaluation.InformationRetrievalEvaluator(
        queries=eval_queries,
        corpus=eval_corpus,
        relevant_docs=eval_relevant,
        name="ptit-eval"
    )

    # Tính warmup steps
    total_steps = len(train_dataloader) * EPOCHS
    warmup      = min(WARMUP_STEPS, total_steps // 10)

    print(f"\n[TRAIN] Bắt đầu finetune...")
    print(f"[TRAIN] Epochs: {EPOCHS}")
    print(f"[TRAIN] Batch size: {BATCH_SIZE}")
    print(f"[TRAIN] Total steps: {total_steps}")
    print(f"[TRAIN] Warmup steps: {warmup}")
    print(f"[TRAIN] Output: {OUTPUT_PATH}")
    print()

    # Finetune
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        evaluator=evaluator,
        epochs=EPOCHS,
        warmup_steps=warmup,
        output_path=OUTPUT_PATH,
        evaluation_steps=len(train_dataloader),  # evaluate sau mỗi epoch
        show_progress_bar=True,
        save_best_model=True  # chỉ lưu model tốt nhất
    )

    print(f"\n[DONE] Finetune xong!")
    print(f"[DONE] Model đã lưu tại: {OUTPUT_PATH}")
    print(f"[DONE] Thời gian kết thúc: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Kiểm tra kích thước model output
    total_size = sum(
        os.path.getsize(os.path.join(dirpath, f))
        for dirpath, _, files in os.walk(OUTPUT_PATH)
        for f in files
    )
    print(f"[DONE] Kích thước model: {total_size / 1e9:.2f} GB")


if __name__ == "__main__":
    main()