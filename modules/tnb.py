"""modules/tnb.py — Blueprint TNB (Taxe Terrains Urbains Non Bâtis)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user, annees_non_payees, get_tarifs_module

bp = Blueprint('tnb', __name__)

@bp.route('/tnb')
@login_required
def tnb_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q', '')
    sql = '''SELECT t.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.actif=1'''
    params = []
    if q:
        sql += ' AND (c.nom LIKE ? OR t.numero_terrain LIKE ? OR t.adresse LIKE ? OR t.titre_foncier LIKE ?)'
        params = [f'%{q}%'] * 4
    items = conn.execute(sql + ' ORDER BY t.date_creation DESC', params).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = get_tarifs_module('TNB')
    conn.close()
    return render_template('tnb_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs, q=q)

@bp.route('/tnb/ajouter', methods=['POST'])
@login_required
def tnb_ajouter():
    conn = get_db()
    n = conn.execute('SELECT COUNT(*) as c FROM terrains').fetchone()['c'] + 1
    num = f"TER{datetime.now().year}{n:05d}"
    f = request.form
    conn.execute('''INSERT INTO terrains (numero_terrain,contribuable_id,commune_id,adresse,adresse_ar,
        quartier,arrondissement,superficie,zone,titre_foncier,num_parcelle,statut,date_acquisition)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (num, f['contribuable_id'], f.get('commune_id', 1), f.get('adresse',''), f.get('adresse_ar',''),
         f.get('quartier',''), f.get('arrondissement',''), f.get('superficie', 0), f.get('zone','B'),
         f.get('titre_foncier',''), f.get('num_parcelle',''), f.get('statut','non_bati'), f.get('date_acquisition','')))
    conn.commit(); conn.close()
    flash('Terrain enregistré ✅', 'success')
    return redirect(url_for('tnb.tnb_liste'))

@bp.route('/tnb/<int:id>')
@login_required
def tnb_detail(id):
    user = get_current_user()
    conn = get_db()
    terrain = conn.execute('''SELECT t.*, c.nom, c.prenom, c.raison_sociale, c.cin, c.telephone,
        c.adresse as ctb_adresse, c.numero as ctb_num, c.id as ctb_id
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.id=?''', (id,)).fetchone()
    permis = conn.execute('SELECT * FROM permis WHERE terrain_id=? ORDER BY date_creation DESC', (id,)).fetchall()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="TNB" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    transferts = conn.execute('''SELECT tr.*, c1.nom as ancien_nom, c2.nom as nouveau_nom
        FROM transferts_terrain tr
        LEFT JOIN contribuables c1 ON tr.ancien_contribuable_id=c1.id
        LEFT JOIN contribuables c2 ON tr.nouveau_contribuable_id=c2.id
        WHERE tr.terrain_id=? ORDER BY tr.date_transfert DESC''', (id,)).fetchall()
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale FROM contribuables WHERE actif=1').fetchall()
    tarifs = get_tarifs_module('TNB')
    annees_man = annees_non_payees('TNB', id)
    conn.close()
    return render_template('tnb_detail.html', user=user, terrain=terrain, permis=permis,
        declarations=declarations, transferts=transferts, contribuables=contribuables,
        tarifs=tarifs, annees_manquantes=annees_man, today=date.today().isoformat())

@bp.route('/tnb/<int:id>/modifier', methods=['POST'])
@login_required
def tnb_modifier(id):
    f = request.form
    conn = get_db()
    conn.execute('''UPDATE terrains SET adresse=?,adresse_ar=?,quartier=?,arrondissement=?,
        superficie=?,zone=?,titre_foncier=?,num_parcelle=?,statut=?,date_acquisition=? WHERE id=?''',
        (f.get('adresse'), f.get('adresse_ar',''), f.get('quartier',''), f.get('arrondissement',''),
         f.get('superficie', 0), f.get('zone'), f.get('titre_foncier'), f.get('num_parcelle'),
         f.get('statut'), f.get('date_acquisition'), id))
    conn.commit(); conn.close()
    flash('Terrain modifié ✅', 'success')
    return redirect(url_for('tnb.tnb_detail', id=id))

@bp.route('/tnb/<int:id>/permis', methods=['POST'])
@login_required
def tnb_permis(id):
    f = request.form
    conn = get_db()
    conn.execute('''INSERT INTO permis (terrain_id,type_permis,numero_permis,date_depot,date_delivrance,statut,description)
        VALUES (?,?,?,?,?,?,?)''',
        (id, f['type_permis'], f.get('numero_permis',''), f.get('date_depot',''),
         f.get('date_delivrance',''), f.get('statut','en_cours'), f.get('description','')))
    conn.commit(); conn.close()
    flash('Permis ajouté ✅', 'success')
    return redirect(url_for('tnb.tnb_detail', id=id))

@bp.route('/tnb/<int:id>/transfert', methods=['POST'])
@login_required
def tnb_transfert(id):
    f = request.form
    conn = get_db()
    terrain = conn.execute('SELECT contribuable_id FROM terrains WHERE id=?', (id,)).fetchone()
    if terrain:
        conn.execute('''INSERT INTO transferts_terrain (terrain_id,ancien_contribuable_id,nouveau_contribuable_id,date_transfert,motif,acte_notarie,agent_id)
            VALUES (?,?,?,?,?,?,?)''',
            (id, terrain['contribuable_id'], f['nouveau_contribuable_id'],
             f.get('date_transfert', date.today().isoformat()), f.get('motif',''), f.get('acte_notarie',''), session['user_id']))
        conn.execute('UPDATE terrains SET contribuable_id=? WHERE id=?', (f['nouveau_contribuable_id'], id))
        conn.commit()
    conn.close()
    flash('Transfert effectué ✅', 'success')
    return redirect(url_for('tnb.tnb_detail', id=id))

@bp.route('/tnb/<int:id>/paiement')
@login_required
def tnb_paiement(id):
    user = get_current_user()
    conn = get_db()
    terrain = conn.execute('''SELECT t.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, b.numero_bulletin
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="TNB" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    tarifs = get_tarifs_module('TNB')
    annees_man = annees_non_payees('TNB', id)
    params_tnb = conn.execute("SELECT * FROM parametres_calcul WHERE module='TNB' ORDER BY code").fetchall()
    conn.close()
    return render_template('paiement_module.html', user=user, objet=terrain, module='TNB',
        module_label='Taxe Terrains Urbains Non Bâtis', ref_id=id,
        declarations=declarations, annees_manquantes=annees_man,
        tarifs=tarifs, params=params_tnb, today=date.today().isoformat())
