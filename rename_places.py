"""
Script pour renommer a1-a6 en P1-P6 dans tout le projet
"""
import os
import re

# Mapping des remplacements
replacements = {
    '"a1"': '"P1"',
    '"a2"': '"P2"',
    '"a3"': '"P3"',
    '"a4"': '"P4"',
    '"a5"': '"P5"',
    '"a6"': '"P6"',
    '/a1': '/P1',
    '/a2': '/P2',
    '/a3': '/P3',
    '/a4': '/P4',
    '/a5': '/P5',
    '/a6': '/P6',
    'place_id="a1"': 'place_id="P1"',
    'place_id="a2"': 'place_id="P2"',
    'place_id="a3"': 'place_id="P3"',
    'place_id="a4"': 'place_id="P4"',
    'place_id="a5"': 'place_id="P5"',
    'place_id="a6"': 'place_id="P6"',
    # Commentaires
    'a1 -': 'P1 -',
    "ex: a10": "ex: P10",
}

# Fichiers à modifier
files_to_process = [
    'backend/tests/test_parking.py',
    'backend/tests/test_sensor.py',
    'backend/tests/test_admin.py',
    'backend/tests/test_access.py',
    'backend/services/websocket_service.py',
    'frontend/admin/places.html',
]

base_dir = r'c:\Users\AJC\Desktop\aero-park-main (4) - Copie\aero-park-main'

def process_file(filepath):
    """Process a single file"""
    full_path = os.path.join(base_dir, filepath)
    
    if not os.path.exists(full_path):
        print(f"❌ File not found: {filepath}")
        return
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply replacements
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        if content != original_content:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated: {filepath}")
        else:
            print(f"⏭️  No changes: {filepath}")
            
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")

# Process all files
print("🚀 Starting place ID rename: a1-a6 → P1-P6\n")
for filepath in files_to_process:
    process_file(filepath)

print("\n✅ Rename complete!")
