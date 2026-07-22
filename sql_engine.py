import random
import json

def run_diagnostic_simulation(msisdn, date_debut, date_fin, **kwargs):
    da = kwargs.get('da', None)
    volume_client = kwargs.get('volume', None)

    print(f"  -> Vérification de la table SOS (RD_T_UC_USSD_SOS_CDR_DET)...")
    if random.random() < 0.2:
        amount = round(random.choice([5.00, 10.00, 15.00, 20.00]), 2)
        return {
            'diagnostic': 'SOS_REMBOURSE',
            'table': 'RD_T_UC_USSD_SOS_CDR_DET',
            'results': [{
                'EVENT_TYPE': 'REV',
                'EVENT_STATUS': 'CVAS_DEBIT_SOLDE',
                'CHARGE_AMOUNT': amount,
                'DA_AMOUNT': amount,
                'LOANADJUSTMENT': amount,
                'LOANLEFT': 0.00,
                'A_MSISDN': msisdn,
                'START_DATE': f"{date_debut} 10:00:00",
                'LOAN_ID': f'LOAN_{random.randint(10000, 99999)}'
            }]
        }

    print(f"  -> Vérification de la table Voice/SMS (RD_T_UC_CCN_RO_GPRS_CDR_DETAIL)...")
    if random.random() < 0.3:
        num_ops = random.randint(2, 10)
        total = round(random.uniform(5, 50), 2)
        return {
            'diagnostic': 'CONSOMMATION_NORMALE',
            'subtype': 'VOICE_SMS',
            'table': 'RD_T_UC_CCN_RO_GPRS_CDR_DETAIL',
            'total_amount': total,
            'num_operations': num_ops,
            'results': [{
                'A_MSISDN': msisdn,
                'CALL_TYPE': random.choice(['VOICE', 'SMS']),
                'GE_AMOUNT': round(total / num_ops, 2),
                'START_DATE': f"{date_debut} {random.randint(8,18)}:00:00",
            }] * num_ops
        }

    print(f"  -> Vérification de la table Data (RD_T_UC_SASNPP_DATA_DT)...")
    if random.random() < 0.35:
        num_ops = random.randint(1, 8)
        total_amount = round(random.uniform(0, 20), 2)
        total_volume_kb = random.randint(500000, 4000000)
        return {
            'diagnostic': 'CONSOMMATION_NORMALE',
            'subtype': 'DATA',
            'table': 'RD_T_UC_SASNPP_DATA_DT',
            'total_volume_kb': total_volume_kb,
            'total_volume_display': f"{total_volume_kb / 1048576:.1f} Go" if total_volume_kb > 1048576 else f"{total_volume_kb / 1024:.0f} Mo",
            'total_amount': total_amount,
            'num_sessions': num_ops,
            'results': [{
                'MSISDN': msisdn,
                'START_DATE': f"{date_debut} {random.randint(8,22)}:00:00",
                'APN': random.choice(['internet', 'web', 'tunisiap']),
                'CALL_TYPE': 'DATA',
                'ROAMING_TYPE': random.choice(['NATIONAL', 'INTERNATIONAL']),
                'DATA_VOLUME': total_volume_kb // num_ops,
                'CHARGE_AMOUNT': round(total_amount / num_ops, 2),
            }] * num_ops
        }

    print(f"  -> Vérification de la table VAS (RD_T_UC_OCCPP_SMS_VAS_DT)...")
    if random.random() < 0.15:
        amount = round(random.choice([1.00, 2.00, 3.00, 5.00]), 2)
        keywords = random.sample(['SONR1', 'SONR2', 'GAM1', 'GAM2', 'APP1', 'SMS_PREM'], 2)
        return {
            'diagnostic': 'CONSOMMATION_NORMALE',
            'subtype': 'VAS',
            'table': 'RD_T_UC_OCCPP_SMS_VAS_DT',
            'total_amount': amount,
            'keywords': keywords,
            'results': [{
                'A_MSISDN': msisdn,
                'CALL_TYPE': 'VAS',
                'KEYWORD': keywords[0],
                'CHARGE_AMOUNT': amount,
            }]
        }

    print(f"  -> Aucune correspondance trouvée dans les tables standards.")
    return {
        'diagnostic': 'INDETERMINE',
        'table': '—',
        'results': [],
        'note': 'Aucune opération trouvée dans les tables standards pour cette période.'
    }
