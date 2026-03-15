"""
modules/config.py — Blueprint : Rubriques, Arrêtés Fiscaux, Tarifs, Paramètres
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, date
from database import get_db
from functools import wraps

bp = Blueprint('config', __name__)

# ── Décorateur auth partagé ──────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if 'user_id' not in session:
        return None
    conn = get_db()
    user = conn.execute('''SELECT u.*, r.nom as role_nom, r.peut_ajouter, r.peut_modifier,
        r.peut_supprimer, r.peut_voir, r.peut_valider_paiement, r.peut_config, r.peut_creer_bulletin
        FROM utilisateurs u JOIN roles r ON u.role_id=r.id WHERE u.id=?''',
        (session['user_id'],)).fetchone()
    conn.close()
    return user


# ════════════════════════════════════════════════════════════
#  RUBRIQUES
# ════════════════════════════════════════════════════════════

@bp.route('/rubriques')
@login_required
def rubriques():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('SELECT * FROM rubriques ORDER BY module').fetchall()
    conn.close()
    return render_template('admin/rubriques.html', user=user, items=items)

@bp.route('/rubriques/ajouter', methods=['POST'])
@login_required
def ajouter_rubrique():
    f = request.form
    conn = get_db()
    conn.execute('INSERT OR IGNORE INTO rubriques (code,libelle,libelle_ar,module,description) VALUES (?,?,?,?,?)',
        (f['code'], f['libelle'], f.get('libelle_ar',''), f['module'], f.get('description','')))
    conn.commit(); conn.close()
    flash('Rubrique ajoutée ✅', 'success')
    return redirect(url_for('config.rubriques'))

@bp.route('/rubriques/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_rubrique(id):
    conn = get_db()
    conn.execute('UPDATE rubriques SET actif = CASE WHEN actif=1 THEN 0 ELSE 1 END WHERE id=?', (id,))
    conn.commit(); conn.close()
    flash('Statut rubrique mis à jour', 'info')
    return redirect(url_for('config.rubriques'))

@bp.route('/rubriques/<int:id>/modifier', methods=['POST'])
@login_required
def modifier_rubrique(id):
    f = request.form
    conn = get_db()
    conn.execute('UPDATE rubriques SET libelle=?,libelle_ar=?,description=? WHERE id=?',
        (f['libelle'], f.get('libelle_ar',''), f.get('description',''), id))
    conn.commit(); conn.close()
    flash('Rubrique modifiée ✅', 'success')
    return redirect(url_for('config.rubriques'))


# ════════════════════════════════════════════════════════════
#  ARRÊTÉS FISCAUX
# ════════════════════════════════════════════════════════════

@bp.route('/arretes-fiscaux')
@login_required
def arretes_fiscaux():
    user = get_current_user()
    conn = get_db()
    arretes = conn.execute('SELECT * FROM arretes_fiscaux ORDER BY date_effet DESC').fetchall()
    rubriques_list = conn.execute('SELECT * FROM rubriques WHERE actif=1 ORDER BY module').fetchall()
    conn.close()
    return render_template('admin/arretes.html', user=user, arretes=arretes,
                           rubriques=rubriques_list, today=date.today().isoformat())

@bp.route('/arretes-fiscaux/creer', methods=['POST'])
@login_required
def creer_arrete():
    user = get_current_user()
    if not user['peut_config']:
        flash('Accès refusé', 'danger')
        return redirect(url_for('config.arretes_fiscaux'))
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM arretes_fiscaux').fetchone()['c'] + 1
    num = f"AF-{datetime.now().year}-{n:03d}"
    date_effet = f['date_effet']
    # Fermer l'arrêté précédent
    conn.execute("UPDATE arretes_fiscaux SET statut='remplace' WHERE statut='actif'")
    conn.execute('''INSERT INTO arretes_fiscaux (numero,titre,date_effet,notes,agent_id)
        VALUES (?,?,?,?,?)''',
        (num, f.get('titre', f'Arrêté Fiscal {datetime.now().year}'),
         date_effet, f.get('notes',''), user['id']))
    arrete_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.commit(); conn.close()
    flash(f'Arrêté fiscal {num} créé ✅', 'success')
    return redirect(url_for('config.arretes_detail', id=arrete_id))

@bp.route('/arretes-fiscaux/<int:id>')
@login_required
def arretes_detail(id):
    user = get_current_user()
    conn = get_db()
    arrete = conn.execute('SELECT * FROM arretes_fiscaux WHERE id=?', (id,)).fetchone()
    if not arrete:
        flash('Arrêté introuvable', 'danger')
        return redirect(url_for('config.arretes_fiscaux'))
    tarifs_list = conn.execute('''SELECT t.*, r.module, r.libelle as rub_libelle, r.code as rub_code
        FROM tarifs t JOIN rubriques r ON t.rubrique_id=r.id
        WHERE t.arrete_id=? ORDER BY r.module, t.libelle''', (id,)).fetchall()
    rubriques_list = conn.execute('SELECT * FROM rubriques WHERE actif=1 ORDER BY module').fetchall()
    historique = conn.execute('''SELECT t.*, r.module, r.libelle as rub_libelle,
        af.numero as arrete_num, af.date_effet
        FROM tarifs t JOIN rubriques r ON t.rubrique_id=r.id
        JOIN arretes_fiscaux af ON t.arrete_id=af.id
        WHERE t.arrete_id != ? ORDER BY r.module, t.date_debut DESC''', (id,)).fetchall()
    conn.close()
    return render_template('admin/arretes_detail.html', user=user, arrete=arrete,
                           tarifs=tarifs_list, rubriques=rubriques_list,
                           historique=historique, today=date.today().isoformat())


# ════════════════════════════════════════════════════════════
#  TARIFS
# ════════════════════════════════════════════════════════════

@bp.route('/tarifs')
@login_required
def tarifs():
    return redirect(url_for('config.arretes_fiscaux'))

@bp.route('/tarifs/ajouter', methods=['POST'])
@login_required
def ajouter_tarif():
    user = get_current_user()
    if not user['peut_config']:
        flash('Accès refusé', 'danger')
        return redirect(url_for('config.arretes_fiscaux'))
    f = request.form
    libelle = f['libelle'].strip()
    rub_code = f.get('rub_code', '')
    # Code tarif auto-généré
    mots = [m[:3].upper() for m in libelle.split()[:2] if m]
    code_tarif = f"{rub_code}-{''.join(mots)}" if rub_code else '-'.join(mots)
    date_debut = f['date_debut']
    conn = get_db()
    # Fermer le tarif précédent pour ce libellé
    conn.execute('''UPDATE tarifs SET date_fin=?, actif=0
        WHERE rubrique_id=? AND libelle=? AND date_fin IS NULL AND actif=1''',
        (date_debut, f['rubrique_id'], libelle))
    conn.execute('''INSERT INTO tarifs (rubrique_id,arrete_id,code_tarif,libelle,valeur,unite,date_debut,date_fin)
        VALUES (?,?,?,?,?,?,?,?)''',
        (f['rubrique_id'], f.get('arrete_id') or None, code_tarif, libelle,
         f['valeur'], f.get('unite','DH'), date_debut, f.get('date_fin') or None))
    conn.commit(); conn.close()
    flash('Tarif ajouté ✅', 'success')
    arrete_id = f.get('arrete_id')
    return redirect(url_for('config.arretes_detail', id=arrete_id) if arrete_id else url_for('config.arretes_fiscaux'))

@bp.route('/tarifs/<int:id>/modifier', methods=['POST'])
@login_required
def modifier_tarif(id):
    f = request.form
    conn = get_db()
    conn.execute('UPDATE tarifs SET valeur=?,unite=?,date_fin=? WHERE id=?',
                 (f['valeur'], f.get('unite','DH'), f.get('date_fin') or None, id))
    conn.commit(); conn.close()
    flash('Tarif modifié ✅', 'success')
    return redirect(url_for('config.arretes_detail', id=f['arrete_id']))

@bp.route('/tarifs/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_tarif(id):
    f = request.form
    conn = get_db()
    conn.execute('DELETE FROM tarifs WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('config.arretes_detail', id=f.get('arrete_id', 1)))


# ════════════════════════════════════════════════════════════
#  PARAMÈTRES DE CALCUL
# ════════════════════════════════════════════════════════════

@bp.route('/parametres')
@login_required
def parametres():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('SELECT * FROM parametres_calcul ORDER BY module, code').fetchall()
    grouped = {}
    for p in items:
        m = p['module']
        if m not in grouped:
            grouped[m] = []
        grouped[m].append(p)
    conn.close()
    return render_template('admin/parametres.html', user=user, grouped=grouped)

@bp.route('/parametres/modifier', methods=['POST'])
@login_required
def modifier_parametres():
    conn = get_db()
    for key, value in request.form.items():
        if key.startswith('param_'):
            param_id = key.replace('param_', '')
            conn.execute('UPDATE parametres_calcul SET valeur=? WHERE id=?', (value, param_id))
    conn.commit(); conn.close()
    flash('Paramètres mis à jour ✅', 'success')
    return redirect(url_for('config.parametres'))
