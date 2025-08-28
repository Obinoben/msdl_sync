#!/usr/bin/env python3
import os
import json
import subprocess
import requests
from pathlib import Path

print("coucou")

# Init
MONDAY_API_KEY = Path("/etc/quadrumane/monday.key").read_text().strip()
m = os.environ.get("m")
if not m:
    raise RuntimeError("La variable d'environnement $m est vide")

data = json.loads(m)
MONDAY_ITEM = data.get("monday_item_id")
SCRIPT_DIR = Path(__file__).resolve().parent

API_URL = "https://api.monday.com/v2"
HEADERS = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json",
}

def update_monday_item(item_id: str, column_id: str, value: dict):
    """Met à jour une colonne simple d'un item Monday"""
    mutation = f"""
    mutation {{
      change_simple_column_value(
        item_id: {item_id},
        column_id: "{column_id}",
        value: "{json.dumps(value).replace('"', '\\"')}"
      ) {{
        id
      }}
    }}
    """
    resp = requests.post(API_URL, headers=HEADERS, json={"query": mutation})
    if resp.status_code != 200:
        print(f"Erreur HTTP {resp.status_code}: {resp.text}")
    else:
        rj = resp.json()
        if "errors" in rj:
            print("Erreur GraphQL:", rj)
        else:
            print("Mise à jour Monday OK:", rj)

print("Message reçu")
update_monday_item(MONDAY_ITEM, "status", {"label": "Traitement"})

global_status = 0
archives = [a.strip() for a in data.get("archives", "").split(",") if a.strip()]

for archive in archives:
    print(f"Lance la synchronisation de {archive}")
    result = subprocess.run(
        [str(SCRIPT_DIR / "syncer.py"), "-s", "-b", archive]
    )
    global_status += result.returncode

if global_status == 0:
    print("Tout a fonctionné")
    update_monday_item(MONDAY_ITEM, "status", {"label": "Succès"})
else:
    print("Erreur de sync")
    update_monday_item(MONDAY_ITEM, "status", {"label": "Échec"})

exit(global_status)
