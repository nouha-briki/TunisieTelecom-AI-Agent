#!/usr/bin/env python3
"""
Script d'entraînement (fine-tuning) du modèle Qwen pour l'automatisation
des réponses aux réclamations clients de Tunisie Telecom.

Ce script utilise Unsloth pour un entraînement efficace avec LoRA,
puis exporte le modèle fine-tuné en format compatible Ollama.

Prérequis :
  - GPU NVIDIA (ou Google Colab avec GPU gratuit)
  - pip install unsloth datasets transformers peft torch accelerate
  - ollama installé pour l'inférence

Modèle de base recommandé : Qwen2.5-7B-Instruct ou Qwen3-4B-Instruct
  (selon la capacité GPU disponible)
"""

import os
import json
import torch
from datasets import load_dataset

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

# ── Choix du modèle de base ──
# Option 1 : Qwen2.5-7B-Instruct (recommandé pour les réclamations)
# Option 2 : Qwen3-4B-Instruct (plus léger, bon compromis)
# Option 3 : Qwen2.5-3B-Instruct (pour GPU limité, ex: Colab T4)
MODEL_NAME = "unsloth/Qwen2.5-7B-Instruct"

# ── Paramètres de LoRA ──
LORA_R = 16              # Rang de l'adaptateur LoRA (8-128)
LORA_ALPHA = 32          # Facteur d'échelle (généralement 2x r)
LORA_DROPOUT = 0.05      # Dropout pour éviter le sur-apprentissage

# ── Paramètres d'entraînement ──
NUM_EPOCHS = 3
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 4
MAX_SEQ_LENGTH = 2048
LEARNING_RATE = 2e-4
SAVE_PATH = "./tunisie_telecom_qwen_finetuned"

# ── Fichier de données ──
TRAINING_DATA_PATH = "training_data_large.jsonl"

# ═══════════════════════════════════════════════════════════════
# ÉTAPE 1 : INSTALLATION DES DÉPENDANCES
# ═══════════════════════════════════════════════════════════════

def install_dependencies():
    """Installe les bibliothèques nécessaires."""
    os.system("pip install unsloth datasets transformers peft torch accelerate trl")
    print("✓ Dépendances installées.")


# ═══════════════════════════════════════════════════════════════
# ÉTAPE 2 : CHARGEMENT DU MODÈLE
# ═══════════════════════════════════════════════════════════════

def load_model():
    """Charge le modèle Qwen avec Unsloth pour un entraînement optimisé."""
    from unsloth import FastLanguageModel
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,  # Auto-détection (float16 ou bfloat16 selon GPU)
        load_in_4bit=True,  # Quantisation 4-bit pour économiser la VRAM
    )
    
    print(f"✓ Modèle chargé : {MODEL_NAME}")
    return model, tokenizer


# ═══════════════════════════════════════════════════════════════
# ÉTAPE 3 : CONFIGURATION LoRA
# ═══════════════════════════════════════════════════════════════

def setup_lora(model):
    """Configure les adaptateurs LoRA pour le fine-tuning."""
    from unsloth import FastLanguageModel
    
    model = FastLanguageModel.get_peft_model(
        model,
        r=LORA_R,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj"
        ],
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        bias="none",
        use_gradient_checkpointing="unsloth",  # Économie de 30% de mémoire
        random_state=42,
        use_rslora=False,
        loftq_config=None,
    )
    
    print("✓ LoRA configurée.")
    return model


# ═══════════════════════════════════════════════════════════════
# ÉTAPE 4 : PRÉPARATION DES DONNÉES
# ═══════════════════════════════════════════════════════════════

# Prompt template pour Qwen Instruct
QWEN_PROMPT_FORMAT = """<|im_start|>system
{system}
<|im_end|>
<|im_start|>user
{instruction}
<|im_end|>
<|im_start|>assistant
{output}
<|im_end|>"""

EOS_TOKEN = "<|im_end|>"

