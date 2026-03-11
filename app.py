from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, flash
import sqlite3, hashlib, io
from datetime import datetime, date
from functools import wraps

app = Flask(__name__)
app.secret_key = 'fiscalite_communale_secret_2024'
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
        id INTEGER PRIMARY KEY, code TEXT, libelle TEXT, libelle_ar TEXT,
        module TEXT UNIQUE, commune_id INTEGER, actif INTEGER DEFAULT 1, description TEXT
    );
    CREATE TABLE IF NOT EXISTS tarifs (
        id INTEGER PRIMARY KEY, rubrique_id INTEGER, commune_id INTEGER,
        annee INTEGER, code_tarif TEXT, libelle TEXT, valeur REAL, unite TEXT,
        min_legal REAL DEFAULT 0, max_legal REAL DEFAULT 0, actif INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS parametres_calcul (
        id INTEGER PRIMARY KEY, module TEXT, code TEXT,
        libelle TEXT, valeur TEXT, unite TEXT, description TEXT, commune_id INTEGER,
        UNIQUE(module, code)
    );
    CREATE TABLE IF NOT EXISTS terrains (
        id INTEGER PRIMARY KEY, numero_terrain TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        adresse TEXT, adresse_ar TEXT, quartier TEXT, arrondissement TEXT,
        superficie REAL, zone TEXT DEFAULT "B",
        titre_foncier TEXT, num_parcelle TEXT,
        statut TEXT DEFAULT "non_bati", date_acquisition TEXT,
        actif INTEGER DEFAULT 1, date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS permis (
        id INTEGER PRIMARY KEY, terrain_id INTEGER,
        type_permis TEXT, numero_permis TEXT,
        date_depot TEXT, date_delivrance TEXT, statut TEXT DEFAULT "en_cours",
        description TEXT, date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS transferts_terrain (
        id INTEGER PRIMARY KEY, terrain_id INTEGER,
        ancien_contribuable_id INTEGER, nouveau_contribuable_id INTEGER,
        date_transfert TEXT, motif TEXT, acte_notarie TEXT, agent_id INTEGER
    );
    CREATE TABLE IF NOT EXISTS etablissements_boissons (
        id INTEGER PRIMARY KEY, numero TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        nom_etablissement TEXT, type_etablissement TEXT,
        adresse TEXT, superficie REAL,
        numero_autorisation TEXT, date_autorisation TEXT,
        statut TEXT DEFAULT "actif", actif INTEGER DEFAULT 1,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS vehicules (
        id INTEGER PRIMARY KEY, numero TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        immatriculation TEXT, type_vehicule TEXT,
        num_autorisation TEXT, date_autorisation TEXT,
        nombre_sieges INTEGER DEFAULT 0,
        statut TEXT DEFAULT "actif", actif INTEGER DEFAULT 1,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS occupations (
        id INTEGER PRIMARY KEY, numero TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        type_occupation TEXT, localisation TEXT, superficie REAL,
        num_autorisation TEXT, date_debut TEXT, date_fin TEXT,
        statut TEXT DEFAULT "actif", actif INTEGER DEFAULT 1,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS dossiers_fourriere (
        id INTEGER PRIMARY KEY, numero TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        immatriculation TEXT, type_vehicule TEXT,
        date_mise_fourriere TEXT, motif TEXT, nb_jours INTEGER DEFAULT 0,
        frais_remorquage REAL DEFAULT 0,
        statut TEXT DEFAULT "en_fourriere", date_restitution TEXT,
        actif INTEGER DEFAULT 1, date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS baux (
        id INTEGER PRIMARY KEY, numero TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        ref_local TEXT, adresse TEXT, superficie REAL,
        loyer_mensuel REAL, date_debut TEXT, date_fin TEXT,
        statut TEXT DEFAULT "actif", actif INTEGER DEFAULT 1,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS affermages (
        id INTEGER PRIMARY KEY, numero TEXT UNIQUE,
        contribuable_id INTEGER, commune_id INTEGER,
        nom_souk TEXT, num_emplacement TEXT, type_activite TEXT,
        redevance_annuelle REAL, date_debut TEXT,
        statut TEXT DEFAULT "actif", actif INTEGER DEFAULT 1,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS declarations (
        id INTEGER PRIMARY KEY, numero TEXT UNIQUE,
        module TEXT, reference_id INTEGER,
        contribuable_id INTEGER, commune_id INTEGER,
        annee INTEGER, trimestre INTEGER DEFAULT 0,
        base_calcul REAL DEFAULT 0, taux REAL DEFAULT 0,
        montant_principal REAL DEFAULT 0,
        penalite_retard REAL DEFAULT 0, majoration REAL DEFAULT 0,
        amende_non_declaration REAL DEFAULT 0, montant_total REAL DEFAULT 0,
        statut TEXT DEFAULT "emis",
        date_declaration TEXT, date_echeance TEXT, date_paiement TEXT,
        agent_id INTEGER, notes TEXT,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS bulletins (
        id INTEGER PRIMARY KEY, numero_bulletin TEXT UNIQUE,
        declaration_id INTEGER, contribuable_id INTEGER, commune_id INTEGER,
        montant REAL, mode_paiement TEXT DEFAULT "especes",
        date_paiement TEXT, statut TEXT DEFAULT "en_attente",
        agent_id INTEGER, regisseur_id INTEGER, notes TEXT,
        date_creation TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS avis_non_paiement (
        id INTEGER PRIMARY KEY, numero_avis TEXT UNIQUE,
        declaration_id INTEGER, contribuable_id INTEGER, commune_id INTEGER,
        montant_du REAL, date_emission TEXT, delai_jours INTEGER DEFAULT 30,
        lot_id TEXT, statut TEXT DEFAULT "emis"
    );
    ''')

    # Roles
    roles_data = [
        ('super_admin',   1,1,1,1,1,1,1),
        ('admin',         1,1,1,1,1,1,1),
        ('agent_assiette',1,1,0,1,0,0,1),
        ('regisseur',     0,0,0,1,1,0,0),
        ('consultant',    0,0,0,1,0,0,0),
    ]
    for r in roles_data:
        c.execute('''INSERT OR IGNORE INTO roles
            (nom,peut_ajouter,peut_modifier,peut_supprimer,peut_voir,peut_valider_paiement,peut_config,peut_creer_bulletin)
            VALUES (?,?,?,?,?,?,?,?)''', r)

    import json, os
    cfg = None
    if os.path.exists('config.json'):
        with open('config.json', 'r', encoding='utf-8') as f:
            cfg = json.load(f)

    if cfg:
        c.execute('INSERT OR IGNORE INTO communes (id, nom, nom_ar, region, province, code) VALUES (1,?,?,?,?,?)',
                  (cfg['commune']['nom'], cfg['commune']['nom_ar'], cfg['commune']['region'], cfg['commune']['province'], cfg['commune']['code']))
    else:
        c.execute('INSERT OR IGNORE INTO communes (id, nom, nom_ar, region, province, code) VALUES (1,?,?,?,?,?)',
                  ('Commune Exemple','بلدية المثال','Région Test','Province Test','COM001'))

    pwd = hashlib.sha256('admin123'.encode()).hexdigest()
    c.execute('INSERT OR IGNORE INTO utilisateurs (nom,prenom,email,mot_de_passe,role_id,commune_id) VALUES (?,?,?,?,1,1)',
              ('Admin','Super','admin@commune.ma',pwd))

    rubriques_default = [
        ('TNB-001','Taxe sur les Terrains Urbains Non Bâtis','رسوم الأراضي الحضرية غير المبنية','TNB'),
        ('TDB-001','Taxe sur les Débits de Boissons','رسوم محلات بيع المشروبات','DEBITS_BOISSONS'),
        ('TPV-001','Taxe Transport Public des Voyageurs','رسوم النقل العام للمسافرين','TRANSPORT_VOYAGEURS'),
        ('STA-001','Droit de Stationnement TPV','رسوم الوقوف','STATIONNEMENT'),
        ('ODP-001','Redevance Occupation Domaine Public','إتاوة احتلال الملك العام','OCCUPATION_DOMAINE'),
        ('FOU-001','Droits de Fourrière','حقوق الحجز','FOURRIERE'),
        ('LOC-001','Produit Location Locaux Commerciaux','إيرادات كراء المحلات','LOCATION_LOCAUX'),
        ('SOU-001','Produit Affermage Souks Communaux','إيرادات كراء الأسواق','AFFERMAGE_SOUKS'),
    ]
    for r in rubriques_default:
        if cfg and r[3] not in cfg['modules']:
            continue
        c.execute('INSERT OR IGNORE INTO rubriques (code,libelle,libelle_ar,module,commune_id) VALUES (?,?,?,?,1)', r)

    # Tarifs par module
    tnb_id = c.execute("SELECT id FROM rubriques WHERE module='TNB'").fetchone()
    if tnb_id:
        for t in [
            (tnb_id[0],1,2025,'TNB-ZA','Zone A — Bien équipée',20,'DH/m²',15,30),
            (tnb_id[0],1,2025,'TNB-ZB','Zone B — Moy. équipée',8,'DH/m²',5,15),
            (tnb_id[0],1,2025,'TNB-ZC','Zone C — Peu équipée',1,'DH/m²',0.5,2),
        ]: c.execute('INSERT OR IGNORE INTO tarifs (rubrique_id,commune_id,annee,code_tarif,libelle,valeur,unite,min_legal,max_legal) VALUES (?,?,?,?,?,?,?,?,?)', t)

    tdb_id = c.execute("SELECT id FROM rubriques WHERE module='DEBITS_BOISSONS'").fetchone()
    if tdb_id:
        for t in [
            (tdb_id[0],1,2025,'TDB-CAF','Café / Salon de thé',6,'%',2,10),
            (tdb_id[0],1,2025,'TDB-BAR','Bar / Brasserie',10,'%',2,10),
            (tdb_id[0],1,2025,'TDB-REST','Restaurant',5,'%',2,10),
            (tdb_id[0],1,2025,'TDB-HOT','Hôtel-Bar',8,'%',2,10),
        ]: c.execute('INSERT OR IGNORE INTO tarifs (rubrique_id,commune_id,annee,code_tarif,libelle,valeur,unite,min_legal,max_legal) VALUES (?,?,?,?,?,?,?,?,?)', t)

    sta_id = c.execute("SELECT id FROM rubriques WHERE module='STATIONNEMENT'").fetchone()
    if sta_id:
        for t in [
            (sta_id[0],1,2025,'STA-GTAXI','Grand Taxi',300,'DH/an',100,500),
            (sta_id[0],1,2025,'STA-PTAXI','Petit Taxi',200,'DH/an',100,500),
            (sta_id[0],1,2025,'STA-BUS','Autocar/Minibus',500,'DH/an',200,1000),
        ]: c.execute('INSERT OR IGNORE INTO tarifs (rubrique_id,commune_id,annee,code_tarif,libelle,valeur,unite,min_legal,max_legal) VALUES (?,?,?,?,?,?,?,?,?)', t)

    odp_id = c.execute("SELECT id FROM rubriques WHERE module='OCCUPATION_DOMAINE'").fetchone()
    if odp_id:
        for t in [
            (odp_id[0],1,2025,'ODP-TER','Terrasse / Étalage',50,'DH/m²/an',20,200),
            (odp_id[0],1,2025,'ODP-KIO','Kiosque',80,'DH/m²/an',30,300),
            (odp_id[0],1,2025,'ODP-CHAN','Chantier',30,'DH/m²/mois',10,100),
        ]: c.execute('INSERT OR IGNORE INTO tarifs (rubrique_id,commune_id,annee,code_tarif,libelle,valeur,unite,min_legal,max_legal) VALUES (?,?,?,?,?,?,?,?,?)', t)

    fou_id = c.execute("SELECT id FROM rubriques WHERE module='FOURRIERE'").fetchone()
    if fou_id:
        for t in [
            (fou_id[0],1,2025,'FOU-VP','Voiture particulière / jour',25,'DH/jour',10,50),
            (fou_id[0],1,2025,'FOU-MOTO','Moto / Scooter / jour',15,'DH/jour',5,30),
            (fou_id[0],1,2025,'FOU-CAM','Camion / jour',50,'DH/jour',20,100),
            (fou_id[0],1,2025,'FOU-REMOR','Frais de remorquage',150,'DH',50,500),
        ]: c.execute('INSERT OR IGNORE INTO tarifs (rubrique_id,commune_id,annee,code_tarif,libelle,valeur,unite,min_legal,max_legal) VALUES (?,?,?,?,?,?,?,?,?)', t)

    params = [
        ('TNB','DATE_LIMITE','Date limite déclaration/paiement','31/03','date','Art.45 Loi 47-06: avant le 31 Mars'),
        ('TNB','PENALITE_RETARD','Pénalité retard paiement','10','%','10% du montant (Art.147)'),
        ('TNB','MAJORATION_1ER_MOIS','Majoration 1er mois retard','5','%','5% du montant impayé'),
        ('TNB','MAJORATION_MOIS_SUP','Majoration par mois sup.','0.5','%','0.5% par mois ou fraction'),
        ('TNB','AMENDE_NON_DECLARATION','Amende défaut déclaration','15','%','15% min 500 DH (Art.134)'),
        ('TNB','SEUIL_EMISSION','Seuil minimum émission','200','DH','Aucune émission < 200 DH'),
        ('DEBITS_BOISSONS','DATE_LIMITE_TRIMESTRE','Délai déclaration trimestrielle','30','jours','30 jours après fin du trimestre'),
        ('DEBITS_BOISSONS','PENALITE_RETARD','Pénalité retard','10','%','10%'),
        ('DEBITS_BOISSONS','MAJORATION_1ER_MOIS','Majoration 1er mois','5','%','5%'),
        ('DEBITS_BOISSONS','MAJORATION_MOIS_SUP','Majoration mois sup.','0.5','%','0.5%/mois'),
        ('DEBITS_BOISSONS','AMENDE_NON_DECLARATION','Amende non-déclaration','15','%','15% min 500 DH'),
        ('STATIONNEMENT','DATE_LIMITE','Mois limite paiement','Janvier','mois','Janvier de chaque année'),
        ('STATIONNEMENT','PENALITE_RETARD','Pénalité retard','10','%','10%'),
        ('STATIONNEMENT','MAJORATION_1ER_MOIS','Majoration 1er mois','5','%','5%'),
        ('STATIONNEMENT','MAJORATION_MOIS_SUP','Majoration mois sup.','0.5','%','0.5%/mois'),
        ('TRANSPORT_VOYAGEURS','DATE_LIMITE','Mois limite paiement','Janvier','mois','Janvier de chaque année'),
        ('TRANSPORT_VOYAGEURS','PENALITE_RETARD','Pénalité retard','10','%','10%'),
        ('TRANSPORT_VOYAGEURS','MAJORATION_1ER_MOIS','Majoration 1er mois','5','%','5%'),
        ('TRANSPORT_VOYAGEURS','MAJORATION_MOIS_SUP','Majoration mois sup.','0.5','%','0.5%/mois'),
        ('FOURRIERE','TARIF_GARDE_VP','Tarif garde VP/jour','25','DH/jour','Voiture particulière'),
        ('FOURRIERE','TARIF_GARDE_MOTO','Tarif garde Moto/jour','15','DH/jour','Moto/Scooter'),
        ('FOURRIERE','TARIF_GARDE_CAM','Tarif garde Camion/jour','50','DH/jour','Camion'),
        ('FOURRIERE','FRAIS_REMORQUAGE','Frais remorquage','150','DH','Forfait'),
        ('OCCUPATION_DOMAINE','DATE_LIMITE','Date limite renouvellement','31/01','date','31 Janvier chaque année'),
        ('OCCUPATION_DOMAINE','PENALITE_RETARD','Pénalité retard','10','%','10%'),
        ('OCCUPATION_DOMAINE','MAJORATION_1ER_MOIS','Majoration 1er mois','5','%','5%'),
        ('LOCATION_LOCAUX','DELAI_PAIEMENT_LOYER','Délai paiement loyer','10','jours','10 jours après début du mois'),
        ('LOCATION_LOCAUX','PENALITE_RETARD','Pénalité retard','10','%','10%'),
        ('AFFERMAGE_SOUKS','DATE_LIMITE','Date limite paiement','31/01','date','31 Janvier chaque année'),
        ('AFFERMAGE_SOUKS','PENALITE_RETARD','Pénalité retard','10','%','10%'),
        ('GLOBAL','SEUIL_EMISSION_MIN','Seuil minimum émission','200','DH','Loi 07-20'),
        ('GLOBAL','DELAI_AVIS','Délai réponse avis non-paiement','30','jours','30 jours légaux'),
    ]
    for p in params:
        c.execute('INSERT OR IGNORE INTO parametres_calcul (module,code,libelle,valeur,unite,description) VALUES (?,?,?,?,?,?)', p)

    conn.commit(); conn.close()

# =================== HELPERS ===================
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if 'user_id' not in session: return None
    conn = get_db()
    user = conn.execute('''SELECT u.*, r.nom as role_nom,
        r.peut_ajouter, r.peut_modifier, r.peut_supprimer, r.peut_voir,
        r.peut_valider_paiement, r.peut_config, r.peut_creer_bulletin,
        com.nom as commune_nom
        FROM utilisateurs u JOIN roles r ON u.role_id=r.id
        LEFT JOIN communes com ON u.commune_id=com.id WHERE u.id=?''', (session['user_id'],)).fetchone()
    conn.close()
    return user

def get_param(module, code, default=0):
    conn = get_db()
    row = conn.execute('SELECT valeur FROM parametres_calcul WHERE module=? AND code=?', (module,code)).fetchone()
    conn.close()
    try: return float(row['valeur']) if row else default
    except: return default

def calculer_penalites(montant, date_ech_str, date_pay_str=None, module='GLOBAL'):
    if not date_pay_str: date_pay_str = date.today().isoformat()
    try:
        d_ech = datetime.strptime(date_ech_str[:10], '%Y-%m-%d').date()
        d_pay = datetime.strptime(date_pay_str[:10], '%Y-%m-%d').date()
    except: return 0, 0
    if d_pay <= d_ech: return 0, 0
    pen = round(montant * get_param(module, 'PENALITE_RETARD', 10) / 100, 2)
    maj1 = get_param(module, 'MAJORATION_1ER_MOIS', 5) / 100
    majS = get_param(module, 'MAJORATION_MOIS_SUP', 0.5) / 100
    mois = max(1, ((d_pay - d_ech).days + 29) // 30)
    maj = round(montant * maj1 + (montant * majS * (mois-1) if mois > 1 else 0), 2)
    return pen, maj

def gen_num(prefix, table, col='numero'):
    conn = get_db()
    n = conn.execute(f'SELECT COUNT(*) as c FROM {table}').fetchone()['c'] + 1
    conn.close()
    return f"{prefix}{datetime.now().year}{n:05d}"

def annees_non_payees(module, ref_id, debut=2020):
    conn = get_db()
    payees = {r['annee'] for r in conn.execute(
        "SELECT DISTINCT annee FROM declarations WHERE module=? AND reference_id=? AND statut IN ('paye','emis')",
        (module, ref_id)).fetchall()}
    conn.close()
    return [a for a in range(debut, datetime.now().year+1) if a not in payees]

# =================== AUTH ===================
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        pwd = hashlib.sha256(request.form['password'].encode()).hexdigest()
        conn = get_db()
        user = conn.execute('SELECT * FROM utilisateurs WHERE email=? AND mot_de_passe=? AND actif=1',
                            (request.form['email'], pwd)).fetchone()
        conn.close()
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        return render_template('login.html', error='Email ou mot de passe incorrect')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear(); return redirect(url_for('login'))

# =================== DASHBOARD ===================
@app.route('/')
@login_required
def index():
    user = get_current_user()
    conn = get_db()
    stats = {
        'contribuables': conn.execute('SELECT COUNT(*) as c FROM contribuables WHERE actif=1').fetchone()['c'],
        'terrains': conn.execute('SELECT COUNT(*) as c FROM terrains WHERE actif=1').fetchone()['c'],
        'bulletins_attente': conn.execute("SELECT COUNT(*) as c FROM bulletins WHERE statut='en_attente'").fetchone()['c'],
        'avis_emis': conn.execute("SELECT COUNT(*) as c FROM avis_non_paiement WHERE statut='emis'").fetchone()['c'],
        'total_emis': conn.execute("SELECT COALESCE(SUM(montant_total),0) as s FROM declarations").fetchone()['s'],
        'total_paye': conn.execute("SELECT COALESCE(SUM(montant),0) as s FROM bulletins WHERE statut='paye'").fetchone()['s'],
    }
    recentes = conn.execute('''SELECT d.*, c.nom, c.prenom, c.raison_sociale FROM declarations d
        JOIN contribuables c ON d.contribuable_id=c.id ORDER BY d.date_creation DESC LIMIT 8''').fetchall()
    conn.close()
    return render_template('index.html', user=user, stats=stats, recentes=recentes)

# =================== CONTRIBUABLES ===================
@app.route('/contribuables')
@login_required
def contribuables():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q','')
    sql = '''SELECT c.*, com.nom as commune_nom FROM contribuables c
        LEFT JOIN communes com ON c.commune_id=com.id WHERE c.actif=1'''
    params = []
    if q:
        sql += ' AND (c.nom LIKE ? OR c.prenom LIKE ? OR c.numero LIKE ? OR c.raison_sociale LIKE ? OR c.cin LIKE ? OR c.nom_ar LIKE ?)'
        params = [f'%{q}%']*6
    items = conn.execute(sql+' ORDER BY c.date_creation DESC', params).fetchall()
    communes = conn.execute('SELECT * FROM communes WHERE actif=1').fetchall()
    conn.close()
    return render_template('contribuables.html', user=user, items=items, communes=communes, q=q)

@app.route('/contribuables/ajouter', methods=['GET','POST'])
@login_required
def ajouter_contribuable():
    user = get_current_user()
    conn = get_db()
    communes = conn.execute('SELECT * FROM communes WHERE actif=1').fetchall()
    if request.method == 'POST':
        n = conn.execute('SELECT COUNT(*) as c FROM contribuables').fetchone()['c']+1
        num = f"CTB{datetime.now().year}{n:06d}"
        f = request.form
        conn.execute('''INSERT INTO contribuables
            (numero,type_personne,nom,prenom,nom_ar,prenom_ar,raison_sociale,raison_sociale_ar,
            cin,ice,rc,adresse,adresse_ar,ville,code_postal,telephone,email,commune_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (num,f.get('type_personne','physique'),f.get('nom',''),f.get('prenom',''),
             f.get('nom_ar',''),f.get('prenom_ar',''),f.get('raison_sociale',''),f.get('raison_sociale_ar',''),
             f.get('cin',''),f.get('ice',''),f.get('rc',''),
             f.get('adresse',''),f.get('adresse_ar',''),f.get('ville',''),f.get('code_postal',''),
             f.get('telephone',''),f.get('email',''),f.get('commune_id',1)))
        conn.commit(); conn.close()
        flash('Contribuable ajouté ✅','success')
        return redirect(url_for('contribuables'))
    conn.close()
    return render_template('ajouter_contribuable.html', user=user, communes=communes)

@app.route('/contribuables/<int:id>/modifier', methods=['GET','POST'])
@login_required
def modifier_contribuable(id):
    user = get_current_user()
    conn = get_db()
    contrib = conn.execute('SELECT * FROM contribuables WHERE id=?',(id,)).fetchone()
    communes = conn.execute('SELECT * FROM communes WHERE actif=1').fetchall()
    if request.method == 'POST':
        f = request.form
        conn.execute('''UPDATE contribuables SET type_personne=?,nom=?,prenom=?,nom_ar=?,prenom_ar=?,
            raison_sociale=?,raison_sociale_ar=?,cin=?,ice=?,rc=?,adresse=?,adresse_ar=?,
            ville=?,code_postal=?,telephone=?,email=?,commune_id=? WHERE id=?''',
            (f.get('type_personne'),f.get('nom'),f.get('prenom'),f.get('nom_ar',''),f.get('prenom_ar',''),
             f.get('raison_sociale'),f.get('raison_sociale_ar',''),f.get('cin'),f.get('ice'),f.get('rc'),
             f.get('adresse'),f.get('adresse_ar',''),f.get('ville'),f.get('code_postal',''),
             f.get('telephone'),f.get('email'),f.get('commune_id'),id))
        conn.commit(); conn.close()
        flash('Contribuable modifié ✅','success')
        return redirect(url_for('contribuables'))
    conn.close()
    return render_template('modifier_contribuable.html', user=user, contrib=contrib, communes=communes)

@app.route('/contribuables/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_contribuable(id):
    user = get_current_user()
    if user['peut_supprimer']:
        conn = get_db()
        conn.execute('UPDATE contribuables SET actif=0 WHERE id=?',(id,))
        conn.commit(); conn.close()
    return redirect(url_for('contribuables'))

# =================== TNB ===================
@app.route('/tnb')
@login_required
def tnb_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q','')
    sql = '''SELECT t.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.actif=1'''
    params = []
    if q:
        sql += ' AND (c.nom LIKE ? OR t.numero_terrain LIKE ? OR t.adresse LIKE ? OR t.titre_foncier LIKE ?)'
        params = [f'%{q}%']*4
    items = conn.execute(sql+' ORDER BY t.date_creation DESC', params).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="TNB") ORDER BY code_tarif''').fetchall()
    conn.close()
    return render_template('tnb_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs, q=q)

@app.route('/tnb/ajouter', methods=['POST'])
@login_required
def tnb_ajouter():
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM terrains').fetchone()['c']+1
    num = f"TER{datetime.now().year}{n:05d}"
    f = request.form
    conn.execute('''INSERT INTO terrains (numero_terrain,contribuable_id,commune_id,adresse,adresse_ar,
        quartier,arrondissement,superficie,zone,titre_foncier,num_parcelle,statut,date_acquisition)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (num,f['contribuable_id'],f.get('commune_id',1),f.get('adresse',''),f.get('adresse_ar',''),
         f.get('quartier',''),f.get('arrondissement',''),f.get('superficie',0),f.get('zone','B'),
         f.get('titre_foncier',''),f.get('num_parcelle',''),f.get('statut','non_bati'),f.get('date_acquisition','')))
    conn.commit(); conn.close()
    flash('Terrain enregistré ✅','success')
    return redirect(url_for('tnb_liste'))

@app.route('/tnb/<int:id>')
@login_required
def tnb_detail(id):
    user = get_current_user()
    conn = get_db()
    terrain = conn.execute('''SELECT t.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.telephone,
        c.adresse as ctb_adresse, c.numero as ctb_num, c.id as ctb_id
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.id=?''',(id,)).fetchone()
    permis = conn.execute('SELECT * FROM permis WHERE terrain_id=? ORDER BY date_creation DESC',(id,)).fetchall()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="TNB" AND d.reference_id=? ORDER BY d.annee DESC''',(id,)).fetchall()
    transferts = conn.execute('''SELECT tr.*, c1.nom as ancien_nom, c2.nom as nouveau_nom
        FROM transferts_terrain tr
        LEFT JOIN contribuables c1 ON tr.ancien_contribuable_id=c1.id
        LEFT JOIN contribuables c2 ON tr.nouveau_contribuable_id=c2.id
        WHERE tr.terrain_id=? ORDER BY tr.date_transfert DESC''',(id,)).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="TNB") ORDER BY code_tarif''').fetchall()
    annees_man = annees_non_payees('TNB', id)
    conn.close()
    return render_template('tnb_detail.html', user=user, terrain=terrain, permis=permis,
        declarations=declarations, transferts=transferts, contribuables=contribuables,
        tarifs=tarifs, annees_manquantes=annees_man, today=date.today().isoformat())

@app.route('/tnb/<int:id>/modifier', methods=['POST'])
@login_required
def tnb_modifier(id):
    f = request.form
    conn = get_db()
    conn.execute('''UPDATE terrains SET adresse=?,adresse_ar=?,quartier=?,arrondissement=?,
        superficie=?,zone=?,titre_foncier=?,num_parcelle=?,statut=?,date_acquisition=? WHERE id=?''',
        (f.get('adresse'),f.get('adresse_ar',''),f.get('quartier',''),f.get('arrondissement',''),
         f.get('superficie',0),f.get('zone'),f.get('titre_foncier'),f.get('num_parcelle'),
         f.get('statut'),f.get('date_acquisition'),id))
    conn.commit(); conn.close()
    flash('Terrain modifié ✅','success')
    return redirect(url_for('tnb_detail', id=id))

@app.route('/tnb/<int:id>/permis', methods=['POST'])
@login_required
def tnb_permis(id):
    f = request.form
    conn = get_db()
    conn.execute('''INSERT INTO permis (terrain_id,type_permis,numero_permis,date_depot,date_delivrance,statut,description)
        VALUES (?,?,?,?,?,?,?)''',
        (id,f['type_permis'],f.get('numero_permis',''),f.get('date_depot',''),
         f.get('date_delivrance',''),f.get('statut','en_cours'),f.get('description','')))
    conn.commit(); conn.close()
    flash('Permis ajouté ✅','success')
    return redirect(url_for('tnb_detail', id=id))

@app.route('/tnb/<int:id>/transfert', methods=['POST'])
@login_required
def tnb_transfert(id):
    f = request.form
    conn = get_db()
    terrain = conn.execute('SELECT contribuable_id FROM terrains WHERE id=?',(id,)).fetchone()
    if terrain:
        conn.execute('''INSERT INTO transferts_terrain (terrain_id,ancien_contribuable_id,nouveau_contribuable_id,date_transfert,motif,acte_notarie,agent_id)
            VALUES (?,?,?,?,?,?,?)''',
            (id,terrain['contribuable_id'],f['nouveau_contribuable_id'],
             f.get('date_transfert',date.today().isoformat()),f.get('motif',''),f.get('acte_notarie',''),session['user_id']))
        conn.execute('UPDATE terrains SET contribuable_id=? WHERE id=?',(f['nouveau_contribuable_id'],id))
        conn.commit()
    conn.close()
    flash('Transfert effectué ✅','success')
    return redirect(url_for('tnb_detail', id=id))

@app.route('/tnb/<int:id>/paiement')
@login_required
def tnb_paiement(id):
    user = get_current_user()
    conn = get_db()
    terrain = conn.execute('''SELECT t.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="TNB" AND d.reference_id=? ORDER BY d.annee DESC''',(id,)).fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="TNB") ORDER BY code_tarif''').fetchall()
    annees_man = annees_non_payees('TNB', id)
    params_tnb = conn.execute("SELECT * FROM parametres_calcul WHERE module='TNB' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=terrain, module='TNB',
        module_label='Taxe Terrains Urbains Non Bâtis', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=tarifs, params=params_tnb, today=date.today().isoformat())

# =================== DEBITS BOISSONS ===================
@app.route('/debits-boissons')
@login_required
def tdb_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q','')
    sql = '''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.actif=1'''
    params = []
    if q:
        sql += ' AND (c.nom LIKE ? OR e.numero LIKE ? OR e.nom_etablissement LIKE ?)'
        params = [f'%{q}%']*3
    items = conn.execute(sql+' ORDER BY e.date_creation DESC', params).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="DEBITS_BOISSONS") ORDER BY valeur''').fetchall()
    conn.close()
    return render_template('tdb_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs, q=q)

@app.route('/debits-boissons/ajouter', methods=['POST'])
@login_required
def tdb_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM etablissements_boissons').fetchone()['c']+1
    num = f"TDB{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO etablissements_boissons
        (numero,contribuable_id,commune_id,nom_etablissement,type_etablissement,adresse,superficie,numero_autorisation,date_autorisation)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (num,f['contribuable_id'],f.get('commune_id',1),f.get('nom_etablissement',''),
         f.get('type_etablissement','cafe'),f.get('adresse',''),f.get('superficie',0),
         f.get('numero_autorisation',''),f.get('date_autorisation','')))
    conn.commit(); conn.close()
    flash('Établissement ajouté ✅','success')
    return redirect(url_for('tdb_liste'))

@app.route('/debits-boissons/<int:id>')
@login_required
def tdb_detail(id):
    user = get_current_user()
    conn = get_db()
    etab = conn.execute('''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="DEBITS_BOISSONS" AND d.reference_id=? ORDER BY d.annee DESC, d.trimestre DESC''',(id,)).fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="DEBITS_BOISSONS") ORDER BY valeur''').fetchall()
    annees_man = annees_non_payees('DEBITS_BOISSONS', id, 2022)
    conn.close()
    return render_template('tdb_detail.html', user=user, etab=etab, declarations=declarations,
        tarifs=tarifs, annees_manquantes=annees_man, today=date.today().isoformat())

@app.route('/debits-boissons/<int:id>/paiement')
@login_required
def tdb_paiement(id):
    user = get_current_user()
    conn = get_db()
    etab = conn.execute('''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="DEBITS_BOISSONS" AND d.reference_id=? ORDER BY d.annee DESC, d.trimestre DESC''',(id,)).fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="DEBITS_BOISSONS") ORDER BY valeur''').fetchall()
    annees_man = annees_non_payees('DEBITS_BOISSONS', id, 2022)
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='DEBITS_BOISSONS' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=etab, module='DEBITS_BOISSONS',
        module_label='Taxe Débits de Boissons', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=tarifs, params=params_m, today=date.today().isoformat())

# =================== STATIONNEMENT ===================
@app.route('/stationnement')
@login_required
def sta_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q','')
    sql = '''SELECT v.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM vehicules v JOIN contribuables c ON v.contribuable_id=c.id WHERE v.actif=1'''
    params = []
    if q:
        sql += ' AND (v.immatriculation LIKE ? OR c.nom LIKE ? OR v.numero LIKE ?)'
        params = [f'%{q}%']*3
    items = conn.execute(sql+' ORDER BY v.date_creation DESC', params).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="STATIONNEMENT") ORDER BY valeur''').fetchall()
    conn.close()
    return render_template('sta_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs, q=q)

@app.route('/stationnement/ajouter', methods=['POST'])
@login_required
def sta_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM vehicules').fetchone()['c']+1
    num = f"STA{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO vehicules (numero,contribuable_id,commune_id,immatriculation,type_vehicule,num_autorisation,date_autorisation,nombre_sieges)
        VALUES (?,?,?,?,?,?,?,?)''',
        (num,f['contribuable_id'],f.get('commune_id',1),f.get('immatriculation',''),
         f.get('type_vehicule','Grand Taxi'),f.get('num_autorisation',''),
         f.get('date_autorisation',''),f.get('nombre_sieges',0)))
    conn.commit(); conn.close()
    flash('Véhicule enregistré ✅','success')
    return redirect(url_for('sta_liste'))

@app.route('/stationnement/<int:id>')
@login_required
def sta_detail(id):
    user = get_current_user()
    conn = get_db()
    veh = conn.execute('''SELECT v.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM vehicules v JOIN contribuables c ON v.contribuable_id=c.id WHERE v.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="STATIONNEMENT" AND d.reference_id=? ORDER BY d.annee DESC''',(id,)).fetchall()
    annees_man = annees_non_payees('STATIONNEMENT', id, 2020)
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="STATIONNEMENT") ORDER BY valeur''').fetchall()
    conn.close()
    return render_template('sta_detail.html', user=user, vehicule=veh, declarations=declarations,
        annees_manquantes=annees_man, tarifs=tarifs, today=date.today().isoformat())

@app.route('/stationnement/<int:id>/paiement')
@login_required
def sta_paiement(id):
    user = get_current_user()
    conn = get_db()
    veh = conn.execute('''SELECT v.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM vehicules v JOIN contribuables c ON v.contribuable_id=c.id WHERE v.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="STATIONNEMENT" AND d.reference_id=? ORDER BY d.annee DESC''',(id,)).fetchall()
    annees_man = annees_non_payees('STATIONNEMENT', id, 2020)
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="STATIONNEMENT") ORDER BY valeur''').fetchall()
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='STATIONNEMENT' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=veh, module='STATIONNEMENT',
        module_label='Droit de Stationnement TPV', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=tarifs, params=params_m, today=date.today().isoformat())

