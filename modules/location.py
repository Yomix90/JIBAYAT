"""modules/location.py — Blueprint Location Locaux Commerciaux"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user, annees_non_payees

bp = Blueprint('loc', __name__)

@bp.route('/location-locaux')
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

@bp.route('/location-locaux/ajouter', methods=['POST'])
@login_required
def loc_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM baux').fetchone()['c'] + 1
    num = f"LOC{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO baux (numero,contribuable_id,commune_id,ref_local,adresse,superficie,loyer_mensuel,date_debut,date_fin)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (num, f['contribuable_id'], 1, f.get('ref_local',''), f.get('adresse',''),
         f.get('superficie', 0), f.get('loyer_mensuel', 0), f.get('date_debut',''), f.get('date_fin','')))
    conn.commit(); conn.close()
    flash('Bail ajouté ✅', 'success')
    return redirect(url_for('loc.loc_liste'))

@bp.route('/location-locaux/<int:id>')
@login_required
def loc_detail(id):
    user = get_current_user()
    conn = get_db()
    item = conn.execute('''SELECT b.*, c.nom, c.prenom, c.raison_sociale, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM baux b JOIN contribuables c ON b.contribuable_id=c.id WHERE b.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b2.numero_bulletin FROM declarations d
        LEFT JOIN bulletins b2 ON b2.declaration_id=d.id
        WHERE d.module="LOCATION_LOCAUX" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    annees_man = annees_non_payees('LOCATION_LOCAUX', id, 2022)
    conn.close()
    infos = [('N°', item['numero']), ('Réf. Local', item['ref_local']), ('Adresse', item['adresse']),
             ('Superficie', str(item['superficie']) + ' m²' if item['superficie'] else '—'),
             ('Loyer mensuel', str(item['loyer_mensuel']) + ' DH'),
             ('Date début', item['date_debut']), ('Date fin', item['date_fin'])]
    return render_template('generic_detail.html', user=user, item=item, declarations=declarations,
        annees_manquantes=annees_man, infos=infos, module_icon='🏢', module_label='Location Locaux Commerciaux',
        back_url=url_for('loc.loc_liste'), paiement_url=url_for('loc.loc_paiement', id=id))

@bp.route('/location-locaux/<int:id>/paiement')
@login_required
def loc_paiement(id):
    user = get_current_user()
    conn = get_db()
    bail = conn.execute('''SELECT b.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM baux b JOIN contribuables c ON b.contribuable_id=c.id WHERE b.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b2.statut as bull_statut, b2.id as bull_id, b2.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b2 ON b2.declaration_id=d.id
        WHERE d.module="LOCATION_LOCAUX" AND d.reference_id=? ORDER BY d.annee DESC, d.trimestre DESC''', (id,)).fetchall()
    annees_man = annees_non_payees('LOCATION_LOCAUX', id, 2022)
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='LOCATION_LOCAUX' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=bail, module='LOCATION_LOCAUX',
        module_label='Location Locaux Commerciaux', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=[], params=params_m, today=date.today().isoformat())
