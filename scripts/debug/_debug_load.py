import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import tempfile, io
from common import load_hermes_config

def debug_load_hermes_config():
    """Test with explicit debugging"""
    tmp_path = os.path.join(tempfile.gettempdir(), 'test_hermes_debug.yaml')
    
    # Clear any existing file
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
    
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write('api_key: sk-test-key-12345\n')
        f.write('some_other: value\n')
    
    # Verify file content
    with open(tmp_path, 'r', encoding='utf-8') as f:
        content = f.read()
    print(f"File content: {repr(content)}")
    print(f"File exists: {os.path.exists(tmp_path)}")
    
    # Try importing yaml
    try:
        import yaml
        print(f"yaml is available: {yaml.__version__ if hasattr(yaml, '__version__') else 'yes'}")
        with open(tmp_path) as f:
            cfg = yaml.safe_load(f)
        print(f"yaml parsed: {cfg}")
    except ImportError:
        print("yaml not available")
    
    # Now run the actual function
    result = load_hermes_config(tmp_path)
    print(f"Result: {result}")
    print(f"api_key repr: {repr(result.get('api_key', ''))}")
    
    os.unlink(tmp_path)
    return result

debug_load_hermes_config()