def formatting_prompts_func(examples):
    """Transforme chaque exemple en texte formaté pour Qwen."""
    inputs = examples["messages"]
    texts = []
    for msgs in inputs:
        system_msg = ""
        user_msg = ""
        assistant_msg = ""
        for msg in msgs:
            if msg["role"] == "system":
                system_msg = msg["content"]
            elif msg["role"] == "user":
                user_msg = msg["content"]
            elif msg["role"] == "assistant":
                assistant_msg = msg["content"]
        
        text = QWEN_PROMPT_FORMAT.format(
            system=system_msg,
            instruction=user_msg,
            output=assistant_msg
        ) + EOS_TOKEN
        texts.append(text)
    return {"text": texts}


def prepare_dataset():
    """Charge et prépare le dataset d'entraînement."""
    dataset = load_dataset("json", data_files={"train": TRAINING_DATA_PATH})
    
    # Appliquer le formatage des prompts
    dataset = dataset.map(
        formatting_prompts_func,
        batched=True,
        remove_columns=["messages", "metadata"],
    )
    
    print(f"✓ Dataset préparé : {len(dataset['train'])} exemples")
    print(f"  Exemple de prompt (début) :\n{dataset['train'][0]['text'][:200]}...")
    return dataset


# ═══════════════════════════════════════════════════════════════
# ÉTAPE 5 : ENTRAÎNEMENT
# ═══════════════════════════════════════════════════════════════

def train_model(model, tokenizer, dataset):
    """Lance l'entraînement du modèle avec SFT Trainer."""
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from unsloth import is_bfloat16_supported
    
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        dataset_text_field="text",
        max_seq_length=MAX_SEQ_LENGTH,
        dataset_num_proc=2,
        packing=False,
        args=TrainingArguments(
            per_device_train_batch_size=BATCH_SIZE,
            gradient_accumulation_steps=GRADIENT_ACCUMULATION,
            warmup_steps=5,
            max_steps=-1,  # Utiliser num_train_epochs au lieu de max_steps
            num_train_epochs=NUM_EPOCHS,
            learning_rate=LEARNING_RATE,
            fp16=not is_bfloat16_supported(),
            bf16=is_bfloat16_supported(),
            logging_steps=10,
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=42,
            output_dir=SAVE_PATH,
            save_strategy="epoch",
            save_total_limit=1,
            report_to="none",
        ),
    )
    
    print("► Démarrage de l'entraînement...")
    trainer.train()
    print("✓ Entraînement terminé.")
    
    return trainer


# ═══════════════════════════════════════════════════════════════
# ÉTAPE 6 : SAUVEGARDE ET CONVERSION
# ═══════════════════════════════════════════════════════════════

def save_and_convert(trainer, model, tokenizer):
    """Sauvegarde le modèle fine-tuné et le convertit pour Ollama."""
    
    # Sauvegarder le modèle fine-tuné (LoRA adapter)
    model.save_pretrained(SAVE_PATH)
    tokenizer.save_pretrained(SAVE_PATH)
    print(f"✓ Modèle sauvegardé dans {SAVE_PATH}")
    
    # Option 1 : Sauvegarder en mode fusionné (merge)
    model.save_pretrained_merged(
        f"{SAVE_PATH}_merged",
        tokenizer,
        save_method="merged_16bit",
    )
    print(f"✓ Modèle fusionné sauvegardé dans {SAVE_PATH}_merged")
    
    # Option 2 : Sauvegarder en mode quantisé GGUF pour Ollama
    model.save_pretrained_gguf(
        f"{SAVE_PATH}_gguf",
        tokenizer,
        quantization_method="q4_K_M",  # Quantisation Q4_K_M pour un bon compromis
    )
    print(f"✓ Modèle GGUF sauvegardé dans {SAVE_PATH}_gguf")
    
    # Créer le Modelfile Ollama
    create_modelfile()