# =================== FOURRIERE ===================
@app.route('/fourriere')
@login_required
def fou_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q','')
    sql = '''SELECT d.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM dossiers_fourriere d LEFT JOIN contribuables c ON d.contribuable_id=c.id WHERE d.actif=1'''
    params = []
    if q:
        sql += ' AND (d.immatriculation LIKE ? OR d.numero LIKE ?)'
        params = [f'%{q}%']*2
    items = conn.execute(sql+' ORDER BY d.date_creation DESC', params).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="FOURRIERE") ORDER BY code_tarif''').fetchall()
    conn.close()
    return render_template('fou_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs, q=q)

@app.route('/fourriere/ajouter', methods=['POST'])
@login_required
def fou_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM dossiers_fourriere').fetchone()['c']+1
    num = f"FOU{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO dossiers_fourriere (numero,contribuable_id,commune_id,immatriculation,type_vehicule,date_mise_fourriere,motif,nb_jours,frais_remorquage)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (num,f.get('contribuable_id'),f.get('commune_id',1),f.get('immatriculation',''),
         f.get('type_vehicule','Voiture particulière'),f.get('date_mise_fourriere',date.today().isoformat()),
         f.get('motif',''),f.get('nb_jours',1),f.get('frais_remorquage',150)))
    conn.commit(); conn.close()
    flash('Dossier fourrière créé ✅','success')
    return redirect(url_for('fou_liste'))

@app.route('/fourriere/<int:id>/paiement')
@login_required
def fou_paiement(id):
    user = get_current_user()
    conn = get_db()
    dossier = conn.execute('''SELECT d.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM dossiers_fourriere d LEFT JOIN contribuables c ON d.contribuable_id=c.id WHERE d.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="FOURRIERE" AND d.reference_id=? ORDER BY d.date_creation DESC''',(id,)).fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="FOURRIERE") ORDER BY code_tarif''').fetchall()
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='FOURRIERE' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=dossier, module='FOURRIERE',
        module_label='Droits de Fourrière', ref_id=id,
        declarations=declarations, annees_manquantes=[],
        tarifs=tarifs, params=params_m, today=date.today().isoformat())

