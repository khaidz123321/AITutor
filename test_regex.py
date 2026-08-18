import json
import re

with open('test_output.txt', 'r', encoding='utf-8') as f:
    raw = f.read()

if '</think>' in raw:
    raw = raw.split('</think>')[-1].strip()

match = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, flags=re.DOTALL | re.IGNORECASE)
if match:
    raw = match.group(1).strip()

raw1 = re.sub(r'\\(?![/"\\bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', raw)
raw2 = re.sub(r',\s*([\]}])', r'\1', raw1)

try:
    json.loads(raw2, strict=False)
    print('SUCCESS')
except Exception as e:
    print('ERROR:', e)
