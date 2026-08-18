import ast
raw = "{'data': [{'id': 'GT1', 'valid': true, 'missing': null}]}"
raw = raw.replace('true', 'True').replace('false', 'False').replace('null', 'None')
try:
    res = ast.literal_eval(raw)
    print('SUCCESS:', res)
except Exception as e:
    print('ERROR:', e)
