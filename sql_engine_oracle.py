#!/usr/bin/env python3
"""
sql_engine_oracle.py — Moteur de diagnostic SQL pour les réclamations Tunisie Telecom.
Connecte à une base Oracle classique via python-oracledb (mode Thin).

Tables utilisées :
  1. RD_T_UC_USSD_SOS_CDR_DET       (SOS Remboursement)
  2. RD_T_UC_CCN_RO_GPRS_CDR_DETAIL (Voice/SMS/Data)
  3. RD_T_UC_OCCPP_DATA_DT          (Data mobile OCCPP)
  4. RD_T_UC_OCCPP_SMS_VAS_DT       (SMS VAS)
  5. RD_T_UC_USSD_CDR_DETAILS       (USSD CDR - bonus)
"""

import oracledb
import json
from config_oracle import ORACLE_CONFIG


def get_connection():
    """Établit la connexion à la base Oracle."""
    try:
        dsn = oracledb.makedsn(
            host=ORACLE_CONFIG["host"],
            port=ORACLE_CONFIG["port"],
            service_name=ORACLE_CONFIG["service_name"]
        )
        conn = oracledb.connect(
            user=ORACLE_CONFIG["user"],
            password=ORACLE_CONFIG["password"],
            dsn=dsn
        )
        print("  ✓ Connexion à la base Oracle réussie.")
        return conn
    except Exception as e:
        print(f"  ✗ ERREUR DE CONNEXION ORACLE : {e}")
        return None


def execute_query(conn, query, **kwargs):
    cursor = conn.cursor()
    if kwargs:
        cursor.execute(query, kwargs)
    else:
        cursor.execute(query)
    columns = [desc[0] for desc in cursor.description] if cursor.description else []
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    cursor.close()
    return rows


# ── ÉTAPE 1 : SOS Remboursement ──
def check_sos_rembourse(conn, msisdn, date_debut, date_fin):
    """
    Vérifie si le débit correspond à un remboursement SOS.
    Table : RD_T_UC_USSD_SOS_CDR_DET
    Condition : EVENT_TYPE='REV' AND EVENT_STATUS='CVAS_DEBIT_SOLDE'
    """
    query = """
    SELECT CHARGE_AMOUNT, DA_AMOUNT, MAIN_DEB_AMOUNT, START_DATE,
           EVENT_TYPE, EVENT_STATUS, SUBSCRIBER_TYPE, SERVICE_ID,
           A_MSISDN, LOANADJUSTMENT, LOANLEFT, FEEADJUSTMENT,
           FEELEFT, FEE, LOAN_ID, EVENT_ID, CREDIT_DATE,
           NE, TYPE_SOS, FILENAME, START_HOUR
    FROM RD_T_UC_USSD_SOS_CDR_DET
    WHERE A_MSISDN = :msisdn
      AND START_DATE BETWEEN TO_DATE(:debut, 'YYYY-MM-DD')
                         AND TO_DATE(:fin, 'YYYY-MM-DD')
    """

    rows = execute_query(conn, query, msisdn=msisdn, debut=date_debut, fin=date_fin)

    for row in rows:
        if row.get('EVENT_TYPE') == 'REV' and row.get('EVENT_STATUS') == 'CVAS_DEBIT_SOLDE':
            return {
                'diagnostic': 'SOS_REMBOURSE',
                'table': 'RD_T_UC_USSD_SOS_CDR_DET',
                'total_amount': float(row.get('CHARGE_AMOUNT', 0)),
                'loan_adjustment': float(row.get('LOANADJUSTMENT', 0)),
                'loan_left': float(row.get('LOANLEFT', 0)),
                'num_records': len(rows),
                'results': rows
            }

    return None


