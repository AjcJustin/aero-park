import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent / "backend"))
from config import get_settings

def diag():
    settings = get_settings()
    pk = settings.firebase_private_key
    print(f"RAW PK length: {len(pk)}")
    print(f"RAW PK starts with: {repr(pk[:40])}")
    print(f"RAW PK contains literal \\n: {'\\n' in pk}")
    print(f"RAW PK contains real newline: {'\n' in pk}")
    
    # Processed as in get_firebase_credentials
    pk_proc = pk.strip()
    if (pk_proc.startswith('"') and pk_proc.endswith('"')) or (pk_proc.startswith("'") and pk_proc.endswith("'")):
        pk_proc = pk_proc[1:-1]
    pk_proc = pk_proc.strip()
    
    # Test both ways
    pk_v1 = pk_proc.replace("\\n", "\n")
    pk_v2 = pk_proc.replace("\n", "\n") # No change
    
    print(f"V1 length: {len(pk_v1)}")
    print(f"V1 newline count: {pk_v1.count('\n')}")
    
    # Verify markers
    if "-----BEGIN PRIVATE KEY-----" not in pk_v1:
        print("MISSING BEGIN MARKER in V1")
    if "-----END PRIVATE KEY-----" not in pk_v1:
        print("MISSING END MARKER in V1")

if __name__ == "__main__":
    diag()
