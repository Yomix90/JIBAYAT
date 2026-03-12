"""
fix_url_for.py — Corrige tous les url_for dans les templates pour les blueprints Flask.
Exécuter UNE SEULE FOIS depuis le dossier JIBAYAT.
"""
import os, re

# Mappings: ancien endpoint → nouveau endpoint blueprint
MAPPINGS = {
    # Contribuables
    "'contribuables'":         "'contribuables.contribuables'",
    "'ajouter_contribuable'":  "'contribuables.ajouter_contribuable'",
    "'modifier_contribuable'": "'contribuables.modifier_contribuable'",
    "'supprimer_contribuable'":"'contribuables.supprimer_contribuable'",
    # TNB
    "'tnb_liste'":    "'tnb.tnb_liste'",
    "'tnb_ajouter'":  "'tnb.tnb_ajouter'",
    "'tnb_detail'":   "'tnb.tnb_detail'",
    "'tnb_modifier'": "'tnb.tnb_modifier'",
    "'tnb_paiement'": "'tnb.tnb_paiement'",
    "'tnb_permis'":   "'tnb.tnb_permis'",
    "'tnb_transfert'":"'tnb.tnb_transfert'",
    # TDB
    "'tdb_liste'":    "'tdb.tdb_liste'",
    "'tdb_ajouter'":  "'tdb.tdb_ajouter'",
    "'tdb_detail'":   "'tdb.tdb_detail'",
    "'tdb_modifier'": "'tdb.tdb_modifier'",
    "'tdb_paiement'": "'tdb.tdb_paiement'",
    # Stationnement
    "'sta_liste'":    "'sta.sta_liste'",
    "'sta_ajouter'":  "'sta.sta_ajouter'",
    "'sta_detail'":   "'sta.sta_detail'",
    "'sta_modifier'": "'sta.sta_modifier'",
    "'sta_paiement'": "'sta.sta_paiement'",
    # Fourrière
    "'fou_liste'":    "'fou.fou_liste'",
    "'fou_ajouter'":  "'fou.fou_ajouter'",
    "'fou_detail'":   "'fou.fou_detail'",
    "'fou_paiement'": "'fou.fou_paiement'",
    # Occupation Domaine Public
    "'odp_liste'":    "'odp.odp_liste'",
    "'odp_ajouter'":  "'odp.odp_ajouter'",
    "'odp_detail'":   "'odp.odp_detail'",
    "'odp_paiement'": "'odp.odp_paiement'",
    # Location Locaux
    "'loc_liste'":    "'loc.loc_liste'",
    "'loc_ajouter'":  "'loc.loc_ajouter'",
    "'loc_detail'":   "'loc.loc_detail'",
    "'loc_paiement'": "'loc.loc_paiement'",
    # Souks
    "'sou_liste'":    "'sou.sou_liste'",
    "'sou_ajouter'":  "'sou.sou_ajouter'",
    "'sou_detail'":   "'sou.sou_detail'",
    "'sou_paiement'": "'sou.sou_paiement'",
    # Config (déjà mis à jour mais au cas où)
    "'rubriques'":         "'config.rubriques'",
    "'arretes_fiscaux'":   "'config.arretes_fiscaux'",
    "'arretes_detail'":    "'config.arretes_detail'",
    "'creer_arrete'":      "'config.creer_arrete'",
    "'ajouter_tarif'":     "'config.ajouter_tarif'",
    "'modifier_tarif'":    "'config.modifier_tarif'",
    "'supprimer_tarif'":   "'config.supprimer_tarif'",
    "'toggle_rubrique'":   "'config.toggle_rubrique'",
    "'modifier_rubrique'": "'config.modifier_rubrique'",
    "'ajouter_rubrique'":  "'config.ajouter_rubrique'",
    "'parametres'":        "'config.parametres'",
    "'modifier_parametres'":"'config.modifier_parametres'",
    # Tarifs (ancienne page)
    "'tarifs'":            "'config.arretes_fiscaux'",
}

templates_dir = 'templates'
fixed = 0

for filename in os.listdir(templates_dir):
    if not filename.endswith('.html'):
        continue
    path = os.path.join(templates_dir, filename)
    content = open(path, encoding='utf-8').read()
    original = content
    for old, new in MAPPINGS.items():
        # Remplace url_for('old') et url_for('old', ...)
        content = re.sub(
            r"url_for\(" + re.escape(old),
            f"url_for({new}",
            content
        )
    if content != original:
        open(path, 'w', encoding='utf-8').write(content)
        fixed += 1
        print(f"  ✅ {filename}")

print(f"\n🎉 {fixed} fichiers corrigés !")