# =================== OCCUPATION DOMAINE PUBLIC ===================
@app.route('/occupation-domaine')
@login_required
def odp_liste():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('''SELECT o.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM occupations o JOIN contribuables c ON o.contribuable_id=c.id WHERE o.actif=1
        ORDER BY o.date_creation DESC''').fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="OCCUPATION_DOMAINE") ORDER BY valeur''').fetchall()
    conn.close()
    return render_template('odp_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs)

@app.route('/occupation-domaine/ajouter', methods=['POST'])
@login_required
def odp_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM occupations').fetchone()['c']+1
    num = f"ODP{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO occupations (numero,contribuable_id,commune_id,type_occupation,localisation,superficie,num_autorisation,date_debut,date_fin)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (num,f['contribuable_id'],1,f.get('type_occupation',''),f.get('localisation',''),
         f.get('superficie',0),f.get('num_autorisation',''),f.get('date_debut',''),f.get('date_fin','')))
    conn.commit(); conn.close()
    flash('Occupation enregistrée ✅','success')
    return redirect(url_for('odp_liste'))

@app.route('/occupation-domaine/<int:id>/paiement')
@login_required
def odp_paiement(id):
    user = get_current_user()
    conn = get_db()
    occ = conn.execute('''SELECT o.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM occupations o JOIN contribuables c ON o.contribuable_id=c.id WHERE o.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="OCCUPATION_DOMAINE" AND d.reference_id=? ORDER BY d.annee DESC''',(id,)).fetchall()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module="OCCUPATION_DOMAINE") ORDER BY valeur''').fetchall()
    annees_man = annees_non_payees('OCCUPATION_DOMAINE', id, 2022)
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='OCCUPATION_DOMAINE' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=occ, module='OCCUPATION_DOMAINE',
        module_label='Occupation Domaine Public', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=tarifs, params=params_m, today=date.today().isoformat())

