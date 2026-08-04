#!/usr/bin/env python3
"""
mail_parser.py — Extrait les paramètres d'une réclamation Tunisie Telecom.
Corrigé pour gérer :
  - Format "entre le JJ/MM et JJ/MM/AAAA"
  - DA complet (ex: DA4, DA7)
  - Montant (ex: 50 DT)
"""

import re
from datetime import datetime, timedelta


def extract_params_from_email(email_text):
    """
    Extrait tous les paramètres d'une réclamation Tunisie Telecom.

    Args:
        email_text: Le texte brut de l'e-mail de réclamation

    Returns:
        dict: Dictionnaire contenant les paramètres extraits
    """
    params = {}

    # ── 1. MSISDN (numéro tunisien : 216 + 8 chiffres) ──
    msisdn_match = re.search(r'(\b216\d{8}\b)', email_text)
    if msisdn_match:
        params['msisdn'] = msisdn_match.group(1)

    # ── 2. DA complet (ex: DA4, DA7, DA12) ──
    # Cherche "DA" suivi de chiffres, précédé d'un espace ou du début de ligne
    da_match = re.search(r'(?<![A-Za-z])(DA\d+\w*)\b', email_text)
    if da_match:
        params['da'] = da_match.group(1)  # Capture "DA4", "DA7", etc.

    # ── 3. Volume de data (ex: 4 Go, 500 Mo, 1 GB) ──
    volume_match = re.search(r'(\d+)\s*(Go|GB|Mo|MB|Ko|KB)', email_text)
    if volume_match:
        params['volume'] = f"{volume_match.group(1)} {volume_match.group(2)}"

    # ── 4. Montant signalé (ex: 50 DT, 15.00 DT) ──
    montant_match = re.search(r'(\d+[.,]?\d*)\s*DT\b', email_text)
    if montant_match:
        params['montant'] = float(montant_match.group(1).replace(',', '.'))

    # ── 5. Date (formats variés) ──

    # Format "entre le JJ/MM et JJ/MM/AAAA"
    date_range_match = re.search(
        r'(?i)entre\s+le\s+(\d{1,2}/\d{2})\s+et\s+(\d{1,2}/\d{2}/\d{4})',
        email_text
    )
    if date_range_match:
        raw_debut = date_range_match.group(1)
        raw_fin = date_range_match.group(2)
        # Extraire l'année de la date de fin
        year = raw_fin.split('/')[2]
        # Convertir JJ/MM → YYYY-MM-DD
        parts_debut = raw_debut.split('/')
        parts_fin = raw_fin.split('/')
        params['date_debut'] = f"{year}-{parts_debut[1]}-{parts_debut[0].zfill(2)}"
        params['date_fin'] = f"{year}-{parts_fin[1]}-{parts_fin[0].zfill(2)}"
        # Fermer la fonction ici car on a trouvé le format complet
        # Mais on continue pour extraire les autres champs
    else:
        # Format "le JJ/MM/AAAA"
        date_match3 = re.search(r'(?i)le\s+(\d{1,2}/\d{2}/\d{4})\b', email_text)
        if date_match3:
            raw_date = date_match3.group(1)
            parts = raw_date.split('/')
            params['date_debut'] = f"{parts[2]}-{parts[1]}-{parts[0].zfill(2)}"
        # Format JJ/MM/AAAA seul
        elif re.search(r'\b\d{1,2}/\d{2}/\d{4}\b', email_text):
            raw_date = re.search(r'\b(\d{1,2}/\d{2}/\d{4})\b', email_text).group(1)
            parts = raw_date.split('/')
            params['date_debut'] = f"{parts[2]}-{parts[1]}-{parts[0].zfill(2)}"
        # Format AAAA-MM-JJ
        date_match2 = re.findall(r'\b(\d{4}-\d{2}-\d{2})\b', email_text)
        if date_match2:
            params['date_debut'] = date_match2[0]
            if len(date_match2) >= 2:
                params['date_fin'] = date_match2[-1]

    # Si seulement date_debut est trouvée, on ajoute +15 jours par défaut
    if 'date_debut' in params and 'date_fin' not in params:
        try:
            d = datetime.strptime(params['date_debut'], "%Y-%m-%d") + timedelta(days=15)
            params['date_fin'] = d.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # ── 6. CRM / Numéro de ticket ──
    crm_match = re.search(r'(?i)(?:CRM|N.\s*CRM)\s*[:\s]*([-\d\w]+)', email_text)
    if crm_match:
        params['crm'] = crm_match.group(1)

    # ── 7. Type de réclamation (mot-clé) ──
    email_lower = email_text.lower()
    recl_types = [
        ('expiration du forfait', 'BALANCE_EXPIRATION'),
        ('expiration de son ff', 'DATA_EXPIRATION'),
        ('expiration', 'DATA_EXPIRATION'),
        ('volume expir', 'DATA_EXPIRATION'),
        ('data expir', 'DATA_EXPIRATION'),
        ('solde a dimin', 'BALANCE_DEDUCTION'),
        ('solde a baiss', 'BALANCE_DEDUCTION'),
        ('montant expir', 'BALANCE_EXPIRATION'),
        ('debit', 'BALANCE_DEDUCTION'),
        ('deduit', 'BALANCE_DEDUCTION'),
        ('consommation', 'CONSUMPTION'),
        ('forfait data', 'DATA_CONSUMPTION'),
        ('forfait internet', 'DATA_CONSUMPTION'),
        ('sos', 'SOS_REMBOURSE'),
        ('credit d\'urgence', 'SOS_REMBOURSE'),
        ('service que je ne reconnais', 'VAS_UNKNOWN'),
        ('vas', 'VAS_UNKNOWN'),
    ]

    for keyword, recl_type in recl_types:
        if keyword.lower() in email_lower:
            params['reclamation_type'] = recl_type
            break
    else:
        params['reclamation_type'] = 'UNKNOWN'

    return params


