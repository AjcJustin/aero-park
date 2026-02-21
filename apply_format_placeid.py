"""
Script pour appliquer API.formatPlaceId() sur tous les affichages de place_id
"""
import os
import re

base_dir = r'c:\Users\AJC\Desktop\aero-park-main (4) - Copie\aero-park-main'

# Patterns à remplacer - chercher les endroits où place_id est affiché
replacements = [
    # Pattern 1: ${place_id} ou ${reservation.place_id} dans les template literals
    (r'\$\{([^}]*\.)?place_id\}(?!\')', r'${API.formatPlaceId(\1place_id)}'),
    
    # Pattern 2: ' + place_id + ' ou ' + reservation.place_id + '
    (r"\'\s*\+\s*([a-zA-Z_][\w\.]*\.place_id)\s*\+\s*\'", r"' + API.formatPlaceId(\1) + '"),
    
    # Pattern 3: (place_id || ...) dans des expressions
    (r'\(([a-zA-Z_][\w\.]*\.place_id)\s*\|\|', r'(API.formatPlaceId(\1) ||'),
]

files_to_process = [
    'frontend/pages/reservation.html',
    'frontend/pages/profile.html',
    'frontend/pages/admin.html',
    'frontend/admin/dashboard.html',
    'frontend/admin/reservations.html',
    'frontend/admin/payments.html',
    'frontend/admin/users.html',
]

def process_file(filepath):
    """Process a single file"""
    full_path = os.path.join(base_dir, filepath)
    
    if not os.path.exists(full_path):
        print(f"❌ File not found: {filepath}")
        return False
    
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes_made = []
        
        # Apply each replacement pattern
        for pattern, replacement in replacements:
            matches = re.findall(pattern, content)
            if matches:
                content = re.sub(pattern, replacement, content)
                changes_made.append(f"  - Pattern '{pattern[:50]}...' matched {len(matches)} times")
        
        # Fix specific issues
        # Remove double >> if present
        content = content.replace('}></span>', '}</span>')
        
        if content != original_content:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated: {filepath}")
            for change in changes_made:
                print(change)
            return True
        else:
            print(f"⏭️  No changes: {filepath}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return False

# Process all files
print("🚀 Applying API.formatPlaceId() to frontend pages\n")
total_updated = 0

for filepath in files_to_process:
    if process_file(filepath):
        total_updated += 1
    print()

print(f"\n✅ Complete! Updated {total_updated}/{len(files_to_process)} files")
