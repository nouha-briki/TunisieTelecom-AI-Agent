#!/usr/bin/env python3
"""
main_agent_v2.py — Pipeline complet d'automatisation des réclamations Tunisie Telecom.
Cette version lit la réclamation depuis un fichier texte externe (reclamation.txt).
Ainsi, il n'est plus nécessaire de modifier le code source pour tester une nouvelle réclamation.
"""

import json
import requests
import sys
import os
import time

from mail_parser import extract_params_from_email

# ── CONFIGURATION : CHOIX DU MOTEUR SQL ──
USE_REAL_ORACLE = True

if USE_REAL_ORACLE:
    try:
        from sql_engine_oracle import run_diagnostic
        print("Mode PRODUCTION : Base Oracle reelle")
    except ImportError as e:
        print(f"ERREUR import: {e}")
        print("Installer oracledb : pip install oracledb")
        print("Configurer vos identifiants dans config_oracle.py")
        sys.exit(1)
else:
    from sql_engine import run_diagnostic_simulation as run_diagnostic
    print("Mode SIMULATION : Donnees fictives")


# ── APPEL À L'AGENT IA (OLLAMA) ──
def ask_agent(prompt_text):
    """Envoie un prompt à l'agent IA via l'API Ollama et retourne la réponse."""
    url = "http://localhost:11434/api/chat"
    payload = {
        "model": "tunisie-telecom-agent",
        "messages": [{"role": "user", "content": prompt_text}],
        "stream": False,
        "options": {"temperature": 0.7, "num_ctx": 8192, "top_k": 40, "top_p": 0.9}
    }
    print("  -> Envoi de la requete a Ollama...")
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        print("  X ERREUR : Ollama n'est pas accessible. Assurez-vous qu'Ollama est lance.")
        return None
    except Exception as e:
        print(f"  X ERREUR Ollama: {e}")
        return None


# ── PIPELINE PRINCIPAL ──
def process_reclamation(email_text):
    """Pipeline complet : traite une réclamation de bout en bout."""
    print("=" * 60)
    print("PIPELINE : Traitement de la reclamation")
    print("=" * 60)

    # Bloc 1 : MailParser
    print("\n[1/5] Extraction des parametres...")
    params = extract_params_from_email(email_text)

    if 'msisdn' not in params:
        print("  X ERREUR : Numero MSISDN non trouve dans l'e-mail.")
        return None

    print(f"  MSISDN : {params.get('msisdn')}")
    if params.get('da'):
        print(f"  DA : {params.get('da')}")
    if params.get('montant'):
        print(f"  Montant reclame : {params.get('montant')} DT")
    if params.get('date_debut'):
        print(f"  Periode : {params.get('date_debut')} -> {params.get('date_fin', 'N/A')}")
    if params.get('crm'):
        print(f"  CRM : {params.get('crm')}")
    print(f"  Type : {params.get('reclamation_type', 'UNKNOWN')}")

    # Bloc 2 : Moteur SQL
    print("\n[2/5] Diagnostic SQL...")
    sql_result = run_diagnostic(
        params['msisdn'],
        params.get('date_debut', '2026-01-01'),
        params.get('date_fin', '2026-01-15'),
        da=params.get('da'),
        volume=params.get('volume'),
        montant=params.get('montant'),
    )
    print(f"  Diagnostic : {sql_result['diagnostic']}")
    if sql_result.get('total_amount'):
        print(f"  Montant trouve : {sql_result['total_amount']} DT")
    if sql_result.get('coverage_ratio'):
        print(f"  Coverage : {sql_result['coverage_ratio']}")

    # Bloc 3 : Assembleur de Prompt
    print("\n[3/5] Construction du prompt...")
    context = f"E-mail client:\n{email_text}\n\n"
    context += f"Parametres:\n{json.dumps(params, ensure_ascii=False)}\n\n"
    context += f"Resultats SQL:\n{json.dumps(sql_result, ensure_ascii=False, default=str)}\n\n"
    context += "Analysez et donnez : 1) Diagnostic 2) Explication client 3) Details techniques 4) Recommandation"

    # Bloc 4 : Agent IA (Ollama)
    print("\n[4/5] Generation de la reponse par l'IA...")
    response = ask_agent(context)

    if response:
        print("\n" + "=" * 60)
        print("REPONSE FINALE :")
        print("=" * 60)
        print(response)
        print("=" * 60)
    else:
        print("  X L'IA n'a pas pu generer de reponse.")

    return response


# ── EXÉCUTION ──
if __name__ == "__main__":
    # Vérifier si le fichier reclamation.txt existe
    fichier_reclamation = "reclamation.txt"
    
    if not os.path.exists(fichier_reclamation):
        print(f"Erreur : Le fichier '{fichier_reclamation}' n'existe pas dans ce dossier.")
        print("Veuillez creer ce fichier, y coller votre e-mail de reclamation, puis relancer le script.")
        
        # Créer un fichier vide par défaut
        with open(fichier_reclamation, "w", encoding="utf-8") as f:
            f.write("Collez votre reclamation ici...\n")
        sys.exit(1)
        
    # Lire le contenu du fichier
    print(f"Lecture de la reclamation depuis : {fichier_reclamation}")
    with open(fichier_reclamation, "r", encoding="utf-8") as f:
        test_email = f.read().strip()
        
    if not test_email or test_email.startswith("Collez votre reclamation"):
        print(f"Erreur : Le fichier '{fichier_reclamation}' est vide ou contient le texte par defaut.")
        sys.exit(1)

    # Traiter la réclamation
    process_reclamation(test_email)