def create_modelfile():
    """Crée le Modelfile pour importer le modèle dans Ollama."""
    modelfile_content = """# Modelfile pour l'agent de réclamations Tunisie Telecom
# Basé sur Qwen2.5-7B-Instruct fine-tuné avec Unsloth

FROM ./tunisie_telecom_qwen_finetuned_gguf/model.gguf

# Paramètres d'inférence optimisés pour les réclamations
PARAMETER temperature 0.7
PARAMETER num_ctx 4096
PARAMETER top_k 40
PARAMETER top_p 0.9
PARAMETER repeat_penalty 1.1

# Prompt système par défaut
SYSTEM \"\"\"Vous êtes un assistant IA spécialisé dans l'automatisation des réponses aux réclamations clients de Tunisie Telecom. Votre rôle est d'analyser les réclamations reçues par email et les données SQL extraites de la base de connaissances Oracle pour diagnostiquer la cause probable du problème et formuler une réponse professionnelle.

La base de connaissances contient 4 tables Oracle principales :
1. RD_T_UC_USSD_SOS_CDR_DET — Événements SOS (crédit d'urgence)
2. RD_T_UC_CCN_RO_GPRS_CDR_DETAIL — CDR voix et SMS
3. RD_T_UC_SASNPP_DATA_DT — CDR data mobile
4. RD_T_UC_OCCPP_SMS_VAS_DT — SMS+ et services VAS

Hiérarchie de diagnostic :
1. Vérifier SOS_CDR_DET : EVENT_TYPE='REV' et EVENT_STATUS='CVAS_DEBIT_SOLDE' → SOS_REMBOURSE
2. Vérifier CDR_DETAIL : CALL_TYPE IN ('VOICE','SMS') et SUM(GE_AMOUNT) > 0 → CONSOMMATION_NORMALE
3. Vérifier DATA_DT : CALL_TYPE='DATA' et SUM(DATA_VOLUME) > 0 → CONSOMMATION_NORMALE
4. Aucune condition → INDETERMINE (escalade humaine)

Répondez toujours de manière professionnelle, claire et empathique.\"\"\"
"""
    
    with open(f"{SAVE_PATH}/Modelfile", "w", encoding="utf-8") as f:
        f.write(modelfile_content)
    
    print(f"✓ Modelfile créé dans {SAVE_PATH}/Modelfile")
    
    # Instructions pour l'utilisateur
    print("\n" + "=" * 60)
    print("INSTRUCTIONS POUR IMPORTER LE MODÈLE DANS OLLAMA :")
    print("=" * 60)
    print(f"  1. Copier le dossier : cp -r {SAVE_PATH}_gguf/ /chemin/ollama/")
    print(f"  2. Créer le modèle : ollama create tunisie-telecom-agent -f {SAVE_PATH}/Modelfile")
    print(f"  3. Tester : ollama run tunisie-telecom-agent")


# ═══════════════════════════════════════════════════════════════
# ÉTAPE 7 : TEST DU MODÈLE
# ═══════════════════════════════════════════════════════════════

def test_model(model, tokenizer):
    """Teste le modèle fine-tuné avec un exemple."""
    from unsloth import FastLanguageModel
    FastLanguageModel.for_inference(model)
    
    test_prompt = QWEN_PROMPT_FORMAT.format(
        system="Vous êtes un assistant IA spécialisé dans l'automatisation des réponses aux réclamations clients de Tunisie Telecom.",
        instruction="Réclamation : \"Bonjour, mon solde a baissé de 15.00 DT sans que je sache pourquoi. Mon numéro est 21697865660. Période du 2026-06-01 au 2026-06-15.\"\n\nDonnées SQL :\n{\"table\": \"RD_T_UC_USSD_SOS_CDR_DET\", \"msisdn\": \"21697865660\", \"results\": [{\"EVENT_TYPE\": \"REV\", \"EVENT_STATUS\": \"CVAS_DEBIT_SOLDE\", \"CHARGE_AMOUNT\": 15.0, \"DA_AMOUNT\": 15.0}]}",
        output=""
    )
    
    inputs = tokenizer([test_prompt], return_tensors="pt").to("cuda")
    outputs = model.generate(**inputs, max_new_tokens=512, use_cache=True)
    response = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
    
    # Extraire uniquement la réponse assistant
    assistant_start = response.find("<|im_start|>assistant")
    if assistant_start != -1:
        response = response[assistant_start + len("<|im_start|>assistant"):]
        response = response.replace("<|im_end|>", "").strip()
    
    print("\n" + "=" * 60)
    print("TEST DU MODÈLE FINE-TUNÉ :")
    print("=" * 60)
    print(response)
    print("=" * 60)


