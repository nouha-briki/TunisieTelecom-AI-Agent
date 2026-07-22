#!/usr/bin/env python3
"""
Générateur de données d'entraînement étendu pour le modèle Qwen.
Produit un dataset plus large (1000+ exemples) avec plus de variété
dans les réclamations clients et les données SQL.
"""

import json
import random
from datetime import datetime, timedelta

NUM_SAMPLES = 500
OUTPUT_FILE = "training_data_large.jsonl"

# ── Templates de réclamations par type ──

RECLAMATION_TEMPLATES = {
    "SOS_REMBOURSE": [
        "Bonjour, mon solde a diminué de {amount:.2f} DT sans que j'en sois informé. Mon numéro est le {msisdn}. Pouvez-vous m'expliquer cette déduction ?",
        "J'ai remarqué une baisse de mon solde de {amount:.2f} DT sur la période du {debut} au {fin}. Je n'ai pas fait d'opération consciente. Numéro : {msisdn}",
        "Pourquoi mon solde a baissé de {amount:.2f} DT ? Je suis le client {msisdn}. Je n'ai pas demandé de crédit SOS récemment.",
        "Mon solde a diminué brutalement. Au téléphone {msisdn}, entre le {debut} et le {fin}, j'ai perdu {amount:.2f} DT. C'est une erreur !",
        "Je n'ai pas compris la déduction de {amount:.2f} DT sur mon numéro {msisdn}. Période : {debut} - {fin}. Merci de vérifier.",
        "Au numéro {msisdn}, mon solde a baissé de {amount:.2f} DT sans notification. Est-ce normal ?",
        "Bonjour service client, je constate une perte de {amount:.2f} DT sur mon compte. Msidsn {msisdn}. Entre le {debut} et le {fin}.",
    ],
    "VOICE_SMS": [
        "Bonjour, mon solde a baissé de {amount:.2f} DT. Numéro {msisdn}. Pouvez-vous me donner le détail de ma consommation ?",
        "Je ne comprends pas ma consommation entre le {debut} et le {fin}. Mon solde a diminué de {amount:.2f} DT. Msisdn : {msisdn}",
        "J'ai été débité de {amount:.2f} DT sur mon compte. Numéro {msisdn}. Pouvez-vous vérifier mes appels et SMS ?",
        "Mon solde a diminué. Je suis le {msisdn}. Veuillez me fournir le détail des opérations sur la période du {debut} au {fin}.",
        "Pourquoi j'ai été débité de {amount:.2f} DT ? Numéro {msisdn}. Période {debut} - {fin}. J'aimerais le détail.",
        "Mon forfait prépayé a diminué de {amount:.2f} DT. Msidsn {msisdn}. Pouvez-vous me donner le breakdown ?",
        "J'ai constaté une consommation anormale sur le {msisdn} entre le {debut} et le {fin}. Montant : {amount:.2f} DT.",
        "Bonjour, au numéro {msisdn}, mon solde a baissé de {amount:.2f} DT. Je voudrais comprendre pourquoi.",
    ],
    "DATA": [
        "Mon forfait data a été consommé rapidement. Numéro {msisdn}. Entre le {debut} et le {fin}, j'ai perdu beaucoup de data.",
        "Je remarque une consommation excessive de data sur mon numéro {msisdn}. Période : {debut} - {fin}.",
        "Bonjour, j'ai consommé beaucoup de data entre le {debut} et le {fin}. Numéro {msisdn}. Pouvez-vous m'expliquer ?",
        "Ma consommation data semble anormale. Msisdn {msisdn}. Période {debut} à {fin}.",
        "Mon crédit internet a été consommé très vite. Numéro {msisdn}. Du {debut} au {fin}. Est-ce normal ?",
        "J'ai utilisé mon forfait data en quelques jours. Msidsn {msisdn}. Période {debut} - {fin}. Pouvez-vous vérifier ?",
        "Au téléphone {msisdn}, ma data mobile a été consommée rapidement entre le {debut} et le {fin}. Pourquoi ?",
    ],
    "VAS": [
        "Bonjour, j'ai été débité de {amount:.2f} DT pour un service que je ne reconnais pas. Numéro {msisdn}. Période {debut} - {fin}.",
        "Je n'ai pas souscrit à un service premium, pourtant j'ai été débité de {amount:.2f} DT. Numéro : {msisdn}. Dates : {debut} à {fin}.",
        "Mon solde a baissé de {amount:.2f} DT à cause d'un service VAS. Numéro {msisdn}. Pouvez-vous vérifier ?",
        "Je n'ai pas demandé de contenu premium. Débit de {amount:.2f} DT sur le {msisdn}. Entre le {debut} et le {fin}.",
        "Quel service a consommé {amount:.2f} DT sur mon numéro {msisdn} ? Période : {debut} - {fin}.",
        "Bonjour, je ne reconnais pas un débit de {amount:.2f} DT sur le {msisdn}. Période {debut} à {fin}. Merci de vérifier.",
        "Un service inconnu a débité mon compte de {amount:.2f} DT. Msidsn {msisdn}. Du {debut} au {fin}.",
    ],
    "INDETERMINE": [
        "Bonjour, mon solde a diminué de {amount:.2f} DT et je ne comprends pas pourquoi. Numéro {msisdn}. Période : {debut} - {fin}.",
        "J'ai perdu {amount:.2f} DT sur mon compte sans raison apparente. Msidsn : {msisdn}. Du {debut} au {fin}.",
        "Mon solde a baissé inexplicablement. Numéro {msisdn}. Entre le {debut} et le {fin}, débit de {amount:.2f} DT constaté.",
        "Je ne trouve pas l'origine d'un débit de {amount:.2f} DT. Numéro {msisdn}. Période {debut} - {fin}.",
        "Au numéro {msisdn}, j'ai perdu {amount:.2f} DT sans explication entre le {debut} et le {fin}.",
        "Bonjour, mon crédit a diminué de {amount:.2f} DT. Msidsn {msisdn}. Du {debut} au {fin}. Aidez-moi s'il vous plaît.",
    ],
}

