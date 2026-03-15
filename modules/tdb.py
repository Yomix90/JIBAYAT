"""modules/tdb.py — Blueprint Débits de Boissons"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user, annees_non_payees, get_tarifs_module

bp = Blueprint('tdb', __name__)

@bp.route('/debits-boissons')
@login_required
def tdb_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q', '')
    sql = '''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.actif=1'''
    params = []
    if q:
        sql += ' AND (c.nom LIKE ? OR e.numero LIKE ? OR e.nom_etablissement LIKE ?)'
        params = [f'%{q}%'] * 3
    items = conn.execute(sql + ' ORDER BY e.date_creation DESC', params).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    conn.close()
    return render_template('tdb/tdb_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs, q=q)

@bp.route('/debits-boissons/ajouter', methods=['POST'])
@login_required
def tdb_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM etablissements_boissons').fetchone()['c'] + 1
    num = f"TDB{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO etablissements_boissons
        (numero,contribuable_id,commune_id,nom_etablissement,type_etablissement,adresse,superficie,numero_autorisation,date_autorisation)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (num, f['contribuable_id'], f.get('commune_id', 1), f.get('nom_etablissement',''),
         f.get('type_etablissement','cafe'), f.get('adresse',''), f.get('superficie', 0),
         f.get('numero_autorisation',''), f.get('date_autorisation','')))
    conn.commit(); conn.close()
    flash('Établissement ajouté ✅', 'success')
    return redirect(url_for('tdb.tdb_liste'))

@bp.route('/debits-boissons/<int:id>')
@login_required
def tdb_detail(id):
    user = get_current_user()
    conn = get_db()
    etab = conn.execute('''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="DEBITS_BOISSONS" AND d.reference_id=? ORDER BY d.annee DESC, d.trimestre DESC''', (id,)).fetchall()
    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    annees_man = annees_non_payees('DEBITS_BOISSONS', id, 2022)
    conn.close()
    return render_template('tdb/tdb_detail.html', user=user, etab=etab, declarations=declarations,
        tarifs=tarifs, annees_manquantes=annees_man, today=date.today().isoformat())

@bp.route('/debits-boissons/<int:id>/modifier', methods=['POST'])
@login_required
def tdb_modifier(id):
    f = request.form
    conn = get_db()
    conn.execute('''UPDATE etablissements_boissons SET nom_etablissement=?,type_etablissement=?,
        adresse=?,numero_autorisation=?,statut=? WHERE id=?''',
        (f.get('nom_etablissement'), f.get('type_etablissement'), f.get('adresse'),
         f.get('numero_autorisation'), f.get('statut','actif'), id))
    conn.commit(); conn.close()
    flash('Établissement modifié ✅', 'success')
    return redirect(url_for('tdb.tdb_detail', id=id))

@bp.route('/debits-boissons/<int:id>/paiement')
@login_required
def tdb_paiement(id):
    user = get_current_user()
    conn = get_db()
    etab = conn.execute('''SELECT e.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM etablissements_boissons e JOIN contribuables c ON e.contribuable_id=c.id WHERE e.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="DEBITS_BOISSONS" AND d.reference_id=? ORDER BY d.annee DESC, d.trimestre DESC''', (id,)).fetchall()
    tarifs = get_tarifs_module('DEBITS_BOISSONS')
    annees_man = annees_non_payees('DEBITS_BOISSONS', id, 2022)
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='DEBITS_BOISSONS' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiements/paiement_module.html', user=user, objet=etab, module='DEBITS_BOISSONS',
        module_label='Taxe Débits de Boissons', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=tarifs, params=params_m, today=date.today().isoformat())
