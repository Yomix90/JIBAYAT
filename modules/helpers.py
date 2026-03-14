"""modules/helpers.py — Fonctions partagées entre tous les blueprints"""
import hashlib
from flask import session, redirect, url_for
from functools import wraps
from datetime import datetime, date
from database import get_db

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
        LEFT JOIN communes com ON u.commune_id=com.id WHERE u.id=?''',
        (session['user_id'],)).fetchone()
    conn.close()
    return user

def get_param(module, code, default=0):
    conn = get_db()
    row = conn.execute('SELECT valeur FROM parametres_calcul WHERE module=? AND code=?', (module, code)).fetchone()
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
    pen  = round(montant * get_param(module, 'PENALITE_RETARD', 10) / 100, 2)
    maj1 = get_param(module, 'MAJORATION_1ER_MOIS', 5) / 100
    majS = get_param(module, 'MAJORATION_MOIS_SUP', 0.5) / 100
    mois = max(1, ((d_pay - d_ech).days + 29) // 30)
    maj  = round(montant * maj1 + (montant * majS * (mois - 1) if mois > 1 else 0), 2)
    return pen, maj

def gen_num(prefix, table, col='numero'):
    conn = get_db()
    n = conn.execute(f'SELECT COUNT(*) as c FROM {table}').fetchone()['c'] + 1
    conn.close()
    return f"{prefix}{datetime.now().year}{n:05d}"

def annees_non_payees(module, ref_id, debut=2020):
    conn = get_db()
    payees = {r['annee'] for r in conn.execute(
        "SELECT DISTINCT annee FROM declarations WHERE module=? AND reference_id=? AND statut='paye'",
        (module, ref_id)).fetchall()}
    conn.close()
    return [a for a in range(debut, datetime.now().year + 1) if a not in payees]

def get_tarifs_module(module):
    conn = get_db()
    rows = conn.execute('''SELECT t.* FROM tarifs t
        JOIN rubriques r ON t.rubrique_id=r.id
        WHERE r.module=? AND t.actif=1
        ORDER BY t.valeur''', (module,)).fetchall()
    conn.close()
    return rows