# ── ÉTAPE 2 : Voice/SMS (CDR classique) ──
def check_voice_sms(conn, msisdn, date_debut, date_fin):
    """
    Vérifie si le débit correspond à des appels ou SMS.
    Table : RD_T_UC_CCN_RO_GPRS_CDR_DETAIL
    Condition : CALL_TYPE IN ('VOICE','SMS') AND SUM(GE_AMOUNT) > 0
    """
    query = """
    SELECT A_MSISDN, B_MSISDN, CALL_TYPE, GE_AMOUNT, EVENT_TYPE,
           START_DATE, START_HOUR, SUBSCRIBER_TYPE, PARTNER, COUNTRY,
           EVENT_DURATION, MAIN_VALUE_BEFORE, MAIN_VALUE_AFTER,
           DA_VALUE_AFTER, DA_VALUE_BEFORE, DA_VALUE,
           SERVICE_TYPE, TRAFFIC_TYPE, PORTABILITY_FLAG, NE
    FROM RD_T_UC_CCN_RO_GPRS_CDR_DETAIL
    WHERE A_MSISDN = :msisdn
      AND START_DATE BETWEEN TO_DATE(:debut, 'YYYY-MM-DD')
                         AND TO_DATE(:fin, 'YYYY-MM-DD')
      AND CALL_TYPE IN ('VOICE', 'SMS')
    """

    rows = execute_query(conn, query, msisdn=msisdn, debut=date_debut, fin=date_fin)

    if rows:
        total = sum(float(r.get('GE_AMOUNT') or 0) for r in rows)
        if total > 0:
            return {
                'diagnostic': 'CONSOMMATION_NORMALE',
                'subtype': 'VOICE_SMS',
                'table': 'RD_T_UC_CCN_RO_GPRS_CDR_DETAIL',
                'total_amount': float(total),
                'num_operations': len(rows),
                'results': rows
            }

    return None


# ── ÉTAPE 3 : Data Mobile (OCCPP) ──
def check_data(conn, msisdn, date_debut, date_fin):
    """
    Vérifie si le débit correspond à de la data mobile.
    Table : RD_T_UC_OCCPP_DATA_DT
    Condition : CALL_TYPE='DATA' AND SUM(DATA_VOLUME) > 0
    """
    query = """
    SELECT A_MSISDN, B_MSISDN, START_DATE, START_HOUR,
           APN, CALL_TYPE, EVENT_TYPE, CHARGING_ID, SERVICE_ID,
           SUBSCRIBER_TYPE, ROAMING_TYPE, PARTNER,
           EVENT_COUNT, DATA_VOLUME, EVENT_DURATION,
           CHARGE_AMOUNT, FILTER_CODE, KEYWORD,
           DA_AMOUNT_CALC, MA_AMNT_CALC, ORIG_START_TIME
    FROM RD_T_UC_OCCPP_DATA_DT
    WHERE A_MSISDN = :msisdn
      AND START_DATE BETWEEN TO_DATE(:debut, 'YYYY-MM-DD')
                         AND TO_DATE(:fin, 'YYYY-MM-DD')
      AND CALL_TYPE = 'DATA'
    """

    rows = execute_query(conn, query, msisdn=msisdn, debut=date_debut, fin=date_fin)

    if rows:
        total_volume = sum(float(r.get('DATA_VOLUME') or 0) for r in rows)
        if total_volume > 0:
            total_amount = sum(float(r.get('CHARGE_AMOUNT') or 0) for r in rows)
            total_volume_display = f"{total_volume / 1048576:.1f} Go" if total_volume > 1048576 else f"{total_volume / 1024:.0f} Mo"
            return {
                'diagnostic': 'CONSOMMATION_NORMALE',
                'subtype': 'DATA',
                'table': 'RD_T_UC_OCCPP_DATA_DT',
                'total_volume_kb': float(total_volume),
                'total_volume_display': total_volume_display,
                'total_amount': float(total_amount),
                'num_sessions': len(rows),
                'results': rows
            }

    return None


# ── ÉTAPE 4 : SMS VAS (OCCPP) ──
def check_vas(conn, msisdn, date_debut, date_fin):
    """
    Vérifie si le débit correspond à des services VAS (SMS premium).
    Table : RD_T_UC_OCCPP_SMS_VAS_DT
    """
    query = """
    SELECT A_MSISDN, B_MSISDN, START_DATE, START_HOUR,
           APN, CALL_TYPE, EVENT_TYPE, CHARGING_ID, SERVICE_ID,
           SUBSCRIBER_TYPE, ROAMING_TYPE, PARTNER,
           EVENT_COUNT, DATA_VOLUME, EVENT_DURATION,
           CHARGE_AMOUNT, FILTER_CODE, KEYWORD,
           DA_AMOUNT_CALC, MA_AMNT_CALC, ORIG_START_TIME
    FROM RD_T_UC_OCCPP_SMS_VAS_DT
    WHERE A_MSISDN = :msisdn
      AND START_DATE BETWEEN TO_DATE(:debut, 'YYYY-MM-DD')
                         AND TO_DATE(:fin, 'YYYY-MM-DD')
    """

    rows = execute_query(conn, query, msisdn=msisdn, debut=date_debut, fin=date_fin)

    if rows:
        total_amount = sum(float(r.get('CHARGE_AMOUNT') or 0) for r in rows)
        keywords = list(set(r.get('KEYWORD', '') for r in rows if r.get('KEYWORD')))
        return {
            'diagnostic': 'CONSOMMATION_NORMALE',
            'subtype': 'VAS',
            'table': 'RD_T_UC_OCCPP_SMS_VAS_DT',
            'total_amount': float(total_amount),
            'keywords': keywords,
            'num_services': len(rows),
            'results': rows
        }

    return None


