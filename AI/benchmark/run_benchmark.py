"""
Benchmark Script — Diagnose Accuracy
Đánh giá độ chính xác phân loại của Agent 1 (Llama/Groq)
Chạy: python run_benchmark.py
"""

import json
import time
import os
import sys
from datetime import datetime
from collections import defaultdict
from dotenv import load_dotenv

# Fix Unicode trên Windows terminal
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ─── Setup path để import từ project ────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
AI_DIR      = os.path.dirname(SCRIPT_DIR)          # thư mục AI/
sys.path.insert(0, AI_DIR)
load_dotenv(os.path.join(AI_DIR, ".env"))

from langchain_core.messages import HumanMessage, AIMessage
from engine.ai_engine import AItutor

# ─── Config ───────────────────────────────────────────────────────────
DATASET_PATH    = os.path.join(SCRIPT_DIR, "benchmark_dataset.json")
RESULTS_PATH    = os.path.join(SCRIPT_DIR, "benchmark_result.md")
CHECKPOINT_PATH = os.path.join(SCRIPT_DIR, "benchmark_checkpoint.json")
DELAY_BETWEEN   = 1.5   # giây chờ giữa mỗi call (tránh rate limit Groq)

# Model benchmark: dùng model production để benchmark chuẩn xác
from core.config import settings
BENCHMARK_MODEL = os.getenv("BENCHMARK_MODEL", settings.DIAGNOSE_MODEL_NAME)

ALL_LABELS = [
    "STEP_CORRECT", "PROBLEM_COMPLETED", "INCOMPLETE",
    "CALCULATION_ERROR", "CONCEPTUAL_ERROR", "VAGUE_OR_OFFTOPIC",
    "REQUEST_HINT", "REQUEST_THEORY", "REVEAL_ANSWER"
]

# ─── Utilities ─────────────────────────────────────────────────────────────
def _save_checkpoint(results):
    """Lưu tiến độ ra file json."""
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump({"results": results}, f, ensure_ascii=False, indent=2)


def build_chat_history(raw_history: list):
    """Convert list dict sang LangChain message format."""
    messages = []
    for msg in raw_history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "ai":
            messages.append(AIMessage(content=msg["content"]))
    return messages


