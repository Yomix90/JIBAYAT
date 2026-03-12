"""
database.py — Connexion DB, init_db, et helpers partagés
"""
import sqlite3, json, os
from datetime import datetime, date

DB = 'fiscalite.db'

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY, nom TEXT UNIQUE,
        peut_ajouter INTEGER DEFAULT 0, peut_modifier INTEGER DEFAULT 0,
        peut_supprimer INTEGER DEFAULT 0, peut_voir INTEGER DEFAULT 1,
        peut_valider_paiement INTEGER DEFAULT 0, peut_config INTEGER DEFAULT 0,
        peut_creer_bulletin INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS utilisateurs (
        id INTEGER PRIMARY KEY, nom TEXT, prenom TEXT,
        email TEXT UNIQUE, mot_de_passe TEXT, role_id INTEGER,
        actif INTEGER DEFAULT 1, commune_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS communes (
        id INTEGER PRIMARY KEY, nom TEXT, nom_ar TEXT,
        region TEXT, province TEXT, code TEXT UNIQUE, actif INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS contribuables (
        id INTEGER PRIMARY KEY, numero TEXT UNIQUE,
        type_personne TEXT DEFAULT "physique",
        nom TEXT, prenom TEXT, nom_ar TEXT, prenom_ar TEXT,
        raison_sociale TEXT, raison_sociale_ar TEXT,
        cin TEXT, ice TEXT, rc TEXT,
        adresse TEXT, adresse_ar TEXT, ville TEXT, code_postal TEXT,
        telephone TEXT, email TEXT, commune_id INTEGER, actif INTEGER DEFAULT 1,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS rubriques (
        id INTEGER PRIMARY KEY, code TEXT UNIQUE, libelle TEXT, libelle_ar TEXT,
        module TEXT UNIQUE, actif INTEGER DEFAULT 1, description TEXT
    );
    CREATE TABLE IF NOT EXISTS arretes_fiscaux (
        id INTEGER PRIMARY KEY,
        numero TEXT UNIQUE,
        titre TEXT,
        date_effet TEXT NOT NULL,
        date_fin TEXT,
        statut TEXT DEFAULT 'actif',
        notes TEXT,
        agent_id INTEGER,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS tarifs (
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
    );
    CREATE TABLE IF NOT EXISTS parametres_calcul (
        id INTEGER PRIMARY KEY, module TEXT, code TEXT,
        libelle TEXT, valeur TEXT, unite TEXT, description TEXT, commune_id INTEGER,
        UNIQUE(module, code)
    );
    CREATE TABLE IF NOT EXISTS tnb_terrains (
        id INTEGER PRIMARY KEY, numero_fiscal TEXT UNIQUE NOT NULL,
        contribuable_id INTEGER, commune_id INTEGER,
        superficie REAL, zone TEXT, adresse TEXT, statut TEXT DEFAULT 'non_bati',
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS tnb_declarations (
        id INTEGER PRIMARY KEY, terrain_id INTEGER, annee INTEGER,
        superficie_declaree REAL, zone TEXT, tarif REAL,
        montant_calcule REAL, montant_paye REAL DEFAULT 0,
        statut TEXT DEFAULT 'emis', date_emission TEXT, date_paiement TEXT,
        agent_id INTEGER, commune_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS tdb_etablissements (
        id INTEGER PRIMARY KEY, numero_licence TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        nom_etablissement TEXT, nom_etablissement_ar TEXT,
        type_etablissement TEXT, categorie TEXT,
        adresse TEXT, date_ouverture TEXT, statut TEXT DEFAULT 'actif',
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS tdb_declarations (
        id INTEGER PRIMARY KEY, etablissement_id INTEGER, annee INTEGER,
        chiffre_affaires REAL, taux REAL, montant_calcule REAL,
        montant_paye REAL DEFAULT 0, statut TEXT DEFAULT 'emis',
        date_emission TEXT, date_paiement TEXT, agent_id INTEGER, commune_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS sta_vehicules (
        id INTEGER PRIMARY KEY, numero_immatriculation TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        type_vehicule TEXT, categorie TEXT,
        marque TEXT, capacite INTEGER, statut TEXT DEFAULT 'actif',
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sta_declarations (
        id INTEGER PRIMARY KEY, vehicule_id INTEGER, annee INTEGER,
        tarif REAL, montant_calcule REAL, montant_paye REAL DEFAULT 0,
        statut TEXT DEFAULT 'emis', date_emission TEXT, date_paiement TEXT,
        agent_id INTEGER, commune_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS odp_occupations (
        id INTEGER PRIMARY KEY, numero_autorisation TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        type_occupation TEXT, superficie REAL, emplacement TEXT,
        date_debut TEXT, date_fin TEXT, tarif REAL, statut TEXT DEFAULT 'actif',
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS odp_declarations (
        id INTEGER PRIMARY KEY, occupation_id INTEGER, annee INTEGER,
        superficie REAL, tarif REAL, montant_calcule REAL,
        montant_paye REAL DEFAULT 0, statut TEXT DEFAULT 'emis',
        date_emission TEXT, date_paiement TEXT, agent_id INTEGER, commune_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS fou_dossiers (
        id INTEGER PRIMARY KEY, numero_pv TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        vehicule_immat TEXT, type_vehicule TEXT,
        date_mise_en_fourriere TEXT, date_sortie TEXT,
        nb_jours INTEGER, statut TEXT DEFAULT 'en_fourriere',
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS fou_declarations (
        id INTEGER PRIMARY KEY, dossier_id INTEGER,
        tarif_journalier REAL, frais_remorquage REAL DEFAULT 0,
        montant_calcule REAL, montant_paye REAL DEFAULT 0,
        statut TEXT DEFAULT 'emis', date_emission TEXT, date_paiement TEXT,
        agent_id INTEGER, commune_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS loc_locaux (
        id INTEGER PRIMARY KEY, numero_contrat TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        designation TEXT, adresse TEXT, superficie REAL,
        loyer_mensuel REAL, date_debut TEXT, date_fin TEXT, statut TEXT DEFAULT 'actif',
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS loc_paiements (
        id INTEGER PRIMARY KEY, local_id INTEGER, mois TEXT,
        montant REAL, montant_paye REAL DEFAULT 0,
        statut TEXT DEFAULT 'en_attente', date_paiement TEXT,
        agent_id INTEGER, commune_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS sou_contrats (
        id INTEGER PRIMARY KEY, numero_contrat TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        nom_souk TEXT, emplacement TEXT, superficie REAL,
        redevance_annuelle REAL, date_debut TEXT, date_fin TEXT, statut TEXT DEFAULT 'actif',
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS sou_paiements (
        id INTEGER PRIMARY KEY, contrat_id INTEGER, annee INTEGER,
        montant REAL, montant_paye REAL DEFAULT 0,
        statut TEXT DEFAULT 'en_attente', date_paiement TEXT,
        agent_id INTEGER, commune_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS paiements_bulletins (
        id INTEGER PRIMARY KEY, module TEXT, reference_id INTEGER,
        commune_id INTEGER, contribuable_id INTEGER,
        montant REAL, date_paiement TEXT, mode_paiement TEXT DEFAULT 'espece',
        reference_paiement TEXT, statut TEXT DEFAULT 'en_attente',
        agent_id INTEGER, valideur_id INTEGER, date_validation TEXT,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS avis_imposition (
        id INTEGER PRIMARY KEY, module TEXT, reference_id INTEGER,
        contribuable_id INTEGER, commune_id INTEGER,
        annee INTEGER, montant REAL, statut TEXT DEFAULT 'emis',
        date_emission TEXT, date_echeance TEXT, date_reglement TEXT,
        agent_id INTEGER
    );
    ''')
    conn.commit()

    # ── Données initiales ──────────────────────────────────────
    import hashlib as _h
    _DEFAULT_CONFIG = 'config.json'
    cfg = None
    if os.path.exists(_DEFAULT_CONFIG):
        with open(_DEFAULT_CONFIG, 'r', encoding='utf-8') as f:
            cfg = json.load(f)

    # Rôles
    roles_default = [
        ('super_admin',1,1,1,1,1,1,1),('admin',1,1,1,1,1,1,1),
        ('agent_assiette',1,1,0,1,0,0,0),('regisseur',0,0,0,1,1,0,1),
        ('consultant',0,0,0,1,0,0,0),
    ]
    for r in roles_default:
        c.execute('''INSERT OR IGNORE INTO roles
            (nom,peut_ajouter,peut_modifier,peut_supprimer,peut_voir,
             peut_valider_paiement,peut_config,peut_creer_bulletin)
            VALUES (?,?,?,?,?,?,?,?)''', r)
    conn.commit()

    # Commune depuis config.json
    if cfg and cfg.get('commune'):
        cm = cfg['commune']
        c.execute('''INSERT OR IGNORE INTO communes (nom,nom_ar,region,province,code)
            VALUES (?,?,?,?,?)''',
            (cm.get('nom','Commune'), cm.get('nom_ar',''), cm.get('region',''),
             cm.get('province',''), cm.get('code','GEN-001')))
        conn.commit()
    else:
        c.execute("INSERT OR IGNORE INTO communes (nom,code) VALUES ('Ma Commune','GEN-001')")
        conn.commit()

    # Admin par défaut
    pwd = _h.sha256('admin123'.encode()).hexdigest()
    admin_role = c.execute("SELECT id FROM roles WHERE nom='super_admin'").fetchone()
    if admin_role:
        c.execute('''INSERT OR IGNORE INTO utilisateurs (nom,prenom,email,mot_de_passe,role_id,commune_id)
            VALUES (?,?,?,?,?,1)''', ('Admin','Super','admin@commune.ma',pwd,admin_role[0]))
        conn.commit()

    # Rubriques avec codes budgétaires officiels
    rubriques_default = [
        ('30101014','Taxe sur les Terrains Urbains Non Bâtis','رسوم الأراضي الحضرية غير المبنية','TNB'),
        ('40101011','Taxe sur les Débits de Boissons','رسوم محلات بيع المشروبات','DEBITS_BOISSONS'),
        ('40201016','Taxe sur le Transport Public des Voyageurs','رسوم النقل العام للمسافرين','TRANSPORT_VOYAGEURS'),
        ('40203033','Droit de Stationnement sur les Véhicules TPV','رسوم الوقوف','STATIONNEMENT'),
        ('40102038','Redevance Occupation Temporaire Domaine Public','إتاوة احتلال الملك العام','OCCUPATION_DOMAINE'),
        ('10403032','Droits de Fourrière','حقوق الحجز','FOURRIERE'),
        ('40102026','Produit de Location des Locaux à Usage Commercial','إيرادات كراء المحلات','LOCATION_LOCAUX'),
        ('40102027','Produit d\'Affermage des Souks Communaux','إيرادات كراء الأسواق','AFFERMAGE_SOUKS'),
    ]
    for r in rubriques_default:
        if cfg and r[3] not in cfg.get('modules', [r[3]]):
            continue
        c.execute('INSERT OR IGNORE INTO rubriques (code,libelle,libelle_ar,module) VALUES (?,?,?,?)', r)
    conn.commit()

    # Arrêté fiscal initial
    c.execute('''INSERT OR IGNORE INTO arretes_fiscaux (id,numero,titre,date_effet,statut,notes)
        VALUES (1,'AF-2020-001','Arrêté Fiscal Initial','2020-01-01','actif','Tarifs initiaux par défaut')''')
    conn.commit()

    # Tarifs initiaux si table vide
    if c.execute('SELECT COUNT(*) FROM tarifs').fetchone()[0] == 0:
        tarifs_data = {
            'TNB': [('Zone A — Bien équipée',20,'DH/m²'),('Zone B — Moyennement équipée',8,'DH/m²'),('Zone C — Peu équipée',1,'DH/m²')],
            'DEBITS_BOISSONS': [('Café / Salon de thé',6,'%'),('Bar / Brasserie',10,'%'),('Restaurant',5,'%'),('Hôtel-Bar',8,'%')],
            'STATIONNEMENT': [('Grand Taxi',300,'DH/an'),('Petit Taxi',200,'DH/an'),('Autocar / Minibus',500,'DH/an')],
            'OCCUPATION_DOMAINE': [('Terrasse / Étalage',50,'DH/m²/an'),('Kiosque',80,'DH/m²/an'),('Chantier',30,'DH/m²/mois')],
            'FOURRIERE': [('Voiture particulière / jour',25,'DH/jour'),('Moto / Scooter / jour',15,'DH/jour'),('Camion / jour',50,'DH/jour'),('Frais de remorquage',150,'DH')],
        }
        for module, items in tarifs_data.items():
            rub = c.execute('SELECT id FROM rubriques WHERE module=?',(module,)).fetchone()
            if rub:
                for libelle, valeur, unite in items:
                    c.execute('INSERT INTO tarifs (rubrique_id,arrete_id,libelle,valeur,unite,date_debut) VALUES (?,1,?,?,?,?)',
                              (rub[0],libelle,valeur,unite,'2020-01-01'))
        conn.commit()

    # Paramètres par défaut
    params = [
        ('TNB','DATE_LIMITE','Date limite déclaration/paiement','31/03','date','Art.45 Loi 47-06: avant le 31 Mars'),
        ('DEBITS_BOISSONS','DATE_LIMITE','Date limite paiement','31/03','date','Avant le 31 Mars'),
        ('STATIONNEMENT','DATE_LIMITE','Date limite paiement','31/01','date','Avant le 31 Janvier'),
    ]
    for p in params:
        c.execute('INSERT OR IGNORE INTO parametres_calcul (module,code,libelle,valeur,unite,description) VALUES (?,?,?,?,?,?)', p)
    conn.commit()
    conn.close()


def get_tarif_at_date(rubrique_id: int, query_date: str) -> dict | None:
    """
    Retourne le tarif actif pour une rubrique à une date donnée.
    Supporte l'historique : si un tarif a été modifié, utilise le bon en fonction de la période.
    """
    conn = get_db()
    row = conn.execute('''
        SELECT * FROM tarifs
        WHERE rubrique_id = ?
          AND date_debut <= ?
          AND (date_fin IS NULL OR date_fin >= ?)
          AND actif = 1
        ORDER BY date_debut DESC
        LIMIT 1
    ''', (rubrique_id, query_date, query_date)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_tarifs_for_period(rubrique_id: int, date_debut: str, date_fin: str) -> list:
    """
    Retourne tous les tarifs applicables sur une période (pour calculs proratisés).
    Utile quand un tarif a changé en cours de période.
    """
    conn = get_db()
    rows = conn.execute('''
        SELECT * FROM tarifs
        WHERE rubrique_id = ?
          AND date_debut <= ?
          AND (date_fin IS NULL OR date_fin >= ?)
          AND actif = 1
        ORDER BY date_debut ASC
    ''', (rubrique_id, date_fin, date_debut)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
