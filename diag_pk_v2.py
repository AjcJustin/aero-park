import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path("backend/.env")
load_dotenv(env_path)

pk = os.getenv("FIREBASE_PRIVATE_KEY")
print(f"RAW PK length: {len(pk) if pk else 'None'}")
print(f"RAW PK repr: {repr(pk[:60]) if pk else 'None'}")

if pk:
    print(f"Contains literal \\n: {'\\n' in pk}")
    print(f"Contains real newline: {'\n' in pk}")
    
    # Simulate cleaning
    pk_clean = pk.strip()
    if (pk_clean.startswith('"') and pk_clean.endswith('"')) or (pk_clean.startswith("'") and pk_clean.endswith("'")):
        pk_clean = pk_clean[1:-1]
    pk_clean = pk_clean.strip()
    
    pk_mapped = pk_clean.replace("\\n", "\n")
    print(f"Mapped PK starts with: {repr(pk_mapped[:40])}")
    print(f"Mapped PK newline count: {pk_mapped.count('\n')}")
