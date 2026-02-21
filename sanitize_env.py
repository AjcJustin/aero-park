import os

# Lire toutes les lignes
with open('backend/.env', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "=" in line:
        key, val = line.split("=", 1)
        # Supprimer les guillemets et espaces
        val = val.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            val = val[1:-1]
        new_lines.append(f"{key}={val}\n")
    else:
        new_lines.append(line)

with open('backend/.env', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("✅ .env file sanitized (quotes removed)")
