"""modules/souks.py — Blueprint Affermage Souks Communaux"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user, annees_non_payees

bp = Blueprint('sou', __name__)

@bp.route('/souks')
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

@bp.route('/souks/ajouter', methods=['POST'])
@login_required
def sou_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM affermages').fetchone()['c'] + 1
    num = f"SOU{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO affermages (numero,contribuable_id,commune_id,nom_souk,num_emplacement,type_activite,redevance_annuelle,date_debut)
        VALUES (?,?,?,?,?,?,?,?)''',
        (num, f['contribuable_id'], 1, f.get('nom_souk',''), f.get('num_emplacement',''),
         f.get('type_activite',''), f.get('redevance_annuelle', 0), f.get('date_debut','')))
    conn.commit(); conn.close()
    flash('Affermage ajouté ✅', 'success')
    return redirect(url_for('sou.sou_liste'))

@bp.route('/souks/<int:id>')
@login_required
def sou_detail(id):
    user = get_current_user()
    conn = get_db()
    item = conn.execute('''SELECT a.*, c.nom, c.prenom, c.raison_sociale, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM affermages a JOIN contribuables c ON a.contribuable_id=c.id WHERE a.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.numero_bulletin FROM declarations d
        LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="AFFERMAGE_SOUKS" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    annees_man = annees_non_payees('AFFERMAGE_SOUKS', id, 2022)
    conn.close()
    infos = [('N°', item['numero']), ('Souk', item['nom_souk']), ('Emplacement', item['num_emplacement']),
             ('Activité', item['type_activite']), ('Redevance annuelle', str(item['redevance_annuelle']) + ' DH'),
             ('Statut', item['statut']), ('Date début', item['date_debut'])]
    return render_template('generic_detail.html', user=user, item=item, declarations=declarations,
        annees_manquantes=annees_man, infos=infos, module_icon='🛒', module_label='Affermage Souks Communaux',
        back_url=url_for('sou.sou_liste'), paiement_url=url_for('sou.sou_paiement', id=id))

@bp.route('/souks/<int:id>/paiement')
@login_required
def sou_paiement(id):
    user = get_current_user()
    conn = get_db()
    aff = conn.execute('''SELECT a.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM affermages a JOIN contribuables c ON a.contribuable_id=c.id WHERE a.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="AFFERMAGE_SOUKS" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    annees_man = annees_non_payees('AFFERMAGE_SOUKS', id, 2022)
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='AFFERMAGE_SOUKS' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=aff, module='AFFERMAGE_SOUKS',
        module_label='Affermage Souks Communaux', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=[], params=params_m, today=date.today().isoformat())
