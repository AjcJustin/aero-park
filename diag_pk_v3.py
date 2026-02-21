import os

# Manual read to avoid Path issues
env_file = "backend/.env"
pk = None
with open(env_file, 'r', encoding='utf-8') as f:
    for line in f:
        if line.startswith("FIREBASE_PRIVATE_KEY="):
            pk = line.split("=", 1)[1].strip()
            break

print("PK Length:", len(pk) if pk else "None")
if pk:
    print("PK Repr (start):", repr(pk[:60]))
    print("Contains literal slash-n:", "\\n" in pk)
    print("Contains real newline:", "\n" in pk)
    
    # Try to clean it
    s = pk
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    
    s_mapped = s.replace("\\n", "\n")
    print("After mapping, newline count:", s_mapped.count("\n"))
    print("After mapping, start repr:", repr(s_mapped[:40]))
