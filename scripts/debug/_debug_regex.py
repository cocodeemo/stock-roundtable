import os, re
tmp_path = os.path.join(os.environ.get('TEMP', '/tmp'), 'test_hermes_config.yaml')

with open(tmp_path, 'w', encoding='utf-8') as f:
    f.write('api_key: sk-test-key-12345\n')
    f.write('some_other: value\n')

with open(tmp_path, 'r', encoding='utf-8') as f:
    content = f.read()
print('Content:', repr(content))

# The actual regex from common.py
pattern = r'api_key:\s*["\']?([^"\'\\\n\s]+)["\']?'
print('Pattern:', pattern)
m = re.search(pattern, content)
print('Match:', m.group(1) if m else 'NO MATCH')

os.unlink(tmp_path)