def compute_f1(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def compute_metrics(results: list):
    """Tính accuracy tổng và F1 từng class."""
    total   = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total if total > 0 else 0.0

    # Confusion matrix data
    tp_map = defaultdict(int)
    fp_map = defaultdict(int)
    fn_map = defaultdict(int)

    for r in results:
        true  = r["true_label"]
        pred  = r["predicted_label"]
        if pred == true:
            tp_map[true] += 1
        else:
            fp_map[pred] += 1
            fn_map[true] += 1

    per_class = {}
    for label in ALL_LABELS:
        p, r, f1 = compute_f1(tp_map[label], fp_map[label], fn_map[label])
        support  = sum(1 for res in results if res["true_label"] == label)
        per_class[label] = {
            "precision": p, "recall": r, "f1": f1, "support": support,
            "tp": tp_map[label], "fp": fp_map[label], "fn": fn_map[label]
        }

    return accuracy, per_class


def build_confusion_matrix(results: list):
    """Trả về dict confusion_matrix[true][pred] = count."""
    matrix = defaultdict(lambda: defaultdict(int))
    for r in results:
        matrix[r["true_label"]][r["predicted_label"]] += 1
    return matrix


def render_confusion_matrix(matrix) -> str:
    labels = ALL_LABELS
    short  = {l: l[:8] for l in labels}
    header = " " * 20 + "  ".join(f"{short[l]:>8}" for l in labels)
    lines  = [header]
    for true in labels:
        row = f"{true:<20}" + "  ".join(
            f"{matrix[true][pred]:>8}" for pred in labels
        )
        lines.append(row)
    return "\n".join(lines)


# ─── Main benchmark ────────────────────────────────────────────────────────
def run_benchmark():
    print("=" * 60)
    print("  AITUTOR BENCHMARK — Diagnose Accuracy")
    print(f"  Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Load dataset
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    cases           = dataset["cases"]
    question_context = json.dumps(dataset["question_context"], ensure_ascii=False)
    total           = len(cases)

    print(f"[INFO] Tổng số cases: {total}")
    print(f"[INFO] Model: {BENCHMARK_MODEL}")
    print(f"[INFO] Delay giữa calls: {DELAY_BETWEEN}s")

    # Kiểm tra checkpoint có sẵn không
    checkpoint_results = []
    done_ids = set()
    if os.path.exists(CHECKPOINT_PATH):
        with open(CHECKPOINT_PATH, "r", encoding="utf-8") as f:
            checkpoint_data = json.load(f)
        checkpoint_results = checkpoint_data.get("results", [])
        done_ids = {r["id"] for r in checkpoint_results}
        print(f"[RESUME] Tìm thấy checkpoint: đã hoàn thành {len(done_ids)}/{total} cases.")
        print(f"[RESUME] Tiếp tục từ case chưa chạy...\n")
    else:
        print(f"[INFO] Không có checkpoint, bắt đầu từ đầu.\n")

    # Khởi tạo AI với model benchmark riêng
    ai = AItutor(benchmark_model=BENCHMARK_MODEL)

    results      = list(checkpoint_results)   # bắt đầu từ checkpoint
    failed_cases = []
    latencies    = []

    for idx, case in enumerate(cases):
        case_id     = case["id"]
        true_label  = case["label"]
        student_msg = case["student_input"]
        history     = build_chat_history(case.get("chat_history", []))

        # Bỏ qua nếu đã có trong checkpoint
        if case_id in done_ids:
            continue

        print(f"[{idx+1:02d}/{total}] {case_id} | Expected: {true_label:<20}", end=" ", flush=True)

        try:
            t0 = time.time()
            result = ai.diagnose(
                user_message=student_msg,
                chat_history=history,
                json_context=question_context
            )
            elapsed = time.time() - t0
            latencies.append(elapsed)

            predicted = result.cognitive_state.value if hasattr(result.cognitive_state, 'value') else str(result.cognitive_state)
            emotion   = result.emotion_state.value if hasattr(result.emotion_state, 'value') else str(result.emotion_state)
            correct   = (predicted == true_label)

            status = "✅" if correct else "❌"
            print(f"→ Got: {predicted:<20} {status} ({elapsed:.2f}s)")

            results.append({
                "id": case_id,
                "true_label": true_label,
                "predicted_label": predicted,
                "emotion_predicted": emotion,
                "correct": correct,
                "latency": elapsed,
                "student_input": student_msg,
                "description": case.get("description", "")
            })

            # Lưu checkpoint sau mỗi case thành công
            _save_checkpoint(results)

        except Exception as e:
            err_str = str(e)
            print(f"-> ERROR: {err_str[:80]}")

            # Nếu lỗi rate limit: dừng lại, in hướng dẫn resume
            if "rate_limit_exceeded" in err_str or "429" in err_str:
                print(f"\n[RATE LIMIT] Hết quota token! Checkpoint đã được lưu.")
                print(f"[RATE LIMIT] Chạy lại sau khi quota reset: python benchmark/run_benchmark.py")
                print(f"[RATE LIMIT] Script sẽ tự động tiếp tục từ case chưa chạy.\n")
                # Vẫn ghi báo cáo dựa trên những gì đã chạy được
                break

            failed_cases.append({"id": case_id, "error": err_str})
            results.append({
                "id": case_id,
                "true_label": true_label,
                "predicted_label": "ERROR",
                "emotion_predicted": "NEUTRAL",
                "correct": False,
                "latency": 0,
                "student_input": student_msg,
                "description": case.get("description", "")
            })
            _save_checkpoint(results)

        time.sleep(DELAY_BETWEEN)

    # Tính metrics
    print("\n" + "=" * 60)
    print("  TỔNG HỢP KẾT QUẢ")
    print("=" * 60)

    accuracy, per_class = compute_metrics(results)
    matrix              = build_confusion_matrix(results)

    correct_count = sum(1 for r in results if r["correct"])
    avg_latency   = sum(latencies) / len(latencies) if latencies else 0
    p50 = sorted(latencies)[int(len(latencies) * 0.5)] if latencies else 0
    p90 = sorted(latencies)[int(len(latencies) * 0.9)] if latencies else 0

    print(f"\n  Accuracy tổng   : {accuracy*100:.1f}% ({correct_count}/{len(results)})")
    print(f"  Latency trung bình: {avg_latency:.2f}s")
    print(f"  p50              : {p50:.2f}s")
    print(f"  p90              : {p90:.2f}s")
    print(f"{'DAT' if accuracy >= 0.8 else 'CHUA DAT'} nguong ky vong (>= 80%)")

    print("\nF1 theo tung class:")
    print(f"  {'Label':<25} {'F1':>6} {'Precision':>10} {'Recall':>8} {'Support':>8}")
    print("  " + "-" * 63)
    for label in ALL_LABELS:
        m   = per_class[label]
        flag = "OK" if m["f1"] >= 0.75 else ("NO DATA" if m["support"] == 0 else "FAIL")
        print(f"  {label:<25} {m['f1']:>6.2f} {m['precision']:>10.2f} {m['recall']:>8.2f} {m['support']:>7}  {flag}")

    # Xóa checkpoint khi hoàn thành toàn bộ
    all_done = len(results) >= total
    if all_done and os.path.exists(CHECKPOINT_PATH):
        os.remove(CHECKPOINT_PATH)
        print(f"\n[CHECKPOINT] Đã xóa checkpoint (hoàn thành toàn bộ {total} cases).")

    # Các case sai
    wrong_cases = [r for r in results if not r["correct"]]
    if wrong_cases:
        print(f"\n❌ Cases phân loại sai ({len(wrong_cases)}):")
        for r in wrong_cases:
            print(f"  [{r['id']}] True={r['true_label']} | Pred={r['predicted_label']}")
            print(f"    Input: \"{r['student_input'][:60]}...\"" if len(r['student_input']) > 60 else f"    Input: \"{r['student_input']}\"")

    # Ghi báo cáo Markdown
    write_markdown_report(results, accuracy, per_class, matrix, avg_latency, p50, p90, failed_cases, dataset)
    print(f"\n📄 Báo cáo đã lưu tại: {RESULTS_PATH}")
    print("=" * 60)


def write_markdown_report(results, accuracy, per_class, matrix, avg_latency, p50, p90, failed_cases, dataset):
    correct_count = sum(1 for r in results if r["correct"])
    wrong_cases   = [r for r in results if not r["correct"]]
    pass_flag     = "✅ ĐẠT" if accuracy >= 0.8 else "❌ CHƯA ĐẠT"
    now           = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    model_name    = BENCHMARK_MODEL

    lines = [
        "# Báo Cáo Benchmark — Diagnose Accuracy",
        f"\n**Thời gian chạy:** {now}",
        f"**Model:** `{model_name}`",
        f"**Dataset:** {len(results)} cases — {dataset['metadata']['subject']}",
        "",
        "---",
        "",
        "## I. Kết Quả Tổng Quan",
        "",
        f"| Chỉ số | Giá trị | Ngưỡng | Đánh giá |",
        f"|---|---|---|---|",
        f"| Accuracy tổng | **{accuracy*100:.1f}%** ({correct_count}/{len(results)}) | ≥ 80% | {pass_flag} |",
        f"| Latency trung bình | {avg_latency:.2f}s | ≤ 1.5s | {'✅' if avg_latency <= 1.5 else '❌'} |",
        f"| Latency p50 | {p50:.2f}s | — | — |",
        f"| Latency p90 | {p90:.2f}s | — | — |",
        f"| Cases lỗi | {len(failed_cases)} | 0 | {'✅' if not failed_cases else '❌'} |",
        "",
        "---",
        "",
        "## II. F1 Theo Từng Class",
        "",
        "| Label | F1 | Precision | Recall | Support | Đánh giá |",
        "|---|---|---|---|---|---|",
    ]

    for label in ALL_LABELS:
        m    = per_class[label]
        flag = "✅" if m["f1"] >= 0.75 else ("⚠️ Không có data" if m["support"] == 0 else "❌ Cần cải thiện")
        lines.append(f"| {label} | {m['f1']:.2f} | {m['precision']:.2f} | {m['recall']:.2f} | {m['support']} | {flag} |")

    lines += [
        "",
        "---",
        "",
        "## III. Cases Phân Loại Sai",
        "",
    ]

    if wrong_cases:
        for r in wrong_cases:
            lines += [
                f"### ❌ `{r['id']}`",
                f"- **True label:** `{r['true_label']}`",
                f"- **Predicted:** `{r['predicted_label']}`",
                f"- **Input:** *\"{r['student_input']}\"*",
                f"- **Mô tả:** {r['description']}",
                "",
            ]
    else:
        lines.append("Không có case nào sai! 🎉\n")

    lines += [
        "---",
        "",
        "## IV. Confusion Matrix",
        "",
        "```",
        render_confusion_matrix(matrix),
        "```",
        "",
        "---",
        "",
        "## V. Khuyến Nghị",
        "",
    ]

    # Tự động sinh khuyến nghị dựa trên kết quả
    recommendations = []
    if accuracy < 0.8:
        recommendations.append("- **Accuracy thấp hơn ngưỡng 80%** — Cần bổ sung thêm ví dụ phân biệt vào prompt của Agent 1.")

    for label in ALL_LABELS:
        m = per_class[label]
        if m["support"] > 0 and m["f1"] < 0.75:
            recommendations.append(f"- **{label}** có F1 = {m['f1']:.2f} < 0.75 — Cần thêm rule phân biệt class này trong diagnose prompt.")

    if avg_latency > 1.5:
        recommendations.append(f"- **Latency {avg_latency:.2f}s > 1.5s** — Cân nhắc giảm max_tokens hoặc đổi sang model nhỏ hơn.")

    if not recommendations:
        recommendations.append("- Tất cả chỉ số đạt ngưỡng. Hệ thống sẵn sàng để chạy benchmark Window Size (Giai đoạn 2).")

    lines += recommendations

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    run_benchmark()
