"""modules/stationnement.py — Blueprint Stationnement TPV"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user, annees_non_payees, get_tarifs_module

bp = Blueprint('sta', __name__)

@bp.route('/stationnement')
@login_required
def sta_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q', '')
    sql = '''SELECT v.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM vehicules v JOIN contribuables c ON v.contribuable_id=c.id WHERE v.actif=1'''
    params = []
    if q:
        sql += ' AND (v.immatriculation LIKE ? OR c.nom LIKE ? OR v.numero LIKE ?)'
        params = [f'%{q}%'] * 3
    items = conn.execute(sql + ' ORDER BY v.date_creation DESC', params).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = get_tarifs_module('STATIONNEMENT')
    conn.close()
    return render_template('stationnement/sta_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs, q=q)

@bp.route('/stationnement/ajouter', methods=['POST'])
@login_required
def sta_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM vehicules').fetchone()['c'] + 1
    num = f"STA{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO vehicules (numero,contribuable_id,commune_id,immatriculation,type_vehicule,num_autorisation,date_autorisation,nombre_sieges)
        VALUES (?,?,?,?,?,?,?,?)''',
        (num, f['contribuable_id'], f.get('commune_id', 1), f.get('immatriculation',''),
         f.get('type_vehicule','Grand Taxi'), f.get('num_autorisation',''),
         f.get('date_autorisation',''), f.get('nombre_sieges', 0)))
    conn.commit(); conn.close()
    flash('Véhicule enregistré ✅', 'success')
    return redirect(url_for('sta.sta_liste'))

@bp.route('/stationnement/<int:id>')
@login_required
def sta_detail(id):
    user = get_current_user()
    conn = get_db()
    veh = conn.execute('''SELECT v.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM vehicules v JOIN contribuables c ON v.contribuable_id=c.id WHERE v.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="STATIONNEMENT" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    annees_man = annees_non_payees('STATIONNEMENT', id, 2020)
    tarifs = get_tarifs_module('STATIONNEMENT')
    conn.close()
    return render_template('stationnement/sta_detail.html', user=user, vehicule=veh, declarations=declarations,
        annees_manquantes=annees_man, tarifs=tarifs, today=date.today().isoformat())

@bp.route('/stationnement/<int:id>/modifier', methods=['POST'])
@login_required
def sta_modifier(id):
    f = request.form
    conn = get_db()
    conn.execute('''UPDATE vehicules SET immatriculation=?,type_vehicule=?,num_autorisation=?,
        nombre_sieges=?,statut=? WHERE id=?''',
        (f.get('immatriculation'), f.get('type_vehicule'), f.get('num_autorisation'),
         f.get('nombre_sieges', 0), f.get('statut','actif'), id))
    conn.commit(); conn.close()
    flash('Véhicule modifié ✅', 'success')
    return redirect(url_for('sta.sta_detail', id=id))

@bp.route('/stationnement/<int:id>/paiement')
@login_required
def sta_paiement(id):
    user = get_current_user()
    conn = get_db()
    veh = conn.execute('''SELECT v.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM vehicules v JOIN contribuables c ON v.contribuable_id=c.id WHERE v.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="STATIONNEMENT" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    annees_man = annees_non_payees('STATIONNEMENT', id, 2020)
    tarifs = get_tarifs_module('STATIONNEMENT')
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='STATIONNEMENT' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiements/paiement_module.html', user=user, objet=veh, module='STATIONNEMENT',
        module_label='Droit de Stationnement TPV', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=tarifs, params=params_m, today=date.today().isoformat())