# ── ÉTAPE 5 : USSD CDR (bonus - vérification supplémentaire) ──
def check_ussd(conn, msisdn, date_debut, date_fin):
    """
    Vérifie les opérations USSD (bonus).
    Table : RD_T_UC_USSD_CDR_DETAILS
    """
    query = """
    SELECT A_MSISDN, B_MSISDN, SERVICE_CODE, START_DATE, START_HOUR,
           RECORD_TYPE, EVENT_STATUS, CHARGE_AMOUNT, EVENT_TYPE,
           CALL_TYPE, SUBSCRIBER_TYPE, DA_AMOUNT, CANAL,
           TOP_UP_ACCOUNT_ID, TOP_UP_AMOUNT, SERVICE_CLASS_ID,
           FILENAME, NE, FILTER_CODE, TRAFFIC_TYPE
    FROM RD_T_UC_USSD_CDR_DETAILS
    WHERE A_MSISDN = :msisdn
      AND START_DATE BETWEEN TO_DATE(:debut, 'YYYY-MM-DD')
                         AND TO_DATE(:fin, 'YYYY-MM-DD')
    """

    rows = execute_query(conn, query, msisdn=msisdn, debut=date_debut, fin=date_fin)

    if rows:
        total_amount = sum(float(r.get('CHARGE_AMOUNT') or 0) for r in rows)
        return {
            'diagnostic': 'CONSOMMATION_NORMALE',
            'subtype': 'USSD',
            'table': 'RD_T_UC_USSD_CDR_DETAILS',
            'total_amount': float(total_amount),
            'num_operations': len(rows),
            'results': rows
        }

    return None


