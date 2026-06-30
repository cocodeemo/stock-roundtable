import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

tmp_path = os.path.join(os.environ.get('TEMP', '/tmp'), 'test_hermes_debug.yaml')

# Create test file
with open(tmp_path, 'w', encoding='utf-8') as f:
    f.write('api_key: sk-test-key-12345\n')
    f.write('some_other: value\n')
f.close()

print(f"File exists: {os.path.exists(tmp_path)}")

# Same code as in load_hermes_config
cfg = {}
result = {"api_key": "", "api_base": None}

try:
    import yaml
    with open(tmp_path) as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        cfg = {}
    print("yaml loaded:", cfg)
except Exception as e:
    cfg = {}
    print(f"yaml failed: {e}")

# Extract api_key from yaml
if cfg:
    for key in ["api_key", "key", "token"]:
        if key in cfg and cfg[key]:
            result["api_key"] = str(cfg[key])
            print(f"Found via yaml key={key}: {repr(cfg[key])}")
            break

# Regex fallback
if not result["api_key"]:
    print("Entering regex fallback...")
    try:
        with open(tmp_path) as f:
            raw = f.read()
        print(f"Raw content: {repr(raw)}")
        m = re.search(r'api_key:\s*["\']?([^"\'\\\n\s]+)["\']?', raw)
        if m:
            result["api_key"] = m.group(1)
            print(f"Regex match: {repr(m.group(1))}")
        else:
            print("NO REGEX MATCH")
    except Exception as e:
        print(f"Regex fallback error: {e}")

print(f"Final result: {result}")

os.unlink(tmp_path)
