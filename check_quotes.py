import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path("backend/.env")
load_dotenv(env_path)

private_key = os.getenv("FIREBASE_PRIVATE_KEY")
if private_key:
    print(f"Starts with: {repr(private_key[:5])}")
    print(f"Ends with: {repr(private_key[-5:])}")
    
    # Check if it has actual surrounding quotes that shouldn't be there
    if private_key.startswith('"') and private_key.endswith('"'):
        print("Detected surrounding double quotes!")
    if private_key.startswith("'") and private_key.endswith("'"):
        print("Detected surrounding single quotes!")
else:
    print("Key not found in ENV")