# =================== LOCATION LOCAUX ===================
@app.route('/location-locaux')
@login_required
def loc_liste():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('''SELECT b.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM baux b JOIN contribuables c ON b.contribuable_id=c.id WHERE b.actif=1
        ORDER BY b.date_creation DESC''').fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    conn.close()
    return render_template('loc_liste.html', user=user, items=items, contribuables=contribuables)

@app.route('/location-locaux/ajouter', methods=['POST'])
@login_required
def loc_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM baux').fetchone()['c']+1
    num = f"LOC{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO baux (numero,contribuable_id,commune_id,ref_local,adresse,superficie,loyer_mensuel,date_debut,date_fin)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (num,f['contribuable_id'],1,f.get('ref_local',''),f.get('adresse',''),
         f.get('superficie',0),f.get('loyer_mensuel',0),f.get('date_debut',''),f.get('date_fin','')))
    conn.commit(); conn.close()
    flash('Bail ajouté ✅','success')
    return redirect(url_for('loc_liste'))

@app.route('/location-locaux/<int:id>/paiement')
@login_required
def loc_paiement(id):
    user = get_current_user()
    conn = get_db()
    bail = conn.execute('''SELECT b.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM baux b JOIN contribuables c ON b.contribuable_id=c.id WHERE b.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b2.statut as bull_statut, b2.id as bull_id, b2.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b2 ON b2.declaration_id=d.id
        WHERE d.module="LOCATION_LOCAUX" AND d.reference_id=? ORDER BY d.annee DESC, d.trimestre DESC''',(id,)).fetchall()
    annees_man = annees_non_payees('LOCATION_LOCAUX', id, 2022)
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='LOCATION_LOCAUX' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=bail, module='LOCATION_LOCAUX',
        module_label='Location Locaux Commerciaux', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=[], params=params_m, today=date.today().isoformat())

