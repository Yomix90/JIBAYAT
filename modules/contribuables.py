"""modules/contribuables.py — Blueprint Contribuables"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user

bp = Blueprint('contribuables', __name__)

@bp.route('/contribuables')
@login_required
def contribuables():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q', '')
    sql = '''SELECT c.*, com.nom as commune_nom FROM contribuables c
        LEFT JOIN communes com ON c.commune_id=com.id WHERE c.actif=1'''
    params = []
    if q:
        sql += ' AND (c.nom LIKE ? OR c.prenom LIKE ? OR c.numero LIKE ? OR c.raison_sociale LIKE ? OR c.cin LIKE ? OR c.nom_ar LIKE ?)'
        params = [f'%{q}%'] * 6
    items = conn.execute(sql + ' ORDER BY c.date_creation DESC', params).fetchall()
    communes = conn.execute('SELECT * FROM communes WHERE actif=1').fetchall()
    conn.close()
    return render_template('contribuables/contribuables.html', user=user, items=items, communes=communes, q=q)

@bp.route('/contribuables/ajouter', methods=['GET', 'POST'])
@login_required
def ajouter_contribuable():
    user = get_current_user()
    conn = get_db()
    communes = conn.execute('SELECT * FROM communes WHERE actif=1').fetchall()
    if request.method == 'POST':
        n = conn.execute('SELECT COUNT(*) as c FROM contribuables').fetchone()['c'] + 1
        num = f"CTB{datetime.now().year}{n:06d}"
        f = request.form
        conn.execute('''INSERT INTO contribuables
            (numero,type_personne,nom,prenom,nom_ar,prenom_ar,raison_sociale,raison_sociale_ar,
            cin,ice,rc,adresse,adresse_ar,ville,code_postal,telephone,email,commune_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (num, f.get('type_personne','physique'), f.get('nom',''), f.get('prenom',''),
             f.get('nom_ar',''), f.get('prenom_ar',''), f.get('raison_sociale',''), f.get('raison_sociale_ar',''),
             f.get('cin',''), f.get('ice',''), f.get('rc',''),
             f.get('adresse',''), f.get('adresse_ar',''), f.get('ville',''), f.get('code_postal',''),
             f.get('telephone',''), f.get('email',''), f.get('commune_id', 1)))
        conn.commit(); conn.close()
        flash('Contribuable ajouté ✅', 'success')
        return redirect(url_for('contribuables.contribuables'))
    conn.close()
    return render_template('contribuables/ajouter_contribuable.html', user=user, communes=communes)

@bp.route('/contribuables/<int:id>/modifier', methods=['GET', 'POST'])
@login_required
def modifier_contribuable(id):
    user = get_current_user()
    conn = get_db()
    contrib = conn.execute('SELECT * FROM contribuables WHERE id=?', (id,)).fetchone()
    communes = conn.execute('SELECT * FROM communes WHERE actif=1').fetchall()
    if request.method == 'POST':
        f = request.form
        conn.execute('''UPDATE contribuables SET type_personne=?,nom=?,prenom=?,nom_ar=?,prenom_ar=?,
            raison_sociale=?,raison_sociale_ar=?,cin=?,ice=?,rc=?,adresse=?,adresse_ar=?,
            ville=?,code_postal=?,telephone=?,email=?,commune_id=? WHERE id=?''',
            (f.get('type_personne'), f.get('nom'), f.get('prenom'), f.get('nom_ar',''), f.get('prenom_ar',''),
             f.get('raison_sociale'), f.get('raison_sociale_ar',''), f.get('cin'), f.get('ice'), f.get('rc'),
             f.get('adresse'), f.get('adresse_ar',''), f.get('ville'), f.get('code_postal',''),
             f.get('telephone'), f.get('email'), f.get('commune_id'), id))
        conn.commit(); conn.close()
        flash('Contribuable modifié ✅', 'success')
        return redirect(url_for('contribuables.contribuables'))
    conn.close()
    return render_template('contribuables/modifier_contribuable.html', user=user, contrib=contrib, communes=communes)

@bp.route('/contribuables/<int:id>/supprimer', methods=['POST'])
@login_required
def supprimer_contribuable(id):
    user = get_current_user()
    if user['peut_supprimer']:
        conn = get_db()
        conn.execute('UPDATE contribuables SET actif=0 WHERE id=?', (id,))
        conn.commit(); conn.close()
    return redirect(url_for('contribuables.contribuables'))
