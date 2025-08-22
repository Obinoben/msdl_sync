#!/usr/bin/env python3

# Prérequis :
# - apt install python3 python3-pip
# - pip install pycryptodome

import json
import base64
import argparse
import requests
from time import time
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from hashlib import sha256
from datetime import datetime

# === CONFIGURATION ===
NTFY_URL = "https://ntfy.sh/Qudrumane_Backups_Pw4mKmuDq0ABO3ZC"
PSK_FILE = "/etc/quadrumane/sync.key"
BACKUP_TYPE = "Syncer"


# === FONCTION UTILITAIRE POUR LE TIMESTAMP ===
def time_to_string(ts):
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

# === CHIFFREMENT AES-256-CBC AVEC IV RANDOM ===
def encrypt_string(plaintext, password):
    key = sha256(password.encode()).digest()
    iv = get_random_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)

    # Padding PKCS7
    pad_len = 16 - len(plaintext.encode('utf-8')) % 16
    padded = plaintext + chr(pad_len) * pad_len
    ciphertext = cipher.encrypt(padded.encode('utf-8'))

    return base64.b64encode(iv + ciphertext).decode('utf-8')

# === GET KEY ===
def read_psk_from_file(path='secret.key'):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()

# === PARSE ARGUMENTS ===
parser = argparse.ArgumentParser()
parser.add_argument("--client", required=True)
parser.add_argument("--vm", required=True)
parser.add_argument("--status", required=True, type=int)
parser.add_argument("--gap", default=1, type=int)
args = parser.parse_args()

PSK = read_psk_from_file(path=PSK_FILE)

# === CONSTRUCTION DU MESSAGE JSON ===
data = {
    "client": args.client,
    "backups_type": BACKUP_TYPE,
    "backups": [{
        "vm": args.vm,
        "date": time_to_string(time()),
        "type": "sync",
        "result": str(args.status),
        "gap": args.gap,
        "days": [
            { "monday": "21:00" },
            { "tuesday": "21:00" },
            { "wednesday": "21:00" },
            { "thursday": "21:00" },
            { "friday": "21:00" },
            { "saturday": "21:00" },
            { "sunday": "21:00" }
        ]
    }]
}

# === CHIFFREMENT ET ENVOI ===
plaintext = json.dumps(data, ensure_ascii=False)
encrypted = encrypt_string(plaintext, PSK)

try:
    headers = {
        "Title": args.client
    }
    response = requests.post(NTFY_URL, data=encrypted, headers=headers)
    response.raise_for_status()
    print("✅ Message envoyé")
except Exception as e:
    print(f"❌ Erreur lors de l’envoi : {e}")
