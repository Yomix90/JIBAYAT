"""
fix_confirm.py — Remplace les onsubmit="return confirm(...)" des templates HTML
par des attributs data-confirm pour la modale personnalisée.
"""
import os, re

TEMPLATES = 'templates'

# Patterns à remplacer
REPLACEMENTS = [
    # Suppression avec confirm()
    (
        r'onsubmit="return confirm\([^)]+\)"',
        'data-confirm="danger" data-confirm-title="Confirmer la suppression" data-confirm-msg="Cette action est irréversible. Voulez-vous vraiment supprimer cet élément ?"'
    ),
    (
        r"onsubmit='return confirm\([^)]+\)'",
        'data-confirm="danger" data-confirm-title="Confirmer la suppression" data-confirm-msg="Cette action est irréversible. Voulez-vous vraiment supprimer cet élément ?"'
    ),
]

fixed = 0
for filename in os.listdir(TEMPLATES):
    if not filename.endswith('.html'):
        continue
    path = os.path.join(TEMPLATES, filename)
    content = open(path, encoding='utf-8').read()
    original = content
    for pattern, replacement in REPLACEMENTS:
        content = re.sub(pattern, replacement, content)
    if content != original:
        open(path, 'w', encoding='utf-8').write(content)
        fixed += 1
        print(f"  ✅ {filename}")

print(f"\n🎉 {fixed} fichiers mis à jour !")
