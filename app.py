from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from datetime import datetime, timezone, timedelta


import json
import base64
import httpx
from aiofiles

import os
from pathlib import Path


app = FastAPI(title="Smart Eye - Détection intelligente d’incidents")

# Autoriser les CORS pour le front-end
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stockage temporaire pour les incidents (pour un prototype)
incident_storage = []

# Fichier de persistance des incidents
INCIDENT_FILE = Path("incident_data.json")

# Charger les incidents à partir du fichier lors du démarrage
if INCIDENT_FILE.exists():
    try:
        with open(INCIDENT_FILE, "r", encoding="utf-8") as f:
            incident_storage.extend(json.load(f))
            print(f"{len(incident_storage)} incidents chargés depuis le fichier.")
    except Exception as e:
        print(f"Erreur lors du chargement des incidents : {e}")

# Fonction pour sauvegarder les incidents dans un fichier
async def save_incident_to_file():
    try:
        async with aiofiles.open(INCIDENT_FILE, "w", encoding="utf-8") as f:
            data = json.dumps(incident_storage, ensure_ascii=False, indent=2)
            await f.write(data)
    except Exception as e:
        print(f"Erreur lors de la sauvegarde de l'incident : {e}")



# # Fonction pour envoyer la réponse aux services compétents
# async def send_to_app(response_data):
#     try:
#         async with httpx.AsyncClient() as client:
#             await client.post(APP_TARGET_URL, json=response_data)
#     except Exception as e:
#         print(f"Erreur lors de l'envoi aux services compétents : {str(e)}")

# Fonction pour valider et formater l’image base64
def format_image_base64(image_data: bytes, mime_type: str = "image/jpeg") -> str:
    try:
        base64_string = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{base64_string}"
    except Exception:
        raise HTTPException(status_code=400, detail="Impossible d'encoder l'image en base64")

# Endpoint POST principal pour signaler un incident
@app.post("/report_incident/")
async def report_incident(
    response: str = Form(...),  # JSON sous forme de chaîne
    image: UploadFile = File(...)  # Image brute comme fichier
):
    try:
        # Parser le JSON
        data = json.loads(response)
        expected_keys = {"accident", "incendie", "violence", "commentaire"}
        if not isinstance(data, dict) or set(data.keys()) != expected_keys:
            raise HTTPException(status_code=400, detail="Le JSON doit contenir exactement 'accident', 'incendie', 'violence', 'commentaire'")

        if not all(isinstance(data[key], bool) for key in ["accident", "incendie", "violence"]):
            raise HTTPException(status_code=400, detail="Les champs 'accident', 'incendie', 'violence' doivent être des booléens")
        if not isinstance(data["commentaire"], str):
            raise HTTPException(status_code=400, detail="Le champ 'commentaire' doit être une chaîne")

        # Identifier les types d’incidents
        incident_types = []
        if data["accident"]:
            incident_types.append("accident")
        if data["incendie"]:
            incident_types.append("incendie")
        if data["violence"]:
            incident_types.append("violence")
        
        if not incident_types:
            raise HTTPException(status_code=400, detail="Aucun type d'incident détecté (au moins un booléen doit être true)")

        # Lire et encoder l’image
        image_data = await image.read()
        if not image_data:
            raise HTTPException(status_code=400, detail="L'image est vide")
        
        mime_type = image.content_type if image.content_type in ["image/jpeg", "image/png"] else "image/jpeg"
        formatted_image_base64 = format_image_base64(image_data, mime_type)


        # Construire la réponse
        response_data = {
            "id": len(incident_storage) + 1,  # ID incrémental pour le prototype
            "timestamp": datetime.now(timezone(timedelta(hours=1))).isoformat(),
            "type": incident_types,
            "location": "Cotonou - Carrefour SIKA",  # À rendre dynamique si nécessaire
            "image": formatted_image_base64,
            "message": data["commentaire"]
        }

        print("Données reçues et formatées :")
        response_data_short = response_data.copy()
        response_data_short["image"] = response_data["image"][:50] + "..."  # Pour lisibilité
        print(json.dumps(response_data_short, indent=2))
        
        # Stocker l'incident pour le monitoring (pour prototype)
        incident_storage.append(response_data)
        save_incident_to_file()

        
        # Envoyer aux services compétents
        # await send_to_app(response_data)
        response_for_client = {"status": "success", "message": "Incident signalé avec succès"}
        return JSONResponse(response_for_client)

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Le JSON envoyé n'est pas valide")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint GET pour récupérer les incidents signalés (pour monitoring)
@app.get("/incidents")
async def get_incidents():
    return incident_storage