# ═══════════════════════════════════════════════════════════════
# ÉTAPE 8 : ALTERNATIVE — APPROCHE RAG + OLLAMA SIMPLE
# ═══════════════════════════════════════════════════════════════

def create_simple_ollama_setup():
    """
    Alternative : Créer un Modelfile simple basé sur Qwen avec
    le prompt système contenant toute la connaissance métier.
    Cette approche ne nécessite PAS de fine-tuning GPU.
    """
    simple_modelfile = """FROM qwen2.5:7b-instruct

PARAMETER temperature 0.7
PARAMETER num_ctx 8192
PARAMETER top_k 40
PARAMETER top_p 0.9

SYSTEM \"\"\"Vous êtes un assistant IA spécialisé dans l'automatisation des réponses aux réclamations clients de Tunisie Telecom.

## BASE DE CONNAISSANCES — TABLES ORACLE

### 1. RD_T_UC_USSD_SOS_CDR_DET (Événements SOS - crédit d'urgence)
Colonne clé : EVENT_TYPE (ADV = avance, REV = remboursement)
Si EVENT_TYPE='REV' ET EVENT_STATUS='CVAS_DEBIT_SOLDE' → le client a utilisé un crédit SOS remboursé automatiquement.
Autres colonnes importantes : CHARGE_AMOUNT, DA_AMOUNT, MAIN_DEB_AMOUNT, LOANADJUSTMENT, LOANLEFT, A_MSISDN, START_DATE

### 2. RD_T_UC_CCN_RO_GPRS_CDR_DETAIL (CDR voix et SMS)
Colonne clé : CALL_TYPE ('VOICE' ou 'SMS')
Si CALL_TYPE IN ('VOICE','SMS') ET SUM(GE_AMOUNT) > 0 → consommation normale d'appels/SMS.
Autres colonnes importantes : GE_AMOUNT (tarif en DT), A_MSISDN, B_MSISDN, START_DATE, SUBSCRIBER_TYPE, PARTNER, COUNTRY

### 3. RD_T_UC_SASNPP_DATA_DT (CDR data mobile)
Colonne clé : CALL_TYPE ('DATA')
Si CALL_TYPE='DATA' ET SUM(DATA_VOLUME) > 0 → consommation normale de data.
Autres colonnes importantes : DATA_VOLUME (en Ko), CHARGE_AMOUNT, SERVICE_ID, ROAMING_TYPE, APN

### 4. RD_T_UC_OCCPP_SMS_VAS_DT (SMS+ et services VAS)
Colonne clé : CALL_TYPE ('VAS')
Peut expliquer des débits inattendus liés à des services premium.
Autres colonnes importantes : KEYWORD (nom du jeu, sonnerie...), CHARGE_AMOUNT, SERVICE_ID, DA_AMOUNT_CALC, MA_AMNT_CALC

## HIÉRARCHIE DE DIAGNOSTIC
Étape 1 : Interroger RD_T_UC_USSD_SOS_CDR_DET
  Si EVENT_TYPE='REV' et EVENT_STATUS='CVAS_DEBIT_SOLDE' → SOS_REMBOURSE
  
Étape 2 : Interroger RD_T_UC_CCN_RO_GPRS_CDR_DETAIL
  Si CALL_TYPE IN ('VOICE','SMS') et SUM(GE_AMOUNT) > 0 → CONSOMMATION_NORMALE
  
Étape 3 : Interroger RD_T_UC_SASNPP_DATA_DT
  Si CALL_TYPE='DATA' et SUM(DATA_VOLUME) > 0 → CONSOMMATION_NORMALE
  
Étape 4 : Aucune condition → INDETERMINE (escalade vers agent humain)

## PARAMÈTRES SQL
Les requêtes utilisent les données extraites par MailParser depuis l'email :
- A_MSISDN / MSISDN ← msisdn (ex: 21697865660)
- START_DATE BETWEEN date_debut AND date_fin
- DA_VALUE (optionnel) ← da (liste des numéros DA)

## FORMAT DE RÉPONSE ATTENDU
1. Diagnostic : [Type de diagnostic]
2. Explication claire en français pour le client
3. Détails techniques (table, colonnes, montants)
4. Recommandation d'action\"\"\"
"""
    
    with open("/home/ubuntu/Modelfile_simple", "w", encoding="utf-8") as f:
        f.write(simple_modelfile)
    
    print("✓ Modelfile simple créé dans /home/ubuntu/Modelfile_simple")
    print("  Pour l'utiliser : ollama create tunisie-telecom-agent -f /home/ubuntu/Modelfile_simple")