# ── Templates de réponses par type ──

RESPONSE_TEMPLATES = {
    "SOS_REMBOURSE": [
        "Diagnostic : SOS_REMBOURSE\n\nLe client a utilisé un crédit SOS (crédit d'urgence) qui a été remboursé automatiquement lors de sa dernière recharge.\n\nDétails :\n- Table interrogée : RD_T_UC_USSD_SOS_CDR_DET\n- MSISDN : {msisdn}\n- Période : du {debut} au {fin}\n- Montant du remboursement SOS : {amount:.2f} DT\n- Type d'événement : REV (remboursement) avec statut CVAS_DEBIT_SOLDE\n\nCause probable : Le client a bénéficié d'un crédit SOS (ADV = avance accordée) qui a été prélevé automatiquement (REV = remboursement) lors de la prochaine recharge. Le client perçoit cela comme une expiration brusque, mais c'est un remboursement normal.\n\nRecommandation : Informer le client que le débit correspond au remboursement d'un crédit SOS qu'il a précédemment utilisé. Le montant de {amount:.2f} DT a été ajusté via LOANADJUSTMENT. Le LOANLEFT est désormais à 0.00 DT, confirmant que le prêt SOS a été entièrement remboursé.",
        "Diagnostic : SOS_REMBOURSE\n\nAnalyse : Débit SOS remboursé automatiquement.\n\nExplication client : Bonjour, le montant de {amount:.2f} DT constaté sur votre solde correspond au remboursement automatique d'un crédit SOS (crédit d'urgence) que vous avez précédemment utilisé. Ce remboursement est effectué lors de votre prochaine recharge conformément aux conditions du service.\n\nDétails techniques :\n- MSISDN : {msisdn}\n- Période : {debut} au {fin}\n- Table source : RD_T_UC_USSD_SOS_CDR_DET\n- EVENT_TYPE : REV (remboursement)\n- LOAN_ID : {loan_id}\n\nRecommandation : Confirmer au client la légitimité du débit et lui rappeler les conditions du crédit SOS.",
    ],
    "VOICE_SMS": [
        "Diagnostic : CONSOMMATION_NORMALE\n\nLe solde a été consommé par des appels vocaux et/ou des SMS.\n\nDétails :\n- Table interrogée : RD_T_UC_CCN_RO_GPRS_CDR_DETAIL\n- MSISDN : {msisdn}\n- Période : du {debut} au {fin}\n- Montant total consommé : {amount:.2f} DT\n- Nombre d'opérations : {num_ops}\n\nCause probable : Consommation normale d'appels et/ou de SMS. Le tarif de chaque opération est enregistré dans GE_AMOUNT (en DT). Les colonnes CALL_TYPE permettent de distinguer les appels vocaux (VOICE) des messages SMS.\n\nRecommandation : Fournir au client le détail des appels et SMS avec les montants facturés. Vérifier les colonnes CALL_TYPE, START_DATE, START_HOUR, GE_AMOUNT, B_MSISDN (destinataire) et PARTNER (opérateur du destinataire).",
        "Diagnostic : CONSOMMATION_NORMALE\n\nExplication client : Bonjour, la diminution de {amount:.2f} DT sur votre solde correspond à votre consommation normale d'appels et de SMS durant la période du {debut} au {fin}. {num_ops} opérations ont été enregistrées.\n\nDétails techniques :\n- MSISDN : {msisdn}\n- Table : RD_T_UC_CCN_RO_GPRS_CDR_DETAIL\n- CALL_TYPE : VOICE et/ou SMS\n- Montant total : {amount:.2f} DT\n\nRecommandation : Transmettre au client le relevé détaillé de ses appels et SMS.",
    ],
    "DATA": [
        "Diagnostic : CONSOMMATION_NORMALE\n\nLe solde a été consommé par de la data mobile (internet).\n\nDétails :\n- Table interrogée : RD_T_UC_SASNPP_DATA_DT\n- MSISDN : {msisdn}\n- Période : du {debut} au {fin}\n- Montant total facturé : {amount:.2f} DT\n- Nombre de sessions : {num_ops}\n\nCause probable : Consommation normale de data mobile. Le volume internet est enregistré dans DATA_VOLUME (en Ko) et le montant dans CHARGE_AMOUNT. Le type de roaming (ROAMING_TYPE) indique si la consommation est nationale ou internationale.\n\nRecommandation : Fournir au client le détail de ses sessions data avec les volumes consommés et les montants correspondants. Vérifier les colonnes START_DATE, DATA_VOLUME, CHARGE_AMOUNT, APN et ROAMING_TYPE. Si le roaming est international, informer le client des tarifs spécifiques.",
        "Diagnostic : CONSOMMATION_NORMALE\n\nExplication client : Bonjour, la consommation de {amount:.2f} DT constatée sur votre ligne {msisdn} correspond à {num_ops} sessions de data mobile entre le {debut} et le {fin}. Le volume total consommé est enregistré dans la table RD_T_UC_SASNPP_DATA_DT.\n\nDétails techniques :\n- Table : RD_T_UC_SASNPP_DATA_DT\n- CALL_TYPE : DATA\n- Volume total : variable selon les sessions\n- Montant total : {amount:.2f} DT\n\nRecommandation : Envoyer au client le détail de ses sessions data et lui rappeler les tarifs applicables.",
    ],
    "VAS": [
        "Diagnostic : CONSOMMATION_NORMALE\n\nLe solde a été consommé par des services VAS (Value Added Services).\n\nDétails :\n- Table interrogée : RD_T_UC_OCCPP_SMS_VAS_DT\n- MSISDN : {msisdn}\n- Période : du {debut} au {fin}\n- Montant total VAS : {amount:.2f} DT\n- Services utilisés : {keywords}\n\nCause probable : Débits liés à des services à valeur ajoutée (contenus premium, jeux, sonneries, etc.). Le mot-clé du service VAS est enregistré dans KEYWORD. Le montant facturé est dans CHARGE_AMOUNT, réparti entre le DA (DA_AMOUNT_CALC) et le compte principal (MA_AMNT_CALC).\n\nRecommandation : Fournir au client le détail des services VAS utilisés et les montants facturés. Proposer la désinscription des services non souhaités. Vérifier les colonnes KEYWORD, SERVICE_ID, CHARGE_AMOUNT, DA_AMOUNT_CALC et MA_AMNT_CALC.",
        "Diagnostic : CONSOMMATION_NORMALE\n\nExplication client : Bonjour, le débit de {amount:.2f} DT sur votre numéro {msisdn} correspond à des services à valeur ajoutée (VAS) utilisés entre le {debut} et le {fin}. Les services identifiés sont : {keywords}.\n\nDétails techniques :\n- Table : RD_T_UC_OCCPP_SMS_VAS_DT\n- CALL_TYPE : VAS\n- Nombre d'événements : variable\n- Montant total : {amount:.2f} DT\n\nRecommandation : Expliquer au client les services VAS activés et proposer la désactivation de ceux qui ne sont pas souhaités.",
    ],
    "INDETERMINE": [
        "Diagnostic : INDETERMINE\n\nAucune des conditions de diagnostic n'a été satisfaite.\n\nDétails :\n- MSISDN : {msisdn}\n- Période : du {debut} au {fin}\n- Montant constaté : {amount:.2f} DT\n- Tables vérifiées : RD_T_UC_USSD_SOS_CDR_DET, RD_T_UC_CCN_RO_GPRS_CDR_DETAIL, RD_T_UC_SASNPP_DATA_DT, RD_T_UC_OCCPP_SMS_VAS_DT\n\nCause probable : Impossible de déterminer la source exacte du débit à partir des tables standards.\n\nRecommandation : Escalader vers un agent humain pour investigation approfondie. Vérifier éventuellement les tables complémentaires (facturation, promotions, ajustements manuels, etc.). Informer le client que son dossier est pris en charge.",
        "Diagnostic : INDETERMINE\n\nExplication client : Bonjour, nous avons vérifié votre numéro {msisdn} pour la période du {debut} au {fin} mais nous n'avons pas pu identifier la source exacte du débit de {amount:.2f} DT dans nos tables standards.\n\nDétails techniques :\n- Tables vérifiées : 4 tables principales (SOS, Voice/SMS, Data, VAS)\n- Aucune opération correspondant au débit n'a été trouvée\n\nRecommandation : Escalade nécessaire vers un agent humain. Le dossier sera examiné par le service facturation.",
    ],
}

