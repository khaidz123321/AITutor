import json
for test_str in ["{", "{ ", "{\n", "{'abc': 1}", "{abc: 1}"]:
    try:
        json.loads(test_str)
    except Exception as e:
        print(repr(test_str), "->", e)
