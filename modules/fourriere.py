"""modules/fourriere.py — Blueprint Fourrière"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user, get_tarifs_module

bp = Blueprint('fou', __name__)

@bp.route('/fourriere')
@login_required
def fou_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q', '')
    sql = '''SELECT d.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM dossiers_fourriere d LEFT JOIN contribuables c ON d.contribuable_id=c.id WHERE d.actif=1'''
    params = []
    if q:
        sql += ' AND (d.immatriculation LIKE ? OR d.numero LIKE ?)'
        params = [f'%{q}%'] * 2
    items = conn.execute(sql + ' ORDER BY d.date_creation DESC', params).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = get_tarifs_module('FOURRIERE')
    conn.close()
    return render_template('fou_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs, q=q)

@bp.route('/fourriere/ajouter', methods=['POST'])
@login_required
def fou_ajouter():
    f = request.form
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM dossiers_fourriere').fetchone()['c'] + 1
    num = f"FOU{datetime.now().year}{n:05d}"
    conn.execute('''INSERT INTO dossiers_fourriere (numero,contribuable_id,commune_id,immatriculation,type_vehicule,date_mise_fourriere,motif,nb_jours,frais_remorquage)
        VALUES (?,?,?,?,?,?,?,?,?)''',
        (num, f.get('contribuable_id'), f.get('commune_id', 1), f.get('immatriculation',''),
         f.get('type_vehicule','Voiture particulière'), f.get('date_mise_fourriere', date.today().isoformat()),
         f.get('motif',''), f.get('nb_jours', 1), f.get('frais_remorquage', 150)))
    conn.commit(); conn.close()
    flash('Dossier fourrière créé ✅', 'success')
    return redirect(url_for('fou.fou_liste'))

@bp.route('/fourriere/<int:id>')
@login_required
def fou_detail(id):
    user = get_current_user()
    conn = get_db()
    dossier = conn.execute('''SELECT d.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.telephone, c.id as ctb_id, c.numero as ctb_num
        FROM dossiers_fourriere d LEFT JOIN contribuables c ON d.contribuable_id=c.id WHERE d.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="FOURRIERE" AND d.reference_id=? ORDER BY d.date_creation DESC''', (id,)).fetchall()
    conn.close()
    return render_template('fou_detail.html', user=user, dossier=dossier, declarations=declarations,
        today=date.today().isoformat())

@bp.route('/fourriere/<int:id>/paiement')
@login_required
def fou_paiement(id):
    user = get_current_user()
    conn = get_db()
    dossier = conn.execute('''SELECT d.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM dossiers_fourriere d LEFT JOIN contribuables c ON d.contribuable_id=c.id WHERE d.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="FOURRIERE" AND d.reference_id=? ORDER BY d.date_creation DESC''', (id,)).fetchall()
    tarifs = get_tarifs_module('FOURRIERE')
    params_m = conn.execute("SELECT * FROM parametres_calcul WHERE module='FOURRIERE' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=dossier, module='FOURRIERE',
        module_label='Droits de Fourrière', ref_id=id,
        declarations=declarations, annees_manquantes=[],
        tarifs=tarifs, params=params_m, today=date.today().isoformat())