# ── Données aléatoires ──

MSISDN_POOL = [f"216{random.randint(20,99)}{random.randint(1000000,9999999)}" for _ in range(50)]
SUBSCRIBER_TYPES = ["HYB", "PREPAID", "POSTPAID"]
PARTNERS = ["TUNTT", "FRTEL", "VODAF", "ORNGE", "ALTEL", "ZAINK"]
COUNTRIES = ["TN", "FR", "MA", "DZ", "LY", "SA", "AE", "GB", "DE", "IT"]
ROAMING_TYPES = ["NATIONAL", "INTERNATIONAL"]
APNS = ["internet", "web", "tunisiap", "wap", "mms"]
KEYWORDS = ["APP1", "APP2", "SONR1", "SONR2", "GAM1", "GAM2", "SMS_PREM", "NEWS_TT", "RINGTON_1", "GAME_X"]
TARIFFS_SOS = [5.00, 7.00, 10.00, 12.00, 15.00, 20.00, 25.00]
TARIFFS_VOICE = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00, 5.00]
TARIFFS_SMS = [0.02, 0.05, 0.10, 0.15, 0.20]
TARIFFS_DATA = [0.05, 0.10, 0.25, 0.50, 1.00, 1.50, 2.00, 3.00, 5.00, 10.00, 15.00, 25.00]
TARIFFS_VAS = [0.50, 1.00, 1.50, 2.00, 3.00, 5.00, 7.00, 10.00, 15.00, 20.00]
DATA_VOLUMES = [100, 500, 1000, 5000, 10000, 50000, 100000, 250000, 500000, 1000000]


