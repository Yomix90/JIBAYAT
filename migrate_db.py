"""
Migration DB : ancienne structure → nouvelle structure avec arretes_fiscaux et tarifs historiques.
Exécuter UNE SEULE FOIS : python migrate_db.py
"""
import sqlite3, shutil, os
from datetime import datetime

DB = 'fiscalite.db'

# ── Sauvegarde avant migration ──────────────────────────────
backup = f"fiscalite_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
shutil.copy2(DB, backup)
print(f"✅ Sauvegarde créée : {backup}")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# ── 1. Créer la table arretes_fiscaux si absente ────────────
c.execute('''CREATE TABLE IF NOT EXISTS arretes_fiscaux (
    id INTEGER PRIMARY KEY,
    numero TEXT UNIQUE,
    titre TEXT,
    date_effet TEXT NOT NULL,
    date_fin TEXT,
    statut TEXT DEFAULT 'actif',
    notes TEXT,
    agent_id INTEGER,
    date_creation TEXT DEFAULT CURRENT_TIMESTAMP
)''')

# Insérer un arrêté initial si inexistant
c.execute('''INSERT OR IGNORE INTO arretes_fiscaux (id,numero,titre,date_effet,statut,notes)
    VALUES (1,'AF-2020-001','Arrêté Fiscal Initial','2020-01-01','actif','Tarifs migrés depuis ancienne version')''')
print("✅ Table arretes_fiscaux OK")

# ── 2. Migrer la table tarifs ───────────────────────────────
# Lire l'ancienne structure
cols = [c2[1] for c2 in c.execute('PRAGMA table_info(tarifs)').fetchall()]
has_new_schema = 'date_debut' in cols
print(f"   Colonnes tarifs actuelles : {cols}")

if not has_new_schema:
    print("   → Migration des tarifs en cours...")
    # Lire les anciens tarifs
    old_tarifs = c.execute('SELECT * FROM tarifs').fetchall()
    
    # Renommer l'ancienne table
    c.execute('ALTER TABLE tarifs RENAME TO tarifs_old')
    
    # Créer la nouvelle table
    c.execute('''CREATE TABLE tarifs (
        id INTEGER PRIMARY KEY,
        rubrique_id INTEGER NOT NULL,
        arrete_id INTEGER,
        code_tarif TEXT,
        libelle TEXT NOT NULL,
        valeur REAL NOT NULL,
        unite TEXT DEFAULT 'DH',
        date_debut TEXT NOT NULL,
        date_fin TEXT,
        actif INTEGER DEFAULT 1
    )''')
    
    # Migrer les données : annee → date_debut = ANNEE-01-01
    migrated = 0
    for t in old_tarifs:
        annee = t['annee'] if 'annee' in t.keys() else 2020
        date_debut = f"{annee}-01-01"
        c.execute('''INSERT INTO tarifs 
            (rubrique_id, arrete_id, code_tarif, libelle, valeur, unite, date_debut, actif)
            VALUES (?,1,?,?,?,?,?,?)''',
            (t['rubrique_id'], t['code_tarif'] or '', t['libelle'],
             t['valeur'], t['unite'] or 'DH', date_debut, t['actif']))
        migrated += 1
    
    c.execute('DROP TABLE tarifs_old')
    print(f"   ✅ {migrated} tarifs migrés vers le nouveau schéma")
else:
    print("   ✅ Table tarifs déjà à jour (nouveau schéma)")

# ── 3. Mise à jour des codes budgétaires dans rubriques ─────
codes_officiels = {
    'TNB':                 '30101014',
    'DEBITS_BOISSONS':     '40101011',
    'TRANSPORT_VOYAGEURS': '40201016',
    'STATIONNEMENT':       '40203033',
    'OCCUPATION_DOMAINE':  '40102038',
    'FOURRIERE':           '10403032',
    'LOCATION_LOCAUX':     '40102026',
    'AFFERMAGE_SOUKS':     '40102027',
}
for module, code in codes_officiels.items():
    c.execute('UPDATE rubriques SET code=? WHERE module=?', (code, module))
    
updated = c.rowcount
print(f"✅ Codes budgétaires mis à jour : {len(codes_officiels)} rubriques")

# ── 4. Supprimer la colonne commune_id de rubriques (SQLite ne supporte pas DROP COLUMN avant 3.35) ─
# On laisse la colonne, elle ne nuit pas

conn.commit()
conn.close()
print("\n🎉 Migration terminée avec succès !")
print(f"   Sauvegarde disponible : {backup}")
