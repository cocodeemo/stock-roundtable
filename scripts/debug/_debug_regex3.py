import re

# The ACTUAL regex string from common.py, character by character
s = 'api_key: sk-test-key-12345'

# Let's build the regex step by step
# r'api_key:\s*["\']?([^"\'\\\n\s]+)["\']?'
pattern = r'api_key:\s*["\']?([^"\'\\\n\s]+)["\']?'
print("Full pattern match:", re.search(pattern, s).group(1) if re.search(pattern, s) else 'NO')

# Let's try simpler char classes to isolate the issue
# Does [^\\s] exclude s literally?
t1 = re.search(r'[^\\s]+', 'sk-test-key-12345')
print("[^\\\\s]+ on 'sk-test-key-12345':", t1.group(0) if t1 else 'NO')

# What about [^\s] - does it exclude space?
t2 = re.search(r'[^\s]+', 'sk-test-key-12345')
print("[^\\s]+ (single backslash) on 'sk-test-key-12345':", t2.group(0) if t2 else 'NO')

# What if we use [^"\'\\n\\s] - without the extra backslash?
# r'[^"\'\n\s]+'  → this should clearly exclude " ' \n and whitespace
t3 = re.search(r'[^"\'\n\s]+', 'sk-test-key-12345')
print("[^\"'\\n\\s]+ on 'sk-test-key-12345':", t3.group(0) if t3 else 'NO')

# Now let's see the actual bytes in the raw string
raw_bytes = [c for c in r'([^"\'\\\n\s]+)']
print("\nRaw string chars:", list(r'([^"\'\\\n\s]+)'))
print("Length:", len(r'([^"\'\\\n\s]+)'))
