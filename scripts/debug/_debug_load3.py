import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from common import load_hermes_config

tmp_path = os.path.join(os.environ.get('TEMP', '/tmp'), 'test_hermes_debug.yaml')

# Create test file
with open(tmp_path, 'w', encoding='utf-8') as f:
    f.write('api_key: sk-test-key-12345\n')
    f.write('some_other: value\n')

print(f"File exists: {os.path.exists(tmp_path)}")
with open(tmp_path) as f:
    print(f"Content: {repr(f.read())}")

# Call actual function
result = load_hermes_config(tmp_path)
print(f"Result: {result}")
print(f"api_key: {repr(result.get('api_key', ''))}")

os.unlink(tmp_path)
