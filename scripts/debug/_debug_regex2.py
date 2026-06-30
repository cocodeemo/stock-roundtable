import re

# Test 1: exact pattern from common.py 
pattern = r'api_key:\s*["\']?([^"\'\\\n\s]+)["\']?'
s = 'api_key: sk-test-key-12345'
print('Pattern:', pattern)
m = re.search(pattern, s)
print('Match:', repr(m.group(1)) if m else 'NO MATCH')

# Test 2: what does [\\s] actually match in regex?
m1 = re.search(r'[\s]', 'hello world')
print('\n[\\s] matches space?', bool(m1))

m2 = re.search(r'[\\s]', 'hello world')
print('[\\\\s] in char class matches space?', bool(m2))

m3 = re.search(r'[s]', 'hello world')
print('[s] matches s?', bool(m3))

# Let me try without the raw string:
pattern2 = 'api_key:\\s*["\\\']?([^"\\\'\\\\\\n\\s]+)["\\\']?'
print('\nNon-raw pattern:', pattern2)
m4 = re.search(pattern2, s)
print('Match:', repr(m4.group(1)) if m4 else 'NO MATCH')

# Key test: does [\\s] exclude literal s?
m5 = re.search(r'[^\\s]+', 'sk-test')
print('\n[^\\\\s]+ on "sk-test":', repr(m5.group(0)) if m5 else 'NO MATCH')
