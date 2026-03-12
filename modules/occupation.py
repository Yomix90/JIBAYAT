"""modules/occupation.py — Blueprint Occupation Domaine Public"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user, annees_non_payees, get_tarifs_module

bp = Blueprint('odp', __name__)

@bp.route('/occupation-domaine')
@login_required
def odp_liste():
    user = get_current_user()
    conn = get_db()
    items = conn.execute('''SELECT o.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM occupations o JOIN contribuables c ON o.contribuable_id=c.id WHERE o.actif=1
        ORDER BY o.date_creation DESC''').fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = get_tarifs_module('OCCUPATION_DOMAINE')
    conn.close()
    return render_template('odp_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs)

@bp.route('/occupation-domaine/ajouter', methods=['POST'])
@login_required
def odp_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM occupations').fetchone()['c'] + 1
    num = f"ODP{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO occupations (numero,contribuable_id,commune_id,type_occupation,localisation,superficie,num_autorisation,date_debut,date_fin)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (num, f['contribuable_id'], 1, f.get('type_occupation',''), f.get('localisation',''),
         f.get('superficie', 0), f.get('num_autorisation',''), f.get('date_debut',''), f.get('date_fin','')))
    conn.commit(); conn.close()
    flash('Occupation enregistrée ✅', 'success')
    return redirect(url_for('odp.odp_liste'))

@bp.route('/occupation-domaine/<int:id>')
@login_required
def odp_detail(id):
    user = get_current_user()
    conn = get_db()
    item = conn.execute('''SELECT o.*, c.nom, c.prenom, c.raison_sociale, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM occupations o JOIN contribuables c ON o.contribuable_id=c.id WHERE o.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.numero_bulletin FROM declarations d
        LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="OCCUPATION_DOMAINE" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    annees_man = annees_non_payees('OCCUPATION_DOMAINE', id, 2022)
    conn.close()
    infos = [('N°', item['numero']), ('Type', item['type_occupation']), ('Localisation', item['localisation']),
             ('Superficie', str(item['superficie']) + ' m²' if item['superficie'] else '—'),
             ('Statut', item['statut']), ('Date début', item['date_debut']), ('Date fin', item['date_fin'])]
    return render_template('generic_detail.html', user=user, item=item, declarations=declarations,
        annees_manquantes=annees_man, infos=infos, module_icon='🏪', module_label='Occupation Domaine Public',
        back_url=url_for('odp.odp_liste'), paiement_url=url_for('odp.odp_paiement', id=id))

@bp.route('/occupation-domaine/<int:id>/paiement')
@login_required
def odp_paiement(id):
    user = get_current_user()
    conn = get_db()
    occ = conn.execute('''SELECT o.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM occupations o JOIN contribuables c ON o.contribuable_id=c.id WHERE o.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="OCCUPATION_DOMAINE" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    tarifs = get_tarifs_module('OCCUPATION_DOMAINE')
    annees_man = annees_non_payees('OCCUPATION_DOMAINE', id, 2022)
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='OCCUPATION_DOMAINE' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=occ, module='OCCUPATION_DOMAINE',
        module_label='Occupation Domaine Public', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=tarifs, params=params_m, today=date.today().isoformat())