SYSTEM_PROMPT = (
    "Vous êtes un assistant IA spécialisé dans l'automatisation des réponses aux réclamations "
    "clients de Tunisie Telecom. Votre rôle est d'analyser les réclamations reçues par email "
    "et les données SQL extraites de la base de connaissances Oracle pour diagnostiquer la "
    "cause probable du problème et formuler une réponse professionnelle.\n\n"
    "La base de connaissances contient 4 tables Oracle principales :\n"
    "1. RD_T_UC_USSD_SOS_CDR_DET — Événements SOS (crédit d'urgence) : types ADV (avance) et REV (remboursement)\n"
    "2. RD_T_UC_CCN_RO_GPRS_CDR_DETAIL — CDR voix et SMS : colonnes CALL_TYPE, GE_AMOUNT, START_DATE\n"
    "3. RD_T_UC_SASNPP_DATA_DT — CDR data mobile : colonnes DATA_VOLUME, CHARGE_AMOUNT, SERVICE_ID\n"
    "4. RD_T_UC_OCCPP_SMS_VAS_DT — SMS+ et services VAS : colonnes KEYWORD, CHARGE_AMOUNT, SERVICE_ID\n\n"
    "Hiérarchie de diagnostic :\n"
    "1. Vérifier RD_T_UC_USSD_SOS_CDR_DET : si EVENT_TYPE='REV' et EVENT_STATUS='CVAS_DEBIT_SOLDE' → SOS_REMBOURSE\n"
    "2. Vérifier RD_T_UC_CCN_RO_GPRS_CDR_DETAIL : si CALL_TYPE IN ('VOICE','SMS') et SUM(GE_AMOUNT) > 0 → CONSOMMATION_NORMALE\n"
    "3. Vérifier RD_T_UC_SASNPP_DATA_DT : si CALL_TYPE='DATA' et SUM(DATA_VOLUME) > 0 → CONSOMMATION_NORMALE\n"
    "4. Si aucune condition satisfaite → INDETERMINE (escalade humaine)\n\n"
    "Répondez toujours de manière professionnelle, claire et empathique. Fournissez le diagnostic, "
    "les détails techniques, et une recommandation d'action."
)


