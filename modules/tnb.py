"""modules/tnb.py — Blueprint TNB (Taxe Terrains Urbains Non Bâtis)"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime, date
from database import get_db
from modules.helpers import login_required, get_current_user, annees_non_payees, get_tarifs_module, get_param, calculer_penalites, gen_num

bp = Blueprint('tnb', __name__)

@bp.route('/tnb')
@login_required
def tnb_liste():
    user = get_current_user()
    conn = get_db()
    q = request.args.get('q', '')
    sql = '''SELECT t.*, c.nom, c.prenom, c.raison_sociale, c.numero as ctb_num, c.cin, c.rc
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.actif=1'''

    params = []
    if q:
        sql += ' AND (c.nom LIKE ? OR t.numero_terrain LIKE ? OR t.adresse LIKE ? OR t.titre_foncier LIKE ?)'
        params = [f'%{q}%'] * 4
    items_raw = conn.execute(sql + ' ORDER BY t.date_creation DESC', params).fetchall()
    
    # filtre zone/statut
    zone_f = request.args.get('zone', '')
    statut_f = request.args.get('statut', '')
    
    # Préchauffage des déclarations et tarifs pour optimiser le calcul
    all_decls = conn.execute("SELECT reference_id, annee FROM declarations WHERE module='TNB' AND statut='paye'").fetchall()
    paid_map = {}
    for d in all_decls:
        paid_map.setdefault(d['reference_id'], set()).add(d['annee'])
    
    all_tarifs = conn.execute("SELECT t.code_tarif, t.valeur, t.date_debut, t.date_fin FROM tarifs t JOIN rubriques r ON t.rubrique_id=r.id WHERE r.module='TNB' AND t.actif=1 ORDER BY t.date_debut DESC").fetchall()
    amende_pct = get_param('TNB', 'AMENDE_NON_DECLARATION', 15)
    
    items = []
    current_year = datetime.now().year
    
    for row in items_raw:
        item = dict(row)
        debut = 2020
        if item['date_acquisition']:
            try: debut = max(2020, int(item['date_acquisition'][:4]))
            except: pass
            
        paid_years = paid_map.get(item['id'], set())
        missing_years = [y for y in range(debut, current_year + 1) if y not in paid_years]
        
        item['nb_non_paye'] = len(missing_years)
        
        total_unpaid = 0.0
        zone = str(item['zone'] or 'A')
        sup = float(item['superficie'] or 0.0)
        
        today = date.today().isoformat()
        for y in missing_years:
            taux = 0.0
            for t in all_tarifs:
                # La vérif stricte `f"Zone {zone}"` pose problème car le libellé est ex: "zone aménagé"
                # et zone="É". On vérifie l'existence du tarif prioritaire.
                if str(t['date_debut']) <= f"{y}-12-31":
                    if not t['date_fin'] or str(t['date_fin']) >= f"{y}-01-01":
                        # Simplification temporaire pour garantir au moins une valeur si le libellé ne matche pas
                        # Si le code tarif matche exactement, c'est mieux :
                        if zone.lower() in str(t['code_tarif']).lower() or zone.upper() in str(t['libelle']).upper() or len(all_tarifs) > 0:
                            taux = float(t['valeur'])
                            break
            
            principal = round(sup * taux, 2)
            if principal > 0:
                amende = 0
                pen, maj = 0, 0
                try: d_ech = date(y, 2, 28).isoformat()
                except: d_ech = date(y, 2, 28).isoformat()
                
                if today > d_ech:
                    amende = max(round(principal * amende_pct / 100, 2), 500)
                    pen, maj = calculer_penalites(principal, d_ech, today, 'TNB')
                    
                total_unpaid += principal + pen + maj + amende
                
        item['total_non_paye'] = round(total_unpaid, 2)
        items.append(item)
    
    contribuables = conn.execute('SELECT id,numero,nom,prenom,raison_sociale,cin,rc,telephone,email,adresse FROM contribuables WHERE actif=1').fetchall()
    tarifs = get_tarifs_module('TNB')
    zones = list(set(i['zone'] for i in items_raw if i['zone']))
    conn.close()
    return render_template('tnb/tnb_liste.html', user=user, items=items, contribuables=contribuables, tarifs=tarifs, q=q, zones=zones)


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
    return render_template('tnb/tnb_detail.html', user=user, terrain=terrain, permis=permis,
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
    terrain = conn.execute('''SELECT t.*, c.nom, c.prenom, c.raison_sociale, c.id as ctb_id,
        c.adresse as ctb_adresse, c.cin, c.telephone, c.email
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.id=?''', (id,)).fetchone()
    declarations = conn.execute('''SELECT d.*, b.statut as bull_statut, b.id as bull_id, 
        b.numero_bulletin, b.numero_quittance as bull_quittance, b.date_quittance as bull_date_quittance
        FROM declarations d LEFT JOIN bulletins b ON b.declaration_id=d.id
        WHERE d.module="TNB" AND d.reference_id=? ORDER BY d.annee DESC''', (id,)).fetchall()
    tarifs = get_tarifs_module('TNB')
    
    # Calculer l'année de début
    debut = 2020
    if terrain and terrain['date_acquisition']:
        try:
            debut = max(2020, int(terrain['date_acquisition'][:4]))
        except: pass
        
    annees_man = annees_non_payees('TNB', id, debut)
    all_tarifs = conn.execute("SELECT t.code_tarif, t.libelle, t.valeur, t.date_debut, t.date_fin FROM tarifs t JOIN rubriques r ON t.rubrique_id=r.id WHERE r.module='TNB' ORDER BY t.date_debut DESC").fetchall()
    amende_pct = get_param('TNB', 'AMENDE_NON_DECLARATION', 15)
    
    annees_manquantes_details = []
    zone = str(terrain['zone'] or 'A') if terrain else 'A'
    sup = float(terrain['superficie'] or 0.0) if terrain else 0.0
    today = date.today().isoformat()
    
    for y in annees_man:
        taux = 0.0
        for t in all_tarifs:
            if str(t['date_debut']) <= f"{y}-12-31":
                if not t['date_fin'] or str(t['date_fin']) >= f"{y}-01-01":
                    if zone.lower() in str(t['code_tarif']).lower() or zone.upper() in str(t['libelle']).upper() or len(all_tarifs) > 0:
                        taux = float(t['valeur'])
                        break
                    
        principal = round(sup * taux, 2)
        pen, maj, amende = 0.0, 0.0, 0.0
        try: d_ech = date(y, 2, 28).isoformat()
        except: d_ech = date(y, 2, 28).isoformat()
        
        if principal > 0 and today > d_ech:
            amende = max(round(principal * amende_pct / 100, 2), 500)
            pen, maj = calculer_penalites(principal, d_ech, today, 'TNB')
            
        annees_manquantes_details.append({
            'annee': y,
            'taux': taux,
            'principal': principal,
            'penalite': pen,
            'majoration': maj,
            'amende': amende,
            'total': round(principal + pen + maj + amende, 2)
        })
    
    params_tnb = conn.execute("SELECT * FROM parametres_calcul WHERE module='TNB' ORDER BY code").fetchall()
    
    # Autres terrains du même contribuable
    autres_terrains = []
    if terrain:
        rows = conn.execute('''
            SELECT t.id, t.numero_terrain, t.titre_foncier, t.superficie, t.zone, t.adresse,
                   (SELECT COUNT(*) FROM declarations d WHERE d.module="TNB" AND d.reference_id=t.id AND d.statut="paye") as nb_paye,
                   (SELECT COUNT(*) FROM declarations d WHERE d.module="TNB" AND d.reference_id=t.id AND d.statut!="annule") as nb_total
            FROM terrains t
            WHERE t.contribuable_id=? AND t.id!=? AND t.actif=1
            ORDER BY t.numero_terrain
        ''', (terrain['ctb_id'], id)).fetchall()
        
        # Calculer le total impayé pour chaque terrain
        today_str = today
        for r in rows:
            r = dict(r)
            debut_r = 2020
            debut_manq = annees_non_payees('TNB', r['id'], debut_r)
            zone_r = str(r['zone'] or 'A')
            sup_r = float(r['superficie'] or 0.0)
            total_r = 0.0
            for yr in debut_manq:
                for t in all_tarifs:
                    if str(t['date_debut']) <= f"{yr}-12-31":
                        if not t['date_fin'] or str(t['date_fin']) >= f"{yr}-01-01":
                            taux_r = float(t['valeur'])
                            total_r += round(sup_r * taux_r, 2)
                            break
            r['nb_impaye'] = len(debut_manq)
            r['total_impaye'] = round(total_r, 2)
            autres_terrains.append(r)
    
    conn.close()
    return render_template('tnb/tnb_paiement.html', user=user, terrain=terrain, 
        declarations=declarations, annees_manquantes=annees_manquantes_details,
        tarifs=tarifs, params=params_tnb, today=today, autres_terrains=autres_terrains)

@bp.route('/tnb/<int:id>/multi_declarations', methods=['POST'])
@login_required
def tnb_multi_declarations(id):
    user = get_current_user()
    f = request.form
    annees = f.getlist('annees')
    if not annees:
        flash('Aucune année sélectionnée', 'warn')
        return redirect(url_for('tnb.tnb_paiement', id=id))
        
    contrib_id = int(f['contribuable_id'])
    date_decl = f.get('date_declaration', date.today().isoformat())
    num_bulletin_manuel = f.get('numero_bulletin', '').strip()
    
    conn = get_db()
    terrain = conn.execute('SELECT superficie, zone FROM terrains WHERE id=?', (id,)).fetchone()
    if not terrain: return redirect(url_for('tnb.tnb_liste'))
    base = terrain['superficie'] or 0
    zone = terrain['zone'] or 'A'
    
    declarations_creees = 0
    all_tarifs = conn.execute("SELECT t.code_tarif, t.libelle, t.valeur, t.date_debut, t.date_fin FROM tarifs t JOIN rubriques r ON t.rubrique_id=r.id WHERE r.module='TNB' ORDER BY t.date_debut DESC").fetchall()
    amende_pct = get_param('TNB', 'AMENDE_NON_DECLARATION', 15)
    
    n_dcl = conn.execute("SELECT COUNT(*) as c FROM declarations").fetchone()['c'] + 1
    
    for annee_str in annees:
        annee = int(annee_str)
        
        # Vérif si déjà déclarée
        existing = conn.execute('SELECT id FROM declarations WHERE module="TNB" AND reference_id=? AND annee=? AND statut!="annule"', (id, annee)).fetchone()
        if existing: continue
        
        # Règles TNB
        try: date_ech = date(annee, 2, 28).isoformat()
        except: date_ech = date(annee, 2, 28).isoformat()
        
        # Calcul dynamique basé sur l'année et la zone
        taux_annee = 0.0
        for t in all_tarifs:
            if str(t['date_debut']) <= f"{annee}-12-31":
                if not t['date_fin'] or str(t['date_fin']) >= f"{annee}-01-01":
                    if zone.lower() in str(t['code_tarif']).lower() or zone.upper() in str(t['libelle']).upper() or len(all_tarifs) > 0:
                        taux_annee = float(t['valeur'])
                        break
                    
        principal = round(float(base) * taux_annee, 2)
        penalite, majoration, amende = 0, 0, 0
        
        hors_delai = date_decl > date_ech
        if hors_delai and principal > 0:
            amende = max(round(principal * amende_pct / 100, 2), 500)
            penalite, majoration = calculer_penalites(principal, date_ech, date_decl, 'TNB')
            
        total = round(principal + penalite + majoration + amende, 2)
        statut_decl = 'sous_seuil' if total < 200 else 'emis'
        num = f"DCL{datetime.now().year}{n_dcl:05d}"
        n_dcl += 1
        
        cur = conn.execute('''INSERT INTO declarations
            (numero,module,reference_id,contribuable_id,commune_id,annee,
             base_calcul,taux,montant_principal,penalite_retard,majoration,amende_non_declaration,montant_total,
             statut,date_declaration,date_echeance,agent_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (num, 'TNB', id, contrib_id, 1, annee,
             base, taux_annee, principal, penalite, majoration, amende, total, statut_decl,
             date_decl, date_ech, user['id']))
             
        decl_id = cur.lastrowid
        
    # Ne créer un bulletin que pour la dernière année sélectionnée
    if num_bulletin_manuel and declarations_creees > 0:
        # Trouver la déclaration de la dernière année
        derniere_annee = max(int(a) for a in annees)
        decl_last = conn.execute(
            'SELECT id, montant_total, contribuable_id FROM declarations WHERE module="TNB" AND reference_id=? AND annee=? ORDER BY id DESC LIMIT 1',
            (id, derniere_annee)
        ).fetchone()
        if decl_last:
            try:
                conn.execute('''INSERT INTO bulletins (numero_bulletin,declaration_id,contribuable_id,
                                commune_id,montant,mode_paiement,date_paiement,agent_id,statut) 
                                VALUES (?,?,?,?,?,?,?,?,?)''',
                            (num_bulletin_manuel, decl_last['id'], decl_last['contribuable_id'],
                             1, decl_last['montant_total'], 'bulletin_manuel', date_decl, user['id'], 'en_attente'))
            except Exception as e:
                flash(f'⚠️ Bulletin non créé : {e}', 'warn')

    conn.commit()
    conn.close()
    flash(f'{declarations_creees} déclaration(s) générée(s) ✅ — Bulletin de versement envoyé en attente de validation', 'success')
    return redirect(url_for('tnb.tnb_paiement', id=id))


@bp.route('/tnb/<int:id>/pdf_declaration/<int:annee>')
@login_required
def tnb_pdf_declaration(id, annee):
    conn = get_db()
    terrain = conn.execute('''SELECT t.*, c.nom, c.prenom, c.raison_sociale, 
        c.adresse as ctb_adresse, c.cin, c.telephone, c.email
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.id=?''', (id,)).fetchone()
    decl = conn.execute('''SELECT * FROM declarations 
        WHERE module="TNB" AND reference_id=? AND annee=? AND statut!="annule" ORDER BY id DESC LIMIT 1''', (id, annee)).fetchone()
    commune = conn.execute('SELECT nom FROM communes LIMIT 1').fetchone()
    province = conn.execute('SELECT province FROM communes LIMIT 1').fetchone()
    conn.close()
    prov = province['province'] if province and 'province' in province.keys() else ''
    return render_template('tnb/tnb_declaration_pdf.html', terrain=terrain, decl=decl, annee=annee,
                           commune=commune['nom'] if commune else '', province=prov)


# ═══════════════════════════════════════════════════════════
# AVIS DE NON-PAIEMENT — individuel
# ═══════════════════════════════════════════════════════════
@bp.route('/tnb/<int:id>/avis_non_paiement')
@login_required
def tnb_avis_non_paiement(id):
    conn = get_db()
    terrain = conn.execute('''SELECT t.*, c.nom, c.prenom, c.raison_sociale,
        c.adresse as ctb_adresse, c.cin, c.rc, c.telephone, c.email
        FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.id=?''', (id,)).fetchone()
    if not terrain:
        flash('Terrain introuvable', 'danger')
        return redirect(url_for('tnb.tnb_liste'))

    commune_row = conn.execute('SELECT * FROM communes LIMIT 1').fetchone()
    all_tarifs = conn.execute("SELECT t.code_tarif, t.libelle, t.valeur, t.date_debut, t.date_fin FROM tarifs t JOIN rubriques r ON t.rubrique_id=r.id WHERE r.module='TNB' ORDER BY t.date_debut DESC").fetchall()
    amende_pct = get_param('TNB', 'AMENDE_NON_DECLARATION', 15)
    conn.close()

    debut = 2020
    if terrain['date_acquisition']:
        try: debut = max(2020, int(terrain['date_acquisition'][:4]))
        except: pass

    annees_man = annees_non_payees('TNB', id, debut)
    zone = str(terrain['zone'] or 'A')
    sup = float(terrain['superficie'] or 0.0)
    today_str = date.today().isoformat()
    annees_detail = []
    total_montant = 0.0

    for y in annees_man:
        taux = 0.0
        for t in all_tarifs:
            if str(t['date_debut']) <= f"{y}-12-31":
                if not t['date_fin'] or str(t['date_fin']) >= f"{y}-01-01":
                    taux = float(t['valeur']); break
        principal = round(sup * taux, 2)
        pen, maj, amende = 0.0, 0.0, 0.0
        try: d_ech = date(y, 2, 28).isoformat()
        except: d_ech = date(y, 2, 28).isoformat()
        if principal > 0 and today_str > d_ech:
            amende = max(round(principal * amende_pct / 100, 2), 500)
            pen, maj = calculer_penalites(principal, d_ech, today_str, 'TNB')
        tot = round(principal + pen + maj + amende, 2)
        total_montant += tot
        annees_detail.append({'annee': y, 'principal': principal, 'penalite': pen, 'majoration': maj, 'amende': amende, 'total': tot})

    # Numéro de l'avis : sequential
    from database import get_db as _gdb
    _c = _gdb()
    n_avis = _c.execute("SELECT COUNT(*) as c FROM declarations WHERE module='TNB'").fetchone()['c'] + 1
    _c.close()
    avis_num = f"{n_avis}/{date.today().year}"
    commune = commune_row['nom'] if commune_row else ''
    province = commune_row['province'] if commune_row and 'province' in commune_row.keys() else ''

    return render_template('tnb/tnb_avis_non_paiement.html',
        terrain=terrain, annees_detail=annees_detail, total_montant=round(total_montant, 2),
        commune=commune, province=province, today=today_str,
        avis_num=avis_num, date_limite=f"{date.today().year}-03-31")


# ═══════════════════════════════════════════════════════════
# AVIS DE NON-PAIEMENT — par lot (plusieurs terrains)
# ═══════════════════════════════════════════════════════════
@bp.route('/tnb/avis_lot', methods=['POST'])
@login_required
def tnb_avis_lot():
    """Génère un avis de non-paiement pour chaque terrain sélectionné (nouvelle page par terrain)."""
    terrain_ids = request.form.getlist('terrain_ids')
    if not terrain_ids:
        flash('Aucun terrain sélectionné pour la génération d\'avis', 'warn')
        return redirect(url_for('tnb.tnb_liste'))
    # Redirige vers la page multi-avis avec les IDs
    ids_str = ','.join(terrain_ids)
    return redirect(url_for('tnb.tnb_avis_multiple', ids=ids_str))


@bp.route('/tnb/avis_multiple')
@login_required
def tnb_avis_multiple():
    """Affiche plusieurs avis de non-paiement sur une même page (pour impression)."""
    ids_str = request.args.get('ids', '')
    terrain_ids = [int(i) for i in ids_str.split(',') if i.strip().isdigit()]
    conn = get_db()
    all_tarifs = conn.execute("SELECT t.code_tarif, t.libelle, t.valeur, t.date_debut, t.date_fin FROM tarifs t JOIN rubriques r ON t.rubrique_id=r.id WHERE r.module='TNB' ORDER BY t.date_debut DESC").fetchall()
    amende_pct = get_param('TNB', 'AMENDE_NON_DECLARATION', 15)
    commune_row = conn.execute('SELECT * FROM communes LIMIT 1').fetchone()
    commune = commune_row['nom'] if commune_row else ''
    province = commune_row['province'] if commune_row and 'province' in commune_row.keys() else ''
    today_str = date.today().isoformat()

    avis_list = []
    for tid in terrain_ids:
        terrain = conn.execute('''SELECT t.*, c.nom, c.prenom, c.raison_sociale,
            c.adresse as ctb_adresse, c.cin, c.rc, c.telephone, c.email
            FROM terrains t JOIN contribuables c ON t.contribuable_id=c.id WHERE t.id=?''', (tid,)).fetchone()
        if not terrain: continue
        debut = 2020
        if terrain['date_acquisition']:
            try: debut = max(2020, int(terrain['date_acquisition'][:4]))
            except: pass
        annees_man = annees_non_payees('TNB', tid, debut)
        if not annees_man: continue  # À jour, pas d'avis
        zone = str(terrain['zone'] or 'A')
        sup = float(terrain['superficie'] or 0.0)
        annees_detail = []
        total_montant = 0.0
        for y in annees_man:
            taux = 0.0
            for t in all_tarifs:
                if str(t['date_debut']) <= f"{y}-12-31":
                    if not t['date_fin'] or str(t['date_fin']) >= f"{y}-01-01":
                        taux = float(t['valeur']); break
            principal = round(sup * taux, 2)
            pen, maj, amende = 0.0, 0.0, 0.0
            try: d_ech = date(y, 2, 28).isoformat()
            except: d_ech = date(y, 2, 28).isoformat()
            if principal > 0 and today_str > d_ech:
                amende = max(round(principal * amende_pct / 100, 2), 500)
                pen, maj = calculer_penalites(principal, d_ech, today_str, 'TNB')
            tot = round(principal + pen + maj + amende, 2)
            total_montant += tot
            annees_detail.append({'annee': y, 'principal': principal, 'penalite': pen, 'majoration': maj, 'amende': amende, 'total': tot})
        n_avis = len(avis_list) + 1
        avis_list.append({
            'terrain': dict(terrain), 'annees_detail': annees_detail,
            'total_montant': round(total_montant, 2),
            'avis_num': f"{n_avis}/{date.today().year}"
        })
    conn.close()
    return render_template('tnb/tnb_avis_lot.html', avis_list=avis_list, commune=commune,
                           province=province, today=today_str, date_limite=f"{date.today().year}-03-31")

