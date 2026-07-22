#!/usr/bin/env python3
"""
mail_parser.py — Extrait les paramètres d'une réclamation Tunisie Telecom.
Gère les formats réels de réclamations (DA, volume, date, CRM, MSISDN, etc.)
"""

import re
from datetime import datetime, timedelta


def extract_params_from_email(email_text):
    """
    Extrait tous les paramètres d'une réclamation Tunisie Telecom.
    Gère le format réaliste : DA, volume, date, MSISDN, CRM, etc.

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

    # ── 2. DA (numéro de compte dédié / dédié data) ──
    da_match = re.search(r'\bDA(\d+\w*)\b', email_text)
    if da_match:
        params['da'] = da_match.group(1)

    # ── 3. Volume de data (ex: 4 Go, 500 Mo, 1 GB) ──
    volume_match = re.search(r'(\d+)\s*(Go|GB|Mo|MB|Ko|KB)', email_text)
    if volume_match:
        params['volume'] = f"{volume_match.group(1)} {volume_match.group(2)}"

    # ── 4. Date (formats variés : JJ/MM/AAAA, AAAA-MM-JJ, etc.) ──
    # Format "le JJ/MM/AAAA"
    date_match3 = re.search(r'(?i)le\s+(\d{1,2}/\d{2}/\d{4})\b', email_text)
    # Format JJ/MM/AAAA seul
    date_match1 = re.search(r'\b(\d{1,2}/\d{2}/\d{4})\b', email_text)
    # Format AAAA-MM-JJ (période : du 2026-06-01 au 2026-06-15)
    date_match2 = re.findall(r'\b(\d{4}-\d{2}-\d{2})\b', email_text)

    if date_match3:
        raw_date = date_match3.group(1)
        parts = raw_date.split('/')
        params['date_debut'] = f"{parts[2]}-{parts[1]}-{parts[0]}"
    elif date_match1:
        raw_date = date_match1.group(1)
        parts = raw_date.split('/')
        params['date_debut'] = f"{parts[2]}-{parts[1]}-{parts[0]}"
    elif date_match2:
        if len(date_match2) >= 2:
            params['date_debut'] = date_match2[0]
            params['date_fin'] = date_match2[-1]
        elif len(date_match2) == 1:
            params['date_debut'] = date_match2[0]

    # Si seulement date_debut est trouvée, on ajoute +15 jours par défaut
    if 'date_debut' in params and 'date_fin' not in params:
        try:
            d = datetime.strptime(params['date_debut'], "%Y-%m-%d") + timedelta(days=15)
            params['date_fin'] = d.strftime("%Y-%m-%d")
        except ValueError:
            pass

    # ── 5. CRM / Numéro de ticket ──
    crm_match = re.search(r'(?i)CRM\s*[:\s]*([-\d\w]+)', email_text)
    if crm_match:
        params['crm'] = crm_match.group(1)

    # ── 6. Type de réclamation (mot-clé) ──
    email_lower = email_text.lower()
    recl_types = {
        'expiration': 'DATA_EXPIRATION',
        'data expir': 'DATA_EXPIRATION',
        'volume expir': 'DATA_EXPIRATION',
        'solde a dimin': 'BALANCE_DEDUCTION',
        'solde a baiss': 'BALANCE_DEDUCTION',
        'débit': 'BALANCE_DEDUCTION',
        'déduit': 'BALANCE_DEDUCTION',
        'dédution': 'BALANCE_DEDUCTION',
        'consommation': 'CONSUMPTION',
        'data mobile': 'DATA_CONSUMPTION',
        'forfait data': 'DATA_CONSUMPTION',
        'forfait internet': 'DATA_CONSUMPTION',
        'sos': 'SOS_REMBOURSE',
        'crédit d\'urgence': 'SOS_REMBOURSE',
        'crédit sos': 'SOS_REMBOURSE',
        'service que je ne reconnais': 'VAS_UNKNOWN',
        'service que je ne reconnais': 'VAS_UNKNOWN',
        'vas': 'VAS_UNKNOWN',
        'service premium': 'VAS_UNKNOWN',
    }

    for keyword, recl_type in recl_types.items():
        if keyword.lower() in email_lower:
            params['reclamation_type'] = recl_type
            break
    else:
        params['reclamation_type'] = 'UNKNOWN'

    return params


# ── Test ──
if __name__ == "__main__":
    # Test 1 : Format réel Tunisie Telecom (expiration data)
    test_email1 = """Bonjour,

Le client teneur de la ligne numéro 21694197397 réclame l'expiration de son FF data comme suit :

-          Balance concerné : DA7
-          Volume expiré : 4 Go
-          Date : le 02/07/2026

Merci de vérifier.

CRM : 1-53034679076

Cordialement"""

    print("=" * 60)
    print("TEST 1 : Réclamation d'expiration de FF data")
    print("=" * 60)
    params1 = extract_params_from_email(test_email1)
    for key, value in params1.items():
        print(f"  {key}: {value}")

    # Test 2 : Format déduction de solde
    test_email2 = """Bonjour,

Je suis client Tunisie Telecom au numéro 21697865660.
J'ai remarqué que mon solde a diminué de 15.00 DT sur la période
du 2026-06-01 au 2026-06-15 sans que j'en sois informé.

Pouvez-vous m'expliquer cette déduction ?

Cordialement"""

    print("\n" + "=" * 60)
    print("TEST 2 : Réclamation de déduction de solde")
    print("=" * 60)
    params2 = extract_params_from_email(test_email2)
    for key, value in params2.items():
        print(f"  {key}: {value}")

    # Test 3 : Consommation data
    test_email3 = """Mon forfait data a été consommé rapidement. Numéro 21651234567.
Entre le 2026-06-01 et le 2026-06-30, j'ai perdu beaucoup de data.
Pouvez-vous vérifier ?"""

    print("\n" + "=" * 60)
    print("TEST 3 : Réclamation de consommation data")
    print("=" * 60)
    params3 = extract_params_from_email(test_email3)
    for key, value in params3.items():
        print(f"  {key}: {value}")