def pick_dates():
    end = datetime(2026, 7, random.randint(1, 9))
    days_ago = random.randint(7, 30)
    start = end - timedelta(days=days_ago)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def generate_entry(diagnostic_type):
    msisdn = random.choice(MSISDN_POOL)
    debut, fin = pick_dates()
    
    templates = RECLAMATION_TEMPLATES.get(diagnostic_type, RECLAMATION_TEMPLATES["INDETERMINE"])
    resp_templates = RESPONSE_TEMPLATES.get(diagnostic_type, RESPONSE_TEMPLATES["INDETERMINE"])
    
    if diagnostic_type == "SOS_REMBOURSE":
        amount = random.choice(TARIFFS_SOS)
        table = "RD_T_UC_USSD_SOS_CDR_DET"
        subscriber = random.choice(SUBSCRIBER_TYPES)
        loan_id = f"LOAN_{random.randint(10000, 99999)}"
        
        sql_results = [{
            "EVENT_TYPE": "REV",
            "EVENT_STATUS": "CVAS_DEBIT_SOLDE",
            "CHARGE_AMOUNT": amount,
            "DA_AMOUNT": amount,
            "MAIN_DEB_AMOUNT": round(random.uniform(20, 100), 2),
            "START_DATE": f"{debut} {random.randint(8,18)}:00:00",
            "SUBSCRIBER_TYPE": subscriber,
            "TRAFFIC_TYPE": random.choice(["NATIONAL", "INTERNATIONAL"]),
            "A_MSISDN": msisdn,
            "ORIG_START_TIME": f"{debut} {random.randint(8,18)}:00:00",
            "TRANSACTION_ID": f"TXN_{random.randint(100000, 999999)}",
            "SERVICE": "SOS_CREDIT",
            "LOANADJUSTMENT": amount,
            "LOANLEFT": 0.00,
            "FEE": 0.00,
            "LOAN_ID": loan_id,
            "EVENT_ID": f"EVT_{random.randint(10000, 99999)}"
        }]
        
    elif diagnostic_type == "VOICE_SMS":
        num_ops = random.randint(2, 20)
        total = 0
        results = []
        for _ in range(num_ops):
            ct = random.choice(["VOICE", "SMS"])
            amt = random.choice(TARIFFS_VOICE if ct == "VOICE" else TARIFFS_SMS)
            total += amt
            results.append({
                "A_MSISDN": msisdn,
                "B_MSISDN": random.choice(MSISDN_POOL),
                "CALL_TYPE": ct,
                "GE_AMOUNT": amt,
                "EVENT_TYPE": random.choice(["VOICE_CALL", "SMS_SENT", "SMS_RECEIVED"]),
                "START_DATE": f"{debut} {random.randint(8,22)}:00:00",
                "SUBSCRIBER_TYPE": random.choice(SUBSCRIBER_TYPES),
                "PARTNER": random.choice(PARTNERS),
                "COUNTRY": random.choice(COUNTRIES),
                "EVENT_DURATION": random.choice([0, 10, 30, 60, 120, 300, 600, 1800]),
            })
        amount = round(total, 2)
        table = "RD_T_UC_CCN_RO_GPRS_CDR_DETAIL"
        sql_results = results
        
    elif diagnostic_type == "DATA":
        num_ops = random.randint(1, 10)
        total = 0
        results = []
        for _ in range(num_ops):
            amt = random.choice(TARIFFS_DATA)
            total += amt
            results.append({
                "DATASOURCE": "SASNPP",
                "START_DATE": f"{debut} {random.randint(8,22)}:00:00",
                "MSISDN": msisdn,
                "APN": random.choice(APNS),
                "CALL_TYPE": "DATA",
                "SERVICE_ID": f"SVC_{random.randint(1000, 9999)}",
                "SUBSCRIBER_TYPE": random.choice(SUBSCRIBER_TYPES),
                "ROAMING_TYPE": random.choice(ROAMING_TYPES),
                "PARTNER": random.choice(PARTNERS),
                "DATA_VOLUME": random.choice(DATA_VOLUMES),
                "EVENT_DURATION": random.choice([60, 120, 300, 600, 1800, 3600, 7200]),
                "CHARGE_AMOUNT": amt,
                "FILTER_CODE": f"FC_{random.randint(10, 99)}"
            })
        amount = round(total, 2)
        table = "RD_T_UC_SASNPP_DATA_DT"
        sql_results = results
        
    elif diagnostic_type == "VAS":
        num_ops = random.randint(1, 6)
        total = 0
        kw_list = []
        results = []
        for _ in range(num_ops):
            amt = random.choice(TARIFFS_VAS)
            kw = random.choice(KEYWORDS)
            kw_list.append(kw)
            total += amt
            results.append({
                "DATASOURCE": "OCCPP",
                "A_MSISDN": msisdn,
                "B_MSISDN": random.choice(["3000", "3500", "4000", "5000", "7000", "8000"]),
                "START_DATE": f"{debut} {random.randint(8,22)}:00:00",
                "CALL_TYPE": "VAS",
                "SERVICE_ID": f"VAS_{random.randint(1000, 9999)}",
                "SUBSCRIBER_TYPE": random.choice(SUBSCRIBER_TYPES),
                "PARTNER": random.choice(PARTNERS),
                "EVENT_COUNT": random.randint(1, 10),
                "DATA_VOLUME": 0,
                "CHARGE_AMOUNT": amt,
                "KEYWORD": kw,
                "DA_AMOUNT_CALC": round(amt * 0.8, 2),
                "MA_AMNT_CALC": round(amt * 0.2, 2),
            })
        amount = round(total, 2)
        table = "RD_T_UC_OCCPP_SMS_VAS_DT"
        sql_results = results
        keywords_str = ", ".join(list(set(kw_list)))
        
    else:  # INDETERMINE
        amount = round(random.uniform(1, 20), 2)
        table = "— (aucune table correspondante)"
        sql_results = {"note": "Aucune opération trouvée dans les tables standards pour cette période."}
    
    # Générer le message utilisateur
    user_content = (
        f"Réclamation client reçue par email :\n"
        f"\"{random.choice(templates).format(amount=amount, msisdn=msisdn, debut=debut, fin=fin)}\"\n\n"
        f"Paramètres extraits par MailParser :\n"
        f"- msisdn : {msisdn}\n"
        f"- date_debut : {debut}\n"
        f"- date_fin : {fin}\n\n"
        f"Résultats de la requête SQL sur la table {table} :\n"
        f"```\n{json.dumps({'table': table, 'msisdn': msisdn, 'date_debut': debut, 'date_fin': fin, 'results': sql_results}, ensure_ascii=False, indent=2)}\n```"
    )
    
    # Générer la réponse
    resp_template = random.choice(resp_templates)
    if diagnostic_type == "SOS_REMBOURSE":
        assistant_content = resp_template.format(
            amount=amount, msisdn=msisdn, debut=debut, fin=fin, loan_id=loan_id
        )
    elif diagnostic_type == "VOICE_SMS":
        assistant_content = resp_template.format(
            amount=amount, msisdn=msisdn, debut=debut, fin=fin, num_ops=len(sql_results)
        )
    elif diagnostic_type == "DATA":
        assistant_content = resp_template.format(
            amount=amount, msisdn=msisdn, debut=debut, fin=fin, num_ops=len(sql_results)
        )
    elif diagnostic_type == "VAS":
        assistant_content = resp_template.format(
            amount=amount, msisdn=msisdn, debut=debut, fin=fin, keywords=keywords_str
        )
    else:
        assistant_content = resp_template.format(
            amount=amount, msisdn=msisdn, debut=debut, fin=fin
        )
    
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": assistant_content}
        ]
    }