# ── MOTEUR PRINCIPAL ──
def run_diagnostic(msisdn, date_debut, date_fin, **kwargs):
    """
    Exécute la hiérarchie de diagnostic complète sur la base Oracle.
    Amélioré : cherche toutes les causes possibles et les combine.
    
    Si un montant signalé par le client est fourni, le moteur continue
    à chercher dans les autres tables tant que le total trouvé est
    insuffisant pour expliquer le montant réclamé.
    
    Args:
        msisdn: Numéro de téléphone
        date_debut: Date de début
        date_fin: Date de fin
        da: Numéro DA (optionnel)
        volume: Volume signalé (optionnel)
        montant: Montant signalé par le client en DT (optionnel)
    """
    client_montant = kwargs.get('montant', None)
    
    conn = get_connection()
    if not conn:
        return {
            'diagnostic': 'ERREUR_SQL',
            'table': '—',
            'results': [],
            'note': 'Impossible de se connecter à la base Oracle.'
        }

    try:
        # Collecter TOUTES les causes trouvées dans toutes les tables
        all_diagnostics = []
        total_found = 0.0

        # Étape 1 : SOS Remboursement
        print(f"  → Vérification de la table SOS (RD_T_UC_USSD_SOS_CDR_DET)...")
        result = check_sos_rembourse(conn, msisdn, date_debut, date_fin)
        if result:
            all_diagnostics.append(result)
            total_found += result.get('total_amount', 0)
            print(f"    ✓ SOS trouvé : {result['total_amount']} DT")

        # Étape 2 : Voice/SMS
        print(f"  → Vérification de la table Voice/SMS (RD_T_UC_CCN_RO_GPRS_CDR_DETAIL)...")
        result = check_voice_sms(conn, msisdn, date_debut, date_fin)
        if result:
            all_diagnostics.append(result)
            total_found += result.get('total_amount', 0)
            print(f"    ✓ Voice/SMS trouvé : {result['total_amount']} DT")

        # Étape 3 : Data
        print(f"  → Vérification de la table Data (RD_T_UC_OCCPP_DATA_DT)...")
        result = check_data(conn, msisdn, date_debut, date_fin)
        if result:
            all_diagnostics.append(result)
            total_found += result.get('total_amount', 0)
            print(f"    ✓ Data trouvé : {result['total_amount']} DT")

        # Étape 4 : VAS
        print(f"  → Vérification de la table VAS (RD_T_UC_OCCPP_SMS_VAS_DT)...")
        result = check_vas(conn, msisdn, date_debut, date_fin)
        if result:
            all_diagnostics.append(result)
            total_found += result.get('total_amount', 0)
            print(f"    ✓ VAS trouvé : {result['total_amount']} DT")

        # Étape 5 : USSD (bonus)
        print(f"  → Vérification de la table USSD (RD_T_UC_USSD_CDR_DETAILS)...")
        result = check_ussd(conn, msisdn, date_debut, date_fin)
        if result:
            all_diagnostics.append(result)
            total_found += result.get('total_amount', 0)
            print(f"    ✓ USSD trouvé : {result['total_amount']} DT")

        # ── Analyse des résultats combinés ──
        conn.close()

        if not all_diagnostics:
            print(f"  → Aucune correspondance trouvée dans les 5 tables.")
            return {
                'diagnostic': 'INDETERMINE',
                'table': '—',
                'results': [],
                'note': 'Aucune opération trouvée dans les 5 tables pour cette période.',
                'causes_found': [],
                'total_found': 0.0,
                'client_montant': client_montant,
            }

        # Si on a des résultats, déterminer le diagnostic principal
        # Priorité : SOS_REMBOURSE > CONSOMMATION_NORMALE
        primary_diagnostic = 'INDETERMINE'
        primary_table = '—'
        
        # Chercher un SOS d'abord (c'est la cause la plus spécifique)
        sos_results = [d for d in all_diagnostics if d['diagnostic'] == 'SOS_REMBOURSE']
        if sos_results:
            primary_diagnostic = 'SOS_REMBOURSE'
            primary_table = sos_results[0]['table']
        else:
            primary_diagnostic = 'CONSOMMATION_NORMALE'
            primary_table = all_diagnostics[0]['table']

        # Calculer le total de toutes les sources
        total_amount = total_found
        subtypes = [d.get('subtype', 'UNKNOWN') for d in all_diagnostics]
        
        # Vérifier si le montant trouvé couvre le montant réclamé
        coverage = None
        if client_montant and client_montant > 0:
            coverage = total_amount / client_montant
            if coverage < 0.5:
                print(f"  ⚠ ATTENTION : Montant trouvé ({total_found:.2f} DT) < 50% du montant réclamé ({client_montant} DT)")
            elif coverage < 1.0:
                print(f"  ⚠ ATTENTION : Montant trouvé ({total_found:.2f} DT) < montant réclamé ({client_montant} DT)")
            else:
                print(f"  ✓ Montant trouvé ({total_found:.2f} DT) couvre le montant réclamé ({client_montant} DT)")

        # Combiner tous les résultats
        combined_results = {
            'diagnostic': primary_diagnostic,
            'table': primary_table,
            'total_amount': float(total_amount),
            'num_causes': len(all_diagnostics),
            'subtypes': subtypes,
            'coverage_ratio': round(coverage, 2) if coverage else None,
            'client_montant': client_montant,
            'causes': all_diagnostics,
        }

        # Ajouter les données de chaque cause
        for i, cause in enumerate(all_diagnostics):
            combined_results[f'cause_{i+1}'] = {
                'diagnostic': cause['diagnostic'],
                'subtype': cause.get('subtype', 'UNKNOWN'),
                'table': cause['table'],
                'total_amount': cause.get('total_amount', 0),
                'num_records': len(cause.get('results', [])),
                'results': cause.get('results', [])
            }

        print(f"  → {len(all_diagnostics)} cause(s) trouvée(s), total : {total_amount:.2f} DT")
        return combined_results

    except Exception as e:
        print(f"  ✗ Erreur critique dans le moteur SQL : {e}")
        try:
            conn.close()
        except:
            pass
        return {
            'diagnostic': 'ERREUR_SQL',
            'table': '—',
            'results': [],
            'note': f'Erreur interne : {str(e)}'
        }


# ── TEST ──
if __name__ == "__main__":
    print("=" * 60)
    print("TEST DE CONNEXION ORACLE")
    print("=" * 60)
    result = run_diagnostic("21694197397", "2026-07-02", "2026-07-17")
    print(f"\nDiagnostic : {result['diagnostic']}")
    if result.get('table') and result['table'] != '—':
        print(f"Table : {result['table']}")
    if result.get('total_amount'):
        print(f"Montant : {result['total_amount']} DT")
    if result.get('total_volume_display'):
        print(f"Volume : {result['total_volume_display']}")
