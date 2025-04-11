import logging
from fastapi import FastAPI, HTTPException, Form, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone, timedelta
import json
import base64
import httpx
from pathlib import Path
import aiofiles
from pydantic import BaseModel, ValidationError

# Configuration du logging
logger = logging.getLogger("incident_api")
logging.basicConfig(level=logging.INFO)

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

# Charger les incidents depuis le fichier lors du démarrage
if INCIDENT_FILE.exists():
    try:
        with open(INCIDENT_FILE, "r", encoding="utf-8") as f:
            loaded_data = json.load(f)
            if isinstance(loaded_data, list):
                incident_storage.extend(loaded_data)
                logger.info(f"{len(incident_storage)} incidents chargés depuis le fichier.")
            else:
                logger.error("Le contenu du fichier n'est pas une liste.")
    except Exception as e:
        logger.error(f"Erreur lors du chargement des incidents : {e}")

# Sauvegarde asynchrone des incidents dans le fichier
async def save_incident_to_file():
    try:
        async with aiofiles.open(INCIDENT_FILE, "w", encoding="utf-8") as f:
            data = json.dumps(incident_storage, ensure_ascii=False, indent=2)
            await f.write(data)
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de l'incident : {e}")

# Modèle Pydantic pour valider le JSON du formulaire
class IncidentReport(BaseModel):
    accident: bool
    incendie: bool
    violence: bool
    commentaire: str

    class Config:
        extra = 'forbid'  # Interdit toute clé supplémentaire

# Fonction pour encoder l’image au format base64
def format_image_base64(image_data: bytes, mime_type: str = "image/jpeg") -> str:
    try:
        base64_string = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{base64_string}"
    except Exception:
        raise HTTPException(status_code=400, detail="Impossible d'encoder l'image en base64")

# Endpoint POST pour signaler un incident
@app.post("/report_incident/")
async def report_incident(
    response: str = Form(...),  # JSON sous forme de chaîne
    image: UploadFile = File(...)  # Image brute en fichier
):
    try:
        # Validation du JSON avec Pydantic
        try:
            report_data = IncidentReport.parse_raw(response)
        except ValidationError as ve:
            raise HTTPException(status_code=400, detail=ve.errors())
        
        # Déterminer les types d'incidents à partir des booléens
        incident_types = []
        if report_data.accident:
            incident_types.append("accident")
        if report_data.incendie:
            incident_types.append("incendie")
        if report_data.violence:
            incident_types.append("violence")
        
        if not incident_types:
            raise HTTPException(
                status_code=400,
                detail="Aucun type d'incident détecté (au moins un booléen doit être true)"
            )

        # Lecture et encodage de l'image
        image_data = await image.read()
        if not image_data:
            raise HTTPException(status_code=400, detail="L'image est vide")
        
        mime_type = image.content_type if image.content_type in ["image/jpeg", "image/png"] else "image/jpeg"
        formatted_image_base64 = format_image_base64(image_data, mime_type)

        # Construction de l'incident (conservation du même format de réponse)
        incident_id = len(incident_storage) + 1  # ID incrémental pour compatibilité
        response_data = {
            "id": incident_id,
            "timestamp": datetime.now(timezone(timedelta(hours=1))).isoformat(),
            "type": incident_types,
            "location": "Cotonou - Carrefour SIKA",  # À rendre dynamique si nécessaire
            "image": formatted_image_base64,
            "message": report_data.commentaire
        }

        # Log de l'incident reçu (affichage partiel de l'image pour la lisibilité)
        response_data_short = response_data.copy()
        response_data_short["image"] = response_data["image"][:50] + "..."
        logger.info("Données reçues et formatées : " + json.dumps(response_data_short, indent=2))
        
        # Stockage de l'incident et persistance
        incident_storage.append(response_data)
        await save_incident_to_file()

        # Réponse au client
        return JSONResponse({"status": "success", "message": "Incident signalé avec succès"})

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Le JSON envoyé n'est pas valide")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint GET pour récupérer les incidents signalés (pour monitoring)
@app.get("/incidents")
async def get_incidents():
    return incident_storage