def main():
    weights = {
        "SOS_REMBOURSE": 0.20,
        "VOICE_SMS": 0.30,
        "DATA": 0.25,
        "VAS": 0.15,
        "INDETERMINE": 0.10,
    }
    
    types = list(weights.keys())
    type_weights = list(weights.values())
    
    dataset = []
    for _ in range(NUM_SAMPLES):
        dt = random.choices(types, weights=type_weights, k=1)[0]
        dataset.append(generate_entry(dt))
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    print(f"Génération terminée : {len(dataset)} exemples dans {OUTPUT_FILE}")
    
    counts = {}
    for entry in dataset:
        # Déterminer le type à partir de la réponse
        resp = entry["messages"][2]["content"]
        if "SOS_REMBOURSE" in resp:
            dt = "SOS_REMBOURSE"
        elif "CONSOMMATION_NORMALE" in resp and ("DATA" in resp or "data" in resp):
            dt = "DATA"
        elif "CONSOMMATION_NORMALE" in resp and ("VAS" in resp or "vas" in resp):
            dt = "VAS"
        elif "CONSOMMATION_NORMALE" in resp:
            dt = "VOICE_SMS"
        else:
            dt = "INDETERMINE"
        counts[dt] = counts.get(dt, 0) + 1
    
    print("\nRépartition :")
    for dt, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {dt}: {count} ({count/len(dataset)*100:.1f}%)")


if __name__ == "__main__":
    main()
