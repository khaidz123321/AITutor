import json

def _parse_llm_json(raw):
    try:
        return [json.loads(raw)]
    except Exception:
        return [{'realNumbers': {'definition': '...'}}]

def test_logic():
    # Giả lập JSON lỗi của DeepSeek-R1 giống hệt trong log của bạn
    raw_output_stage1 = """{
      "realNumbers": {
        "definition": "Real numbers are numbers that can be represented on a number line and include rational and irrational numbers.",
        "properties": [
          {
            "property": "Density",
            "description": "Between any two real numbers, there exists another real number."
          }
        ]
      }
    }"""
    
    batch_data = _parse_llm_json(raw_output_stage1)
    print("Dữ liệu bóc tách được (giả lập):", batch_data)
    
    # Đoạn code kiểm tra logic mới vừa được thêm vào exercises.py
    is_valid = False
    if isinstance(batch_data, dict) and batch_data.get("questions"):
        is_valid = True
    elif isinstance(batch_data, list):
        for item in batch_data:
            item_str = str(item).lower()
            if "question" in item_str or "id" in item_str or "topic" in item_str:
                is_valid = True
                break
                
    print("Biến is_valid:", is_valid)
    
    if not is_valid:
        print("=> THÀNH CÔNG: Đã phát hiện JSON lỗi không chứa cấu trúc câu hỏi. Hệ thống sẽ Raise ValueError và nhảy sang hàm Fallback (Qwen 2.5).")
    else:
        print("=> THẤT BẠI: Không phát hiện được JSON lỗi.")

if __name__ == "__main__":
    test_logic()