# =================== AFFERMAGE SOUKS ===================
@app.route('/souks')
@login_required
def sou_liste():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('''SELECT a.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM affermages a JOIN contribuables c ON a.contribuable_id=c.id WHERE a.actif=1
        ORDER BY a.date_creation DESC''').fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    conn.close()
    return render_template('sou_liste.html', user=user, items=items, contribuables=contribuables)

@app.route('/souks/ajouter', methods=['POST'])
@login_required
def sou_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM affermages').fetchone()['c']+1
    num = f"SOU{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO affermages (numero,contribuable_id,commune_id,nom_souk,num_emplacement,type_activite,redevance_annuelle,date_debut)
        VALUES (?,?,?,?,?,?,?,?)''',
        (num,f['contribuable_id'],1,f.get('nom_souk',''),f.get('num_emplacement',''),
         f.get('type_activite',''),f.get('redevance_annuelle',0),f.get('date_debut','')))
    conn.commit(); conn.close()
    flash('Affermage ajouté ✅','success')
    return redirect(url_for('sou_liste'))

@app.route('/souks/<int:id>/paiement')
@login_required
def sou_paiement(id):
    user = get_current_user()
    conn = get_db()
    aff = conn.execute('''SELECT a.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM affermages a JOIN contribuables c ON a.contribuable_id=c.id WHERE a.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="AFFERMAGE_SOUKS" AND d.reference_id=? ORDER BY d.annee DESC''',(id,)).fetchall()
    annees_man = annees_non_payees('AFFERMAGE_SOUKS', id, 2022)
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='AFFERMAGE_SOUKS' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=aff, module='AFFERMAGE_SOUKS',
        module_label='Affermage Souks Communaux', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=[], params=params_m, today=date.today().isoformat())

# =================== DECLARATIONS ===================
@app.route('/declarations/creer', methods=['POST'])
@login_required
def creer_declaration():
    user = get_current_user()
    f = request.form
    module = f['module']
    ref_id = int(f['reference_id'])
    contrib_id = int(f['contribuable_id'])
    annee = int(f.get('annee', datetime.now().year))
    base = float(f.get('base_calcul', 0))
    taux = float(f.get('taux', 0))
    principal = round(base * taux / 100 if taux else base, 2)
    date_ech = f.get('date_echeance','')
    date_decl = f.get('date_declaration', date.today().isoformat())
    hors_delai = f.get('hors_delai') == '1'
    penalite, majoration, amende = 0, 0, 0
    if hors_delai:
        a_pct = get_param(module,'AMENDE_NON_DECLARATION',15)
        amende = max(round(principal * a_pct / 100, 2), 500)
    if date_ech and date_decl > date_ech:
        penalite, majoration = calculer_penalites(principal, date_ech, date_decl, module)
    total = round(principal + penalite + majoration + amende, 2)
    if total < 200: total = 0; statut = 'sous_seuil'
    else: statut = 'emis'
    num = gen_num('DCL','declarations')
    conn = get_db()
    conn.execute('''INSERT INTO declarations (numero,module,reference_id,contribuable_id,commune_id,annee,trimestre,
        base_calcul,taux,montant_principal,penalite_retard,majoration,amende_non_declaration,montant_total,
        statut,date_declaration,date_echeance,agent_id,notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (num,module,ref_id,contrib_id,1,annee,int(f.get('trimestre',0)),
         base,taux,principal,penalite,majoration,amende,total,statut,
         date_decl,date_ech,user['id'],f.get('notes','')))
    conn.commit(); conn.close()
    flash(f'Déclaration {num} — Total: {total:.2f} DH ✅','success')
    routes_map = {
        'TNB': 'tnb_paiement', 'DEBITS_BOISSONS': 'tdb_paiement',
        'STATIONNEMENT': 'sta_paiement', 'OCCUPATION_DOMAINE': 'odp_paiement',
        'FOURRIERE': 'fou_paiement', 'LOCATION_LOCAUX': 'loc_paiement',
        'AFFERMAGE_SOUKS': 'sou_paiement',
    }
    if module in routes_map:
        return redirect(url_for(routes_map[module], id=ref_id))
    return redirect(url_for('paiements'))

