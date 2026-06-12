# Báo Cáo Benchmark — Diagnose Accuracy

**Thời gian chạy:** 2026-06-07 20:57:49
**Model:** `qwen/qwen3-32b`
**Dataset:** 57 cases — Giải tích 1 - PTIT

---

## I. Kết Quả Tổng Quan

| Chỉ số | Giá trị | Ngưỡng | Đánh giá |
|---|---|---|---|
| Accuracy tổng | **93.0%** (53/57) | ≥ 80% | ✅ ĐẠT |
| Latency trung bình | 6.86s | ≤ 1.5s | ❌ |
| Latency p50 | 4.86s | — | — |
| Latency p90 | 17.43s | — | — |
| Cases lỗi | 0 | 0 | ✅ |

---

## II. F1 Theo Từng Class

| Label | F1 | Precision | Recall | Support | Đánh giá |
|---|---|---|---|---|---|
| STEP_CORRECT | 1.00 | 1.00 | 1.00 | 9 | ✅ |
| PROBLEM_COMPLETED | 1.00 | 1.00 | 1.00 | 4 | ✅ |
| INCOMPLETE | 0.71 | 0.62 | 0.83 | 6 | ❌ Cần cải thiện |
| CALCULATION_ERROR | 1.00 | 1.00 | 1.00 | 1 | ✅ |
| CONCEPTUAL_ERROR | 0.92 | 1.00 | 0.86 | 14 | ✅ |
| VAGUE_OR_OFFTOPIC | 1.00 | 1.00 | 1.00 | 7 | ✅ |
| REQUEST_HINT | 0.80 | 0.80 | 0.80 | 5 | ✅ |
| REQUEST_THEORY | 1.00 | 1.00 | 1.00 | 7 | ✅ |
| REVEAL_ANSWER | 1.00 | 1.00 | 1.00 | 4 | ✅ |

---

## III. Cases Phân Loại Sai

### ❌ `TC_CE_004`
- **True label:** `CONCEPTUAL_ERROR`
- **Predicted:** `INCOMPLETE`
- **Input:** *"Em chỉ cần tìm giới hạn a bằng cách giải phương trình a = (5+a²)/2a là xong"*
- **Mô tả:** CONCEPTUAL_ERROR: Học sinh chỉ tìm điểm bất động mà thiếu bước chứng minh dãy đơn điệu và bị chặn — sai phương pháp hội tụ.

### ❌ `TC_RH_005`
- **True label:** `REQUEST_HINT`
- **Predicted:** `INCOMPLETE`
- **Input:** *"Mình nghĩ là max X = 2 nhưng không chắc, bạn cho biết đúng không rồi gợi ý tiếp đi"*
- **Mô tả:** Học sinh phân vân không dám đoán

### ❌ `TC_EDGE_003`
- **True label:** `INCOMPLETE`
- **Predicted:** `REQUEST_HINT`
- **Input:** *"Em không biết"*
- **Mô tả:** EDGE CASE: Câu quá mơ hồ không có lịch sử

### ❌ `TC_EDGE_005`
- **True label:** `CONCEPTUAL_ERROR`
- **Predicted:** `INCOMPLETE`
- **Input:** *"sup X = 2 đúng không, và min X = 1 vì 1 là số nhỏ nhất gần X"*
- **Mô tả:** EDGE CASE: Đúng một phần sai một phần nguy hiểm

---

## IV. Confusion Matrix

```
                    STEP_COR  PROBLEM_  INCOMPLE  CALCULAT  CONCEPTU  VAGUE_OR  REQUEST_  REQUEST_  REVEAL_A
STEP_CORRECT               9         0         0         0         0         0         0         0         0
PROBLEM_COMPLETED          0         4         0         0         0         0         0         0         0
INCOMPLETE                 0         0         5         0         0         0         1         0         0
CALCULATION_ERROR          0         0         0         1         0         0         0         0         0
CONCEPTUAL_ERROR           0         0         2         0        12         0         0         0         0
VAGUE_OR_OFFTOPIC          0         0         0         0         0         7         0         0         0
REQUEST_HINT               0         0         1         0         0         0         4         0         0
REQUEST_THEORY             0         0         0         0         0         0         0         7         0
REVEAL_ANSWER              0         0         0         0         0         0         0         0         4
```

---

## V. Khuyến Nghị

- **INCOMPLETE** có F1 = 0.71 < 0.75 — Cần thêm rule phân biệt class này trong diagnose prompt.
- **Latency 6.86s > 1.5s** — Cân nhắc giảm max_tokens hoặc đổi sang model nhỏ hơn.