# ── Test ──
if __name__ == "__main__":
    # Test 1 : Réclamation Voix avec "entre le JJ/MM et JJ/MM/AAAA"
    test_email1 = """Bonjour,

Le client teneur de la ligne numéro 21699077434 réclame l'expiration du forfait Voix comme suit.

-          Balance concerné : DA4
-          Montant expiré : 50 DT
-          Date d'expiration : entre le 28/06 et 29/06/2026

Merci de vérifier.

N° CRM : 1-53032674216"""

    print("=" * 60)
    print("TEST 1 : Réclamation Voix (entre le JJ/MM et JJ/MM/AAAA)")
    print("=" * 60)
    params1 = extract_params_from_email(test_email1)
    for key, value in params1.items():
        print(f"  {key}: {value}")

    # Test 2 : Réclamation Data avec "le JJ/MM/AAAA"
    test_email2 = """Bonjour,

Le client teneur de la ligne numéro 21694197397 réclame l'expiration de son FF data comme suit :

-          Balance concerné : DA7
-          Volume expiré : 4 Go
-          Date : le 02/07/2026

Merci de vérifier.

CRM : 1-53034679076"""

    print("\n" + "=" * 60)
    print("TEST 2 : Réclamation Data (le JJ/MM/AAAA)")
    print("=" * 60)
    params2 = extract_params_from_email(test_email2)
    for key, value in params2.items():
        print(f"  {key}: {value}")

    # Test 3 : Réclamation déduction solde
    test_email3 = """Bonjour,

Je suis client Tunisie Telecom au numéro 21697865660.
J'ai remarqué que mon solde a diminué de 15.00 DT sur la période
du 2026-06-01 au 2026-06-15 sans que j'en sois informé.

Cordialement"""

    print("\n" + "=" * 60)
    print("TEST 3 : Réclamation déduction solde")
    print("=" * 60)
    params3 = extract_params_from_email(test_email3)
    for key, value in params3.items():
        print(f"  {key}: {value}")