# =================== BULLETINS / PAIEMENTS ===================
@app.route('/paiements')
@login_required
def paiements():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('''SELECT b.*, d.module, d.annee, c.nom, c.prenom, c.raison_sociale
        FROM bulletins b JOIN declarations d ON b.declaration_id=d.id
        JOIN contribuables c ON b.contribuable_id=c.id ORDER BY b.date_creation DESC''').fetchall()
    decls_sans_bulletin = conn.execute('''SELECT d.*, c.nom, c.prenom, c.raison_sociale FROM declarations d
        JOIN contribuables c ON d.contribuable_id=c.id
        WHERE d.statut="emis" AND d.montant_total>0
        AND d.id NOT IN (SELECT declaration_id FROM bulletins WHERE statut IN ("en_attente","paye"))
        ORDER BY d.date_creation DESC''').fetchall()
    conn.close()
    return render_template('paiements.html', user=user, items=items, decls=decls_sans_bulletin, today=date.today().isoformat())

@app.route('/bulletins/creer', methods=['POST'])
@login_required
def creer_bulletin():
    user = get_current_user()
    if not user['peut_creer_bulletin']:
        flash('Accès refusé','danger'); return redirect(url_for('paiements'))
    f = request.form
    conn = get_db()
    decl = conn.execute('SELECT * FROM declarations WHERE id=?',(f['declaration_id'],)).fetchone()
    if decl:
        num = gen_num('BUL','bulletins','numero_bulletin')
        conn.execute('''INSERT INTO bulletins (numero_bulletin,declaration_id,contribuable_id,commune_id,montant,mode_paiement,date_paiement,agent_id,notes)
            VALUES (?,?,?,?,?,?,?,?,?)''',
            (num,decl['id'],decl['contribuable_id'],decl['commune_id'],decl['montant_total'],
             f.get('mode_paiement','especes'),f.get('date_paiement',date.today().isoformat()),
             user['id'],f.get('notes','')))
        conn.commit()
        flash(f'Bulletin {num} créé — En attente validation régisseur ✅','success')
    conn.close()
    return redirect(url_for('paiements'))

@app.route('/bulletins/<int:id>/valider', methods=['POST'])
@login_required
def valider_bulletin(id):
    user = get_current_user()
    if not user['peut_valider_paiement']:
        flash('Accès refusé — Réservé au Régisseur','danger'); return redirect(url_for('paiements'))
    conn = get_db()
    b = conn.execute('SELECT * FROM bulletins WHERE id=?',(id,)).fetchone()
    if b:
        conn.execute("UPDATE bulletins SET statut='paye',regisseur_id=? WHERE id=?",(user['id'],id))
        conn.execute("UPDATE declarations SET statut='paye',date_paiement=? WHERE id=?",
                     (date.today().isoformat(),b['declaration_id']))
        conn.commit()
        flash('Paiement validé ✅','success')
    conn.close()
    return redirect(url_for('paiements'))

# =================== AVIS ===================
@app.route('/avis')
@login_required
def avis():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('''SELECT a.*, d.module, d.annee, c.nom, c.prenom, c.raison_sociale, c.adresse
        FROM avis_non_paiement a JOIN declarations d ON a.declaration_id=d.id
        JOIN contribuables c ON a.contribuable_id=c.id ORDER BY a.date_emission DESC''').fetchall()
    decls = conn.execute('''SELECT d.*, c.nom, c.prenom, c.raison_sociale FROM declarations d
        JOIN contribuables c ON d.contribuable_id=c.id
        WHERE d.statut="emis" AND d.montant_total>0
        AND d.id NOT IN (SELECT declaration_id FROM avis_non_paiement WHERE statut="emis")''').fetchall()
    conn.close()
    return render_template('avis.html', user=user, items=items, decls=decls)

