#!/usr/bin/env python3
"""
config_oracle.py — Fichier de configuration des identifiants Oracle.
Sépare les credentials du code métier pour plus de sécurité.
"""

# ── CONFIGURATION ORACLE (À REMPLACER PAR VOS VRAIES VALEURS) ──
ORACLE_CONFIG = {
    "host": "localhost",       # ex: "oracle.tunisietelecom.tn" ou IP de votre serveur
    "port": 1521,              # port par défaut Oracle
    "service_name": "ORCL",    # Service Name (ou SID selon votre config)
    "user": "C##youssef",   # Username de connexion
    "password": "Pass1234" # Mot de passe
}
