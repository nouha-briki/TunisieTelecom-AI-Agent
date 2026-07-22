#!/usr/bin/env python3
"""
main_agent.py — Pipeline complet d'automatisation des réclamations Tunisie Telecom.
(Architecture RAG + Ollama Simple — Pas de GPU requis)

Flux : E-mail → MailParser → Moteur SQL → Assembleur → Agent IA (Ollama) → Réponse
"""

import re
import json
import requests
from mail_parser import extract_params_from_email
from sql_engine import run_diagnostic_simulation


# ── APPEL À L'AGENT IA (OLLAMA) ──
def ask_agent(prompt_text):
    """
    Envoie un prompt à l'agent IA via l'API Ollama et retourne la réponse.
    """
    url = "http://localhost:11434/api/chat"

    payload = {
        "model": "tunisie-telecom-agent",
        "messages": [
            {"role": "user", "content": prompt_text}
        ],
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_ctx": 8192,
            "top_k": 40,
            "top_p": 0.9
        }
    }

    print(f"  → Envoi de la requête à Ollama...")
    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.exceptions.ConnectionError:
        print("  ✗ ERREUR : Ollama n'est pas accessible.")
        print("  → Assurez-vous qu'Ollama est lancé : 'ollama serve'")
        return None
    except Exception as e:
        print(f"  ✗ ERREUR : {e}")
        return None


# ── PIPELINE PRINCIPAL ──
def process_reclamation(email_text):
    """
    Pipeline complet : traite une réclamation de bout en bout.

    Args:
        email_text: Le texte brut de l'e-mail de réclamation

    Returns:
        str: La réponse générée par l'agent IA
    """

    print("=" * 60)
    print("PIPELINE : Traitement de la réclamation")
    print("  Architecture : RAG + Ollama (Sans GPU)")
    print("=" * 60)

    # ── Bloc 1 : MailParser ──
    print("\n[1/5] Extraction des paramètres...")
    params = extract_params_from_email(email_text)

    if 'msisdn' not in params:
        print("  ✗ ERREUR : Numéro MSISDN non trouvé dans l'e-mail.")
        print("  → Le numéro doit être au format 216XXXXXXXX")
        return None

    print(f"  MSISDN : {params['msisdn']}")
    if params.get('da'):
        print(f"  DA : {params['da']}")
    if params.get('volume'):
        print(f"  Volume signalé : {params['volume']}")
    if params.get('date_debut'):
        print(f"  Période : {params['date_debut']} → {params.get('date_fin', 'N/A')}")
    if params.get('crm'):
        print(f"  CRM : {params['crm']}")
    print(f"  Type de réclamation : {params.get('reclamation_type', 'UNKNOWN')}")

    # ── Bloc 2 : Moteur SQL ──
    print("\n[2/5] Diagnostic SQL...")
    sql_result = run_diagnostic_simulation(
        params['msisdn'],
        params.get('date_debut', '2026-01-01'),
        params.get('date_fin', '2026-01-15'),
        da=params.get('da'),
        volume=params.get('volume'),
    )
    print(f"  Diagnostic : {sql_result['diagnostic']}")
    if sql_result.get('subtype'):
        print(f"  Type : {sql_result['subtype']}")
    if sql_result.get('total_amount'):
        print(f"  Montant total : {sql_result['total_amount']} DT")
    if sql_result.get('total_volume_kb'):
        print(f"  Volume data : {sql_result.get('total_volume_display', 'N/A')}")

    # ── Bloc 3 : Assembleur de Prompt ──
    print("\n[3/5] Construction du prompt...")

    # Contexte enrichi
    context_parts = []

    # Informations du client
    context_parts.append(f"**E-mail original du client :**\n\n{email_text}")

    # Paramètres extraits
    context_parts.append(f"\n**Paramètres extraits par MailParser :**")
    context_parts.append(f"- MSISDN : {params['msisdn']}")
    if params.get('da'):
        context_parts.append(f"- Compte DA : {params['da']}")
    if params.get('volume'):
        context_parts.append(f"- Volume signalé par le client : {params['volume']}")
    if params.get('date_debut'):
        context_parts.append(f"- Date de début : {params['date_debut']}")
    if params.get('date_fin'):
        context_parts.append(f"- Date de fin : {params['date_fin']}")
    if params.get('crm'):
        context_parts.append(f"- Ticket CRM : {params['crm']}")
    context_parts.append(f"- Type détecté : {params.get('reclamation_type', 'UNKNOWN')}")

    # Résultats SQL
    context_parts.append(f"\n**Résultats de la requête SQL :**")
    context_parts.append(f"```json\n{json.dumps(sql_result, ensure_ascii=False, indent=2)}\n```")

    # Instructions de réponse
    context_parts.append(f"""
**Instructions :**
1. Commencez par le **Diagnostic** (SOS_REMBOURSE, CONSOMMATION_NORMALE, INDETERMINE)
2. Donnez une **explication claire en français** pour le client
3. Fournissez les **détails techniques** (table interrogée, montants, volumes)
4. Terminez par une **recommandation d'action** (ou escalade si indéterminé)
5. Utilisez un ton **professionnel et empathique**
6. Si le diagnostic est INDETERMINE, recommandez l'escalade vers un agent humain""")

    prompt = "\n".join(context_parts)

    # ── Bloc 4 : Agent IA (Ollama) ──
    print("\n[4/5] Génération de la réponse par l'IA...")
    response = ask_agent(prompt)

    if response:
        print(f"  ✓ Réponse générée ({len(response)} caractères)")
    else:
        print("  ✗ L'IA n'a pas pu générer de réponse.")
        return None

    # ── Bloc 5 : Affichage final ──
    print("\n[5/5] Réponse finale")
    print("-" * 60)
    print(response)
    print("-" * 60)

    return response


# ── EXÉCUTION ──
if __name__ == "__main__":
    # Réclamation réelle Tunisie Telecom (format CRM)
    test_email = """Bonjour,

Le client teneur de la ligne numéro 21694197397 réclame l'expiration de son FF data comme suit :

-          Balance concerné : DA7
-          Volume expiré : 4 Go
-          Date : le 02/07/2026

Merci de vérifier.

CRM : 1-53034679076

Cordialement"""

    response = process_reclamation(test_email)

    if response:
        print("\n" + "=" * 60)
        print("✓ Traitement terminé avec succès !")
        print("=" * 60)