@app.route('/avis/generer', methods=['POST'])
@login_required
def generer_avis():
    conn = get_db()
    mode = request.form.get('mode','individuel')
    lot_id = f"LOT{datetime.now().strftime('%Y%m%d%H%M%S')}"
    if mode == 'lot':
        decls = conn.execute('''SELECT * FROM declarations WHERE statut="emis" AND montant_total>0
            AND id NOT IN (SELECT declaration_id FROM avis_non_paiement WHERE statut="emis")''').fetchall()
        for d in decls:
            num = gen_num('AVS','avis_non_paiement','numero_avis')
            conn.execute('''INSERT INTO avis_non_paiement (numero_avis,declaration_id,contribuable_id,commune_id,montant_du,date_emission,lot_id)
                VALUES (?,?,?,?,?,?,?)''',(num,d['id'],d['contribuable_id'],d['commune_id'],d['montant_total'],date.today().isoformat(),lot_id))
    else:
        decl_id = request.form.get('declaration_id')
        if decl_id:
            d = conn.execute('SELECT * FROM declarations WHERE id=?',(decl_id,)).fetchone()
            if d:
                num = gen_num('AVS','avis_non_paiement','numero_avis')
                conn.execute('''INSERT INTO avis_non_paiement (numero_avis,declaration_id,contribuable_id,commune_id,montant_du,date_emission)
                    VALUES (?,?,?,?,?,?)''',(num,d['id'],d['contribuable_id'],d['commune_id'],d['montant_total'],date.today().isoformat()))
    conn.commit(); conn.close()
    flash('Avis générés ✅','success')
    return redirect(url_for('avis'))

# =================== MISSING DETAIL + MODIFIER ROUTES ===================
@app.route('/fourriere/<int:id>')
@login_required
def fou_detail(id):
    user = get_current_user()
    conn = get_db()
    dossier = conn.execute('''SELECT d.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM dossiers_fourriere d LEFT JOIN contribuables c ON d.contribuable_id=c.id WHERE d.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="FOURRIERE" AND d.reference_id=? ORDER BY d.date_creation DESC''',(id,)).fetchall()
    conn.close()
    return render_template('fou_detail.html', user=user, dossier=dossier, declarations=declarations,
        today=date.today().isoformat())

@app.route('/debits-boissons/<int:id>/modifier', methods=['POST'])
@login_required
def tdb_modifier(id):
    f = request.form
    conn = get_db()
    conn.execute('''UPDATE etablissements_boissons SET nom_etablissement=?,type_etablissement=?,
        adresse=?,numero_autorisation=?,statut=? WHERE id=?''',
        (f.get('nom_etablissement'),f.get('type_etablissement'),f.get('adresse'),
         f.get('numero_autorisation'),f.get('statut','actif'),id))
    conn.commit(); conn.close()
    flash('Établissement modifié ✅','success')
    return redirect(url_for('tdb_detail', id=id))

@app.route('/stationnement/<int:id>/modifier', methods=['POST'])
@login_required
def sta_modifier(id):
    f = request.form
    conn = get_db()
    conn.execute('''UPDATE vehicules SET immatriculation=?,type_vehicule=?,num_autorisation=?,
        nombre_sieges=?,statut=? WHERE id=?''',
        (f.get('immatriculation'),f.get('type_vehicule'),f.get('num_autorisation'),
         f.get('nombre_sieges',0),f.get('statut','actif'),id))
    conn.commit(); conn.close()
    flash('Véhicule modifié ✅','success')
    return redirect(url_for('sta_detail', id=id))

@app.route('/occupation-domaine/<int:id>')
@login_required
def odp_detail(id):
    user = get_current_user()
    conn = get_db()
    item = conn.execute('''SELECT o.*, c.nom, c.prenom, c.raison_sociale, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM occupations o JOIN contribuables c ON o.contribuable_id=c.id WHERE o.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.numero_bulletin FROM declarations d
        LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="OCCUPATION_DOMAINE" AND d.reference_id=? ORDER BY d.annee DESC''',(id,)).fetchall()
    annees_man = annees_non_payees('OCCUPATION_DOMAINE', id, 2022)
    conn.close()
    infos = [('N°', item['numero']),('Type', item['type_occupation']),('Localisation', item['localisation']),
             ('Superficie', str(item['superficie'])+' m²' if item['superficie'] else '—'),
             ('Statut', item['statut']),('Date début', item['date_debut']),('Date fin', item['date_fin'])]
    return render_template('generic_detail.html', user=user, item=item, declarations=declarations,
        annees_manquantes=annees_man, infos=infos, module_icon='🏪', module_label='Occupation Domaine Public',
        back_url=url_for('odp_liste'), paiement_url=url_for('odp_paiement', id=id))

@app.route('/location-locaux/<int:id>')
@login_required
def loc_detail(id):
    user = get_current_user()
    conn = get_db()
    item = conn.execute('''SELECT b.*, c.nom, c.prenom, c.raison_sociale, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM baux b JOIN contribuables c ON b.contribuable_id=c.id WHERE b.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b2.numero_bulletin FROM declarations d
        LEFT JOIN bulletins b2 ON b2.declaration_id=d.id
        WHERE d.module="LOCATION_LOCAUX" AND d.reference_id=? ORDER BY d.annee DESC''',(id,)).fetchall()
    annees_man = annees_non_payees('LOCATION_LOCAUX', id, 2022)
    conn.close()
    infos = [('N°', item['numero']),('Réf. Local', item['ref_local']),('Adresse', item['adresse']),
             ('Superficie', str(item['superficie'])+' m²' if item['superficie'] else '—'),
             ('Loyer mensuel', str(item['loyer_mensuel'])+' DH'),
             ('Date début', item['date_debut']),('Date fin', item['date_fin'])]
    return render_template('generic_detail.html', user=user, item=item, declarations=declarations,
        annees_manquantes=annees_man, infos=infos, module_icon='🏢', module_label='Location Locaux Commerciaux',
        back_url=url_for('loc_liste'), paiement_url=url_for('loc_paiement', id=id))

