import os
import re

filepath = r"d:\Project\AITutor\AI\controller\endpoints\exercises.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Modify Stage 1 loop to capture the last error
stage1_regex = r"qa_list = \[\]\s*for batch_num in range\(3\):(.*?)if len\(qa_list\) == 0:\s*raise HTTPException\(status_code=500, detail=\"DeepSeek Stage 1 khong the sinh ra cau hoi nao\.\"\)"

new_stage1 = """qa_list = []
        last_error = ""
        for batch_num in range(3):
            print(f"-> Stage 1: DeepSeek dang sinh bai tap... (Batch {batch_num + 1}/3)")
            
            try:
                raw_output_stage1 = _call_llm(
                    model=DEEPSEEK_MODEL,
                    messages=[
                        {"role": "system", "content": _DEEPSEEK_GENERATE_QA_PROMPT},
                        {"role": "user", "content": f"LY THUYET:\n{theory_text}"}
                    ],
                    temperature=0.7,
                    response_format={"type": "json_object"}
                )
                
                # Loai bo block <think> cua DeepSeek khoi raw_output_stage1 (neu co)
                if "</think>" in raw_output_stage1:
                    raw_output_stage1 = raw_output_stage1.split("</think>")[-1].strip()
                    
                batch_data = _parse_llm_json(raw_output_stage1)
                if isinstance(batch_data, dict):
                    # Nguoi dung pass JSON object don le (ko mong muon, nhung van check)
                    if "questions" in batch_data:
                        qa_list.extend(batch_data["questions"])
                    elif "data" in batch_data:
                        qa_list.extend(batch_data["data"])
                    else:
                        qa_list.append(batch_data)
                elif isinstance(batch_data, list):
                    qa_list.extend(batch_data)
                    
            except Exception as e:
                print(f"Lỗi ở batch {batch_num + 1}: {e}")
                last_error = str(e)
                
        if len(qa_list) == 0:
            raise HTTPException(status_code=500, detail=f"DeepSeek Stage 1 khong the sinh ra cau hoi nao. Loi cuoi cung: {last_error}")"""

if re.search(stage1_regex, content, flags=re.DOTALL):
    content = re.sub(stage1_regex, lambda m: new_stage1, content, flags=re.DOTALL)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Patched error reporting!")
else:
    print("Could not find stage1 block!")