# ═══════════════════════════════════════════════════════════════
# SCRIPT PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def main():
    """Exécute le pipeline complet d'entraînement."""
    
    print("=" * 60)
    print("TRAINING PIPELINE — QWEN + OLLAMA")
    print("Automatisation des réclamations — Tunisie Telecom")
    print("=" * 60)
    
    # Vérifier si GPU disponible
    has_gpu = torch.cuda.is_available()
    print(f"\nGPU disponible : {'Oui (' + torch.cuda.get_device_name(0) + ')' if has_gpu else 'Non'}")
    
    if not has_gpu:
        print("\n⚠️  AUCUN GPU DÉTECTÉ !")
        print("Ce script nécessite un GPU NVIDIA pour le fine-tuning avec Unsloth.")
        print("\nOptions disponibles :")
        print("  1. Utiliser Google Colab (GPU gratuit T4)")
        print("  2. Utiliser l'approche RAG + Ollama simple (pas de GPU requis)")
        print("  3. Louer un GPU cloud (Lambda Labs, RunPod, etc.)")
        print("\nLe Modelfile simple sera créé automatiquement (sans fine-tuning).")
        create_simple_ollama_setup()
        return
    
    print(f"  VRAM disponible : {torch.cuda.get_device_properties(0).total_mem / 1e9:.1f} GB")
    
    # Étape 1 : Installer les dépendances
    print("\n--- ÉTAPE 1 : Installation des dépendances ---")
    install_dependencies()
    
    # Étape 2 : Charger le modèle
    print("\n--- ÉTAPE 2 : Chargement du modèle ---")
    model, tokenizer = load_model()
    
    # Étape 3 : Configurer LoRA
    print("\n--- ÉTAPE 3 : Configuration LoRA ---")
    model = setup_lora(model)
    
    # Étape 4 : Préparer les données
    print("\n--- ÉTAPE 4 : Préparation des données ---")
    dataset = prepare_dataset()
    
    # Étape 5 : Entraînement
    print("\n--- ÉTAPE 5 : Entraînement ---")
    trainer = train_model(model, tokenizer, dataset)
    
    # Étape 6 : Sauvegarde et conversion
    print("\n--- ÉTAPE 6 : Sauvegarde et conversion ---")
    save_and_convert(trainer, model, tokenizer)
    
    # Étape 7 : Test
    print("\n--- ÉTAPE 7 : Test du modèle ---")
    test_model(model, tokenizer)
    
    # Créer aussi le Modelfile simple en alternative
    create_simple_ollama_setup()
    
    print("\n" + "=" * 60)
    print("PIPELINE TERMINÉ AVEC SUCCÈS !")
    print("=" * 60)


if __name__ == "__main__":
    main()