@app.route('/souks/<int:id>')
@login_required
def sou_detail(id):
    user = get_current_user()
    conn = get_db()
    item = conn.execute('''SELECT a.*, c.nom, c.prenom, c.raison_sociale, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM affermages a JOIN contribuables c ON a.contribuable_id=c.id WHERE a.id=?''',(id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.numero_bulletin FROM declarations d
        LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="AFFERMAGE_SOUKS" AND d.reference_id=? ORDER BY d.annee DESC''',(id,)).fetchall()
    annees_man = annees_non_payees('AFFERMAGE_SOUKS', id, 2022)
    conn.close()
    infos = [('N°', item['numero']),('Souk', item['nom_souk']),('Emplacement', item['num_emplacement']),
             ('Activité', item['type_activite']),('Redevance annuelle', str(item['redevance_annuelle'])+' DH'),
             ('Statut', item['statut']),('Date début', item['date_debut'])]
    return render_template('generic_detail.html', user=user, item=item, declarations=declarations,
        annees_manquantes=annees_man, infos=infos, module_icon='🛒', module_label='Affermage Souks Communaux',
        back_url=url_for('sou_liste'), paiement_url=url_for('sou_paiement', id=id))

@app.route('/rubriques/ajouter', methods=['POST'])
@login_required
def ajouter_rubrique():
    f = request.form
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO rubriques (code,libelle,libelle_ar,module,commune_id,description) VALUES (?,?,?,?,?,?)',
        (f['code'],f['libelle'],f.get('libelle_ar',''),f['module'],f.get('commune_id',1),f.get('description','')))
    conn.commit(); conn.close()
    flash('Rubrique ajoutée ✅','success')
    return redirect(url_for('rubriques'))

@app.route('/rubriques/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_rubrique(id):
    user = get_current_user()
    if user['peut_supprimer']:
        conn = get_db()
        conn.execute('DELETE FROM rubriques WHERE id=?',(id,))
        conn.commit(); conn.close()
        flash('Rubrique supprimée','info')
    return redirect(url_for('rubriques'))

# =================== CONFIG ===================
@app.route('/rubriques')
@login_required
def rubriques():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('SELECT r.*, c.nom as commune_nom FROM rubriques r LEFT JOIN communes c ON r.commune_id=c.id ORDER BY r.module').fetchall()
    conn.close()
    return render_template('rubriques.html', user=user, items=items)

@app.route('/tarifs')
@login_required
def tarifs():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('''SELECT t.*, r.module, r.libelle as rub_libelle, com.nom as commune_nom
        FROM tarifs t JOIN rubriques r ON t.rubrique_id=r.id
        LEFT JOIN communes com ON t.commune_id=com.id ORDER BY r.module, t.code_tarif''').fetchall()
    rubriques_list = conn.execute('SELECT * FROM rubriques WHERE actif=1').fetchall()
    communes = conn.execute('SELECT * FROM communes WHERE actif=1').fetchall()
    conn.close()
    return render_template('tarifs.html', user=user, items=items, rubriques=rubriques_list,
                           communes=communes, annee_courante=datetime.now().year)

@app.route('/tarifs/ajouter', methods=['POST'])
@login_required
def ajouter_tarif():
    f = request.form
    conn = get_db()
    conn.execute('INSERT INTO tarifs (rubrique_id,commune_id,annee,code_tarif,libelle,valeur,unite,min_legal,max_legal) VALUES (?,?,?,?,?,?,?,?,?)',
        (f['rubrique_id'],f.get('commune_id',1),f['annee'],f.get('code_tarif',''),f['libelle'],f['valeur'],f.get('unite','DH'),f.get('min_legal',0),f.get('max_legal',0)))
    conn.commit(); conn.close()
    flash('Tarif ajouté ✅','success')
    return redirect(url_for('tarifs'))

@app.route('/tarifs/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_tarif(id):
    conn = get_db()
    conn.execute('DELETE FROM tarifs WHERE id=?',(id,))
    conn.commit(); conn.close()
    return redirect(url_for('tarifs'))

@app.route('/parametres')
@login_required
def parametres():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('SELECT * FROM parametres_calcul ORDER BY module, code').fetchall()
    grouped = {}
    for p in items:
        m = p['module']
        if m not in grouped: grouped[m] = []
        grouped[m].append(p)
    conn.close()
    return render_template('parametres.html', user=user, grouped=grouped)

@app.route('/parametres/modifier', methods=['POST'])
@login_required
def modifier_parametres():
    user = get_current_user()
    if not user['peut_config']:
        flash('Accès refusé','danger'); return redirect(url_for('parametres'))
    conn = get_db()
    for k, v in request.form.items():
        if k.startswith('p_'):
            conn.execute('UPDATE parametres_calcul SET valeur=? WHERE id=?',(v,k[2:]))
    conn.commit(); conn.close()
    flash('Paramètres mis à jour ✅','success')
    return redirect(url_for('parametres'))

@app.route('/utilisateurs')
@login_required
def utilisateurs():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('''SELECT u.*, r.nom as role_nom, c.nom as commune_nom FROM utilisateurs u
        JOIN roles r ON u.role_id=r.id LEFT JOIN communes c ON u.commune_id=c.id WHERE u.actif=1''').fetchall()
    roles = conn.execute('SELECT * FROM roles').fetchall()
    communes = conn.execute('SELECT * FROM communes WHERE actif=1').fetchall()
    conn.close()
    return render_template('utilisateurs.html', user=user, items=items, roles=roles, communes=communes)

@app.route('/utilisateurs/ajouter', methods=['POST'])
@login_required
def ajouter_utilisateur():
    user = get_current_user()
    if not user['peut_config']: flash('Accès refusé','danger'); return redirect(url_for('utilisateurs'))
    f = request.form
    pwd = hashlib.sha256(f['password'].encode()).hexdigest()
    conn = get_db()
    try:
        conn.execute('INSERT INTO utilisateurs (nom,prenom,email,mot_de_passe,role_id,commune_id) VALUES (?,?,?,?,?,?)',
            (f['nom'],f['prenom'],f['email'],pwd,f['role_id'],f.get('commune_id',1)))
        conn.commit(); flash('Utilisateur créé ✅','success')
    except Exception as e: flash(f'Erreur: {e}','danger')
    conn.close()
    return redirect(url_for('utilisateurs'))

@app.route('/communes')
@login_required
def communes():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('SELECT * FROM communes WHERE actif=1').fetchall()
    conn.close()
    return render_template('communes.html', user=user, items=items)

@app.route('/communes/ajouter', methods=['POST'])
@login_required
def ajouter_commune():
    f = request.form
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO communes (nom,nom_ar,region,province,code) VALUES (?,?,?,?,?)',
        (f['nom'],f.get('nom_ar',''),f['region'],f['province'],f['code']))
    conn.commit(); conn.close()
    return redirect(url_for('communes'))

# =================== EXPORT ===================
@app.route('/export/<module>/excel')
@login_required
def export_excel(module):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    conn = get_db()
    data = conn.execute('''SELECT d.numero, c.nom||" "||COALESCE(c.prenom,"") as contribuable, c.cin,
        d.annee, d.base_calcul, d.taux, d.montant_principal, d.penalite_retard, d.majoration,
        d.amende_non_declaration, d.montant_total, d.statut, d.date_declaration
        FROM declarations d JOIN contribuables c ON d.contribuable_id=c.id
        WHERE d.module=? ORDER BY d.date_creation DESC''',(module,)).fetchall()
    conn.close()
    wb = Workbook(); ws = wb.active; ws.title = module[:31]
    hf = Font(bold=True, color='FFFFFF')
    hfill = PatternFill('solid', fgColor='1e3a5f')
    hdrs = ['N° Décl.','Contribuable','CIN','Année','Base','Taux%','Principal','Pénalité','Majoration','Amende','TOTAL','Statut','Date']
    for i,h in enumerate(hdrs,1):
        cell = ws.cell(row=1,column=i,value=h)
        cell.font = hf; cell.fill = hfill
        ws.column_dimensions[cell.column_letter].width = 15
    for r,row in enumerate(data,2):
        for i,v in enumerate(row,1): ws.cell(row=r,column=i,value=v)
    out = io.BytesIO(); wb.save(out); out.seek(0)
    return send_file(out, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=f'{module}_{datetime.now():%Y%m%d}.xlsx')

# =================== API ===================
@app.route('/api/contribuable/<int:id>')
@login_required
def api_contribuable(id):
    conn = get_db()
    c = conn.execute('SELECT * FROM contribuables WHERE id=?',(id,)).fetchone()
    conn.close()
    return jsonify(dict(c) if c else {})

@app.route('/api/calcul')
@login_required
def api_calcul():
    montant = float(request.args.get('montant',0))
    ech = request.args.get('echeance','')
    pay = request.args.get('paiement', date.today().isoformat())
    module = request.args.get('module','GLOBAL')
    hors_delai = request.args.get('hors_delai','0') == '1'
    p, m = calculer_penalites(montant, ech, pay, module)
    amende = 0
    if hors_delai:
        a_pct = get_param(module,'AMENDE_NON_DECLARATION',15)
        amende = max(round(montant * a_pct/100, 2), 500)
    return jsonify({'penalite':p,'majoration':m,'amende':amende,'total':round(montant+p+m+amende,2)})

@app.route('/api/tarifs/<module>')
@login_required
def api_tarifs(module):
    conn = get_db()
    tarifs = conn.execute('''SELECT * FROM tarifs WHERE rubrique_id=
        (SELECT id FROM rubriques WHERE module=?) ORDER BY code_tarif''',(module,)).fetchall()
    conn.close()
    return jsonify([dict(t) for t in tarifs])

@app.route('/api/stats')
@login_required
def api_stats():
    conn = get_db()
    modules = ['TNB','DEBITS_BOISSONS','TRANSPORT_VOYAGEURS','STATIONNEMENT',
               'OCCUPATION_DOMAINE','FOURRIERE','LOCATION_LOCAUX','AFFERMAGE_SOUKS']
    result = {}
    for m in modules:
        r = conn.execute("SELECT COUNT(*) as c, COALESCE(SUM(montant_total),0) as t FROM declarations WHERE module=?",(m,)).fetchone()
        result[m] = {'count':r['c'],'total':round(r['t'],2)}
    conn.close()
    return jsonify(result)

if __name__ == '__main__':
    init_db()
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8",80)); ip = s.getsockname()[0]; s.close()
    except: ip = 'localhost'
    print(f"\n{'='*55}\n  GFC MAROC — Gestion Fiscale Communale\n  Local : http://localhost:5000\n  Réseau: http://{ip}:5000\n  Login : admin@commune.ma / admin123\n{'='*55}\n")
    app.run(host='0.0.0.0', port=5000, debug=False)
