"""modules/tdb.py — Blueprint Débits de Boissons (workflow trimestriel complet)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user, get_tarifs_module, get_param, calculer_penalites, gen_num

bp = Blueprint('tdb', __name__)

# ── Helpers ─────────────────────────────────────────────────────────
TRIMESTRES = {1: 'T1 (Jan–Mar)', 2: 'T2 (Avr–Jun)', 3: 'T3 (Jul–Sep)', 4: 'T4 (Oct–Déc)'}
DEADLINE_TRIM = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}  # mois, jour

def trimestres_non_payes(ref_id: int, debut: int = 2022) -> list[dict]:
    """Retourne la liste des trimestres non déclarés/payés depuis debut."""
    conn = get_db()
    payes = {(r['annee'], r['trimestre']) for r in conn.execute(
        """SELECT annee, trimestre FROM declarations
           WHERE module='DEBITS_BOISSONS' AND reference_id=? AND statut NOT IN ('annule')""",
        (ref_id,)).fetchall()}
    conn.close()
    today = date.today()
    result = []
    for y in range(debut, today.year + 1):
        for t in range(1, 5):
            if (y, t) in payes:
                continue
            mois, jour = DEADLINE_TRIM[t]
            try:
                ech = date(y, mois, jour)
            except ValueError:
                ech = date(y, mois, 28)
            if ech > today:
                continue  # Pas encore échu
            result.append({'annee': y, 'trimestre': t, 'label': TRIMESTRES[t],
                           'echeance': ech.isoformat(), 'en_retard': today.isoformat() > ech.isoformat()})
    return result


def calcul_trimestre(base_ht: float, taux: float, annee: int, trim: int,
                     date_decl_str: str, amende_pct: float = 15.0) -> dict:
    """Calcule principal, pénalités et amende pour un trimestre."""
    principal = round(base_ht * taux / 100, 2)
    mois, jour = DEADLINE_TRIM[trim]
    try:
        ech = date(annee, mois, jour).isoformat()
    except ValueError:
        ech = date(annee, mois, 28).isoformat()
    pen, maj = 0.0, 0.0
    amende = 0.0
    if principal > 0 and date_decl_str > ech:
        amende = max(round(principal * amende_pct / 100, 2), 500)
        pen, maj = calculer_penalites(principal, ech, date_decl_str, 'DEBITS_BOISSONS')
    return {'principal': principal, 'penalite': pen, 'majoration': maj,
            'amende': amende, 'total': round(principal + pen + maj + amende, 2), 'echeance': ech}


# ═══════════════════════════════════════════════════════════
# LISTE
# ═══════════════════════════════════════════════════════════
@bp.route('/debits-boissons')
@login_required
def tdb_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q', '')
    sql = '''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num, c.cin, c.rc
        FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.actif=1'''
    params = []
    if q:
        sql += ' AND (c.nom LIKE ? OR e.numero LIKE ? OR e.nom_etablissement LIKE ? OR c.cin LIKE ?)'
        params = [f'%{q}%'] * 4
    items_raw = conn.execute(sql + ' ORDER BY e.date_creation DESC', params).fetchall()
    items = []
    for etab in items_raw:
        item = dict(etab)
        non_payes = trimestres_non_payes(etab['id'], 2022)
        item['nb_non_paye'] = len(non_payes)
        item['annees_non_payees'] = sorted(set(t['annee'] for t in non_payes))
        items.append(item)
    contribuables = conn.execute(
        'SELECT id,numero,nom,prenom,raison_sociale,cin,rc,telephone,email,adresse FROM contribuables WHERE actif=1'
    ).fetchall()
    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    conn.close()
    return render_template('tdb/tdb_liste.html', user=user, items=items,
                           contribuables=contribuables, tarifs=tarifs, q=q)


# ═══════════════════════════════════════════════════════════
# AJOUTER
# ═══════════════════════════════════════════════════════════
@bp.route('/debits-boissons/ajouter', methods=['POST'])
@login_required
def tdb_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM etablissements_boissons').fetchone()['c'] + 1
    num = f"TDB{datetime.now().year}{n:05d}"
    conn.execute(
        '''INSERT INTO etablissements_boissons
        (numero,contribuable_id,commune_id,nom_etablissement,type_etablissement,adresse,superficie,numero_autorisation,date_autorisation)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (num, f['contribuable_id'], f.get('commune_id', 1), f.get('nom_etablissement', ''),
         f.get('type_etablissement', 'cafe'), f.get('adresse', ''), f.get('superficie', 0),
         f.get('numero_autorisation', ''), f.get('date_autorisation', '')))
    conn.commit(); conn.close()
    flash('Établissement ajouté ✅', 'success')
    return redirect(url_for('tdb.tdb_liste'))


# ═══════════════════════════════════════════════════════════
# DETAIL
# ═══════════════════════════════════════════════════════════
@bp.route('/debits-boissons/<int:id>')
@login_required
def tdb_detail(id):
    user = get_current_user()
    conn = get_db()
    etab = conn.execute(
        '''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.telephone, c.id as ctb_id, c.numero as ctb_num
           FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.id=?''',
        (id,)).fetchone()
    declarations = conn.execute(
        '''SELECT d.*, b.statut as bull_statut, b.numero_bulletin, b.numero_quittance, b.date_quittance
           FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
           WHERE d.module="DEBITS_BOISSONS" AND d.reference_id=? ORDER BY d.annee DESC, d.trimestre DESC''',
        (id,)).fetchall()
    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    non_payes = trimestres_non_payes(id, 2022)
    conn.close()
    return render_template('tdb/tdb_detail.html', user=user, etab=etab, declarations=declarations,
                           tarifs=tarifs, trimestres_non_payes=non_payes, today=date.today().isoformat())


# ═══════════════════════════════════════════════════════════
# MODIFIER
# ═══════════════════════════════════════════════════════════
@bp.route('/debits-boissons/<int:id>/modifier', methods=['POST'])
@login_required
def tdb_modifier(id):
    f = request.form
    conn = get_db()
    conn.execute(
        '''UPDATE etablissements_boissons SET nom_etablissement=?,type_etablissement=?,
           adresse=?,numero_autorisation=?,statut=? WHERE id=?''',
        (f.get('nom_etablissement'), f.get('type_etablissement'), f.get('adresse'),
         f.get('numero_autorisation'), f.get('statut', 'actif'), id))
    conn.commit(); conn.close()
    flash('Établissement modifié ✅', 'success')
    return redirect(url_for('tdb.tdb_detail', id=id))


# ═══════════════════════════════════════════════════════════
# PAIEMENT — affichage
# ═══════════════════════════════════════════════════════════
@bp.route('/debits-boissons/<int:id>/paiement')
@login_required
def tdb_paiement(id):
    user = get_current_user()
    conn = get_db()
    etab = conn.execute(
        '''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id,
           c.adresse as ctb_adresse, c.cin, c.rc, c.telephone, c.email
           FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.id=?''',
        (id,)).fetchone()
    if not etab:
        flash('Établissement introuvable', 'danger')
        return redirect(url_for('tdb.tdb_liste'))

    declarations = conn.execute(
        '''SELECT d.*, b.statut as bull_statut, b.id as bull_id,
           b.numero_bulletin, b.numero_quittance as bull_quittance, b.date_quittance as bull_date_quittance
           FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
           WHERE d.module="DEBITS_BOISSONS" AND d.reference_id=? ORDER BY d.annee DESC, d.trimestre DESC''',
        (id,)).fetchall()

    # Autres établissements ODP du même contribuable
    autres_odp = conn.execute(
        '''SELECT op.*, 'ODP' as module_type FROM occupations_domaine op
           WHERE op.contribuable_id=? AND op.actif=1''',
        (etab['ctb_id'],)).fetchall()

    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    non_payes = trimestres_non_payes(id, 2022)
    amende_pct = get_param('DEBITS_BOISSONS', 'AMENDE_NON_DECLARATION', 15)
    today_str = date.today().isoformat()

    # Grouper non-payés par année pour l'affichage
    from collections import defaultdict
    by_year: dict = defaultdict(list)
    for t in non_payes:
        by_year[t['annee']].append(t)
    non_payes_by_year = dict(sorted(by_year.items()))

    # Paramètres
    params_m = conn.execute(
        "SELECT * FROM parametres_calcul WHERE module='DEBITS_BOISSONS' ORDER BY code").fetchall()
    commune_row = conn.execute('SELECT * FROM communes LIMIT 1').fetchone()
    conn.close()

    return render_template('tdb/tdb_paiement.html', user=user, etab=etab,
                           declarations=declarations, non_payes_by_year=non_payes_by_year,
                           tarifs=tarifs, params=params_m, today=today_str,
                           amende_pct=amende_pct, autres_odp=autres_odp,
                           commune=commune_row['nom'] if commune_row else '',
                           TRIMESTRES=TRIMESTRES)


# ═══════════════════════════════════════════════════════════
# SOUMETTRE DÉCLARATION TRIMESTRIELLE (après saisie des montants)
# ═══════════════════════════════════════════════════════════
@bp.route('/debits-boissons/<int:id>/declarer', methods=['POST'])
@login_required
def tdb_declarer(id):
    user = get_current_user()
    f = request.form
    conn = get_db()
    etab = conn.execute('SELECT contribuable_id FROM etablissements_boissons WHERE id=?', (id,)).fetchone()
    if not etab:
        conn.close()
        return redirect(url_for('tdb.tdb_liste'))

    contrib_id = etab['contribuable_id']
    date_decl = f.get('date_declaration', date.today().isoformat())
    num_bulletin = f.get('numero_bulletin', '').strip()
    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    amende_pct = get_param('DEBITS_BOISSONS', 'AMENDE_NON_DECLARATION', 15)
    taux = float(tarifs[0]['valeur']) if tarifs else 10.0

    # Récupérer les trimestres sélectionnés avec leurs montants déclarés
    trims_selectionnes = f.getlist('trims')  # format: "annee_trim"
    n_dcl = conn.execute("SELECT COUNT(*) as c FROM declarations").fetchone()['c'] + 1
    decls_creees = 0
    last_decl_id = None
    last_total = 0.0

    for trim_key in trims_selectionnes:
        try:
            annee_str, trim_str = trim_key.split('_')
            annee = int(annee_str)
            trim = int(trim_str)
        except ValueError:
            continue

        # Vérif doublon
        existing = conn.execute(
            'SELECT id FROM declarations WHERE module="DEBITS_BOISSONS" AND reference_id=? AND annee=? AND trimestre=? AND statut!="annule"',
            (id, annee, trim)).fetchone()
        if existing:
            continue

        base_ht = float(f.get(f'base_{annee}_{trim}', 0) or 0)
        calc = calcul_trimestre(base_ht, taux, annee, trim, date_decl, amende_pct)

        total = calc['total']
        statut_decl = 'sous_seuil' if total < 200 else 'emis'
        num = f"DCL-TDB{datetime.now().year}{n_dcl:05d}"
        n_dcl += 1

        cur = conn.execute(
            '''INSERT INTO declarations
               (numero,module,reference_id,contribuable_id,commune_id,annee,trimestre,
                base_calcul,taux,montant_principal,penalite_retard,majoration,amende_non_declaration,montant_total,
                statut,date_declaration,date_echeance,agent_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (num, 'DEBITS_BOISSONS', id, contrib_id, 1, annee, trim,
             base_ht, taux, calc['principal'], calc['penalite'], calc['majoration'],
             calc['amende'], total, statut_decl, date_decl, calc['echeance'], user['id']))
        last_decl_id = cur.lastrowid
        last_total = total
        decls_creees += 1

    # Créer un seul bulletin pour la dernière déclaration
    if num_bulletin and last_decl_id and last_total >= 200:
        try:
            conn.execute(
                '''INSERT INTO bulletins (numero_bulletin,declaration_id,contribuable_id,
                   commune_id,montant,mode_paiement,date_paiement,agent_id,statut)
                   VALUES (?,?,?,?,?,?,?,?,?)''',
                (num_bulletin, last_decl_id, contrib_id, 1, last_total,
                 'bulletin_manuel', date_decl, user['id'], 'en_attente'))
        except Exception as e:
            flash(f'⚠️ Bulletin non créé : {e}', 'warn')

    conn.commit(); conn.close()
    flash(f'✅ {decls_creees} déclaration(s) trimestrielle(s) enregistrée(s). Bulletin de versement envoyé.', 'success')
    return redirect(url_for('tdb.tdb_paiement', id=id))


# ═══════════════════════════════════════════════════════════
# DÉCLARATION ANNUELLE (renseigner les montants de l'année précédente)
# ═══════════════════════════════════════════════════════════
@bp.route('/debits-boissons/<int:id>/declaration-annuelle', methods=['GET', 'POST'])
@login_required
def tdb_declaration_annuelle(id):
    user = get_current_user()
    conn = get_db()
    etab = conn.execute(
        '''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.rc,
           c.adresse as ctb_adresse, c.telephone, c.email, c.id as ctb_id
           FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.id=?''',
        (id,)).fetchone()
    commune_row = conn.execute('SELECT * FROM communes LIMIT 1').fetchone()
    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    taux = float(tarifs[0]['valeur']) if tarifs else 10.0

    if request.method == 'POST':
        f = request.form
        annee_decl = int(f.get('annee_declaration', date.today().year - 1))
        date_decl = f.get('date_declaration', date.today().isoformat())
        montants = {}
        total_annuel = 0.0
        for t in range(1, 5):
            base = float(f.get(f'base_t{t}', 0) or 0)
            montants[t] = base
            total_annuel += base

        # Générer numéro de déclaration annuelle
        n = conn.execute("SELECT COUNT(*) as c FROM declarations_annuelles_tdb").fetchone()['c'] + 1 if conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='declarations_annuelles_tdb'").fetchone() else 1

        # Stocker la déclaration annuelle dans declarations_annuelles_tdb
        try:
            conn.execute(
                '''INSERT OR IGNORE INTO declarations_annuelles_tdb
                   (numero,etablissement_id,contribuable_id,commune_id,annee,
                    base_t1,base_t2,base_t3,base_t4,total_base,taux,montant_du,
                    date_declaration,agent_id,statut)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (f"DA-TDB{datetime.now().year}{n:05d}", id, etab['ctb_id'], 1, annee_decl,
                 montants[1], montants[2], montants[3], montants[4],
                 total_annuel, taux, round(total_annuel * taux / 100, 2),
                 date_decl, user['id'], 'soumise'))
        except Exception:
            pass
        conn.commit(); conn.close()
        flash(f'✅ Déclaration annuelle {annee_decl} enregistrée.', 'success')
        return redirect(url_for('tdb.tdb_paiement', id=id))

    # GET — afficher formulaire et générer le PDF
    annee_decl = request.args.get('annee', str(date.today().year - 1))
    annee_decl = int(annee_decl)

    # Récupérer les déclarations trimestrielles déjà saisies pour cette année
    decls_trim = {r['trimestre']: r for r in conn.execute(
        'SELECT * FROM declarations WHERE module="DEBITS_BOISSONS" AND reference_id=? AND annee=?',
        (id, annee_decl)).fetchall()}
    conn.close()

    commune = commune_row['nom'] if commune_row else ''
    province = commune_row.get('province', '') if commune_row else ''
    n_decl = f"DA-{annee_decl}-{id:04d}"

    if request.args.get('pdf'):
        return render_template('tdb/tdb_declaration_annuelle_pdf.html',
                               etab=etab, annee=annee_decl, decls_trim=decls_trim,
                               taux=taux, commune=commune, province=province,
                               today=date.today().isoformat(), n_decl=n_decl)
    return render_template('tdb/tdb_declaration_annuelle.html',
                           user=user, etab=etab, annee=annee_decl, decls_trim=decls_trim,
                           taux=taux, commune=commune, province=province,
                           today=date.today().isoformat(), n_decl=n_decl)


# ═══════════════════════════════════════════════════════════
# PDF DÉCLARATION CHIFFRE D'AFFAIRES (Formulaire vierge à remplir)
# ═══════════════════════════════════════════════════════════
@bp.route('/debits-boissons/<int:id>/pdf-declaration-ca')
@login_required
def tdb_pdf_ca(id):
    """Génère le PDF de déclaration du chiffre d'affaires à remplir manuellement."""
    conn = get_db()
    etab = conn.execute(
        '''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.rc,
           c.adresse as ctb_adresse, c.telephone, c.email
           FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.id=?''',
        (id,)).fetchone()
    commune_row = conn.execute('SELECT * FROM communes LIMIT 1').fetchone()
    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    conn.close()

    trims_str = request.args.get('trims', '')
    trims_selected = []
    for tk in trims_str.split(','):
        tk = tk.strip()
        if '_' in tk:
            try:
                y, t = tk.split('_')
                trims_selected.append({'annee': int(y), 'trimestre': int(t),
                                       'label': TRIMESTRES.get(int(t), '')})
            except ValueError:
                pass

    taux = float(tarifs[0]['valeur']) if tarifs else 10.0
    commune = commune_row['nom'] if commune_row else ''
    province = commune_row.get('province', '') if commune_row else ''
    n_decl = f"TDB-CA-{date.today().year}-{id:04d}"

    return render_template('tdb/tdb_declaration_ca_pdf.html',
                           etab=etab, trims=trims_selected, taux=taux,
                           commune=commune, province=province,
                           today=date.today().isoformat(), n_decl=n_decl,
                           TRIMESTRES=TRIMESTRES)


# ═══════════════════════════════════════════════════════════
# AVIS DE NON-PAIEMENT (individuel)
# ═══════════════════════════════════════════════════════════
@bp.route('/debits-boissons/<int:id>/avis-non-paiement')
@login_required
def tdb_avis(id):
    conn = get_db()
    etab = conn.execute(
        '''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.rc,
           c.adresse as ctb_adresse, c.telephone, c.email
           FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.id=?''',
        (id,)).fetchone()
    commune_row = conn.execute('SELECT * FROM communes LIMIT 1').fetchone()
    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    conn.close()

    non_payes = trimestres_non_payes(id, 2022)
    taux = float(tarifs[0]['valeur']) if tarifs else 10.0
    commune = commune_row['nom'] if commune_row else ''
    province = commune_row.get('province', '') if commune_row else ''
    n_avis = f"{id:03d}/{date.today().year}"

    return render_template('tdb/tdb_avis.html',
                           etab=etab, non_payes=non_payes, taux=taux,
                           commune=commune, province=province,
                           today=date.today().isoformat(), n_avis=n_avis,
                           TRIMESTRES=TRIMESTRES)
