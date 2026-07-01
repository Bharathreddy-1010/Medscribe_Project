import os
import re
import shutil
import tempfile
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.db import get_db
from backend.ai import extractor

app = FastAPI(
    title="MedScribe API",
    description="Backend service for ambient clinical audio summarization and structured EHR parsing.",
    version="1.0.0"
)

# Enable CORS for the frontend application
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect database
db = get_db()

# Data models
class PrescriptionSchema(BaseModel):
    drug: str = Field(..., description="Name of the prescribed drug")
    dosage: str = Field(..., description="Dosage details (e.g. 500mg)")
    frequency: str = Field(..., description="Frequency of intake (e.g. twice a day)")

class EncounterSchema(BaseModel):
    patient_name: str = Field(..., description="Name of the patient")
    encounter_date: str = Field(..., description="Encounter date")
    transcript: str = Field(..., description="Full spoken transcript")
    symptoms: List[str] = Field(default=[], description="List of detected symptoms")
    diagnoses: List[str] = Field(default=[], description="List of detected diagnoses")
    prescriptions: List[PrescriptionSchema] = Field(default=[], description="List of prescriptions")
    clinical_notes: str = Field(..., description="Markdown clinical summary notes")

class EncounterUpdateSchema(BaseModel):
    patient_name: Optional[str] = None
    encounter_date: Optional[str] = None
    symptoms: Optional[List[str]] = None
    diagnoses: Optional[List[str]] = None
    prescriptions: Optional[List[PrescriptionSchema]] = None
    clinical_notes: Optional[str] = None

def sanitize_text(text: str) -> str:
    """Helper to sanitize text input and prevent script injections."""
    if not text:
        return ""
    # Basic HTML tag stripping
    clean = re.sub(r'<[^>]*>', '', text)
    return clean

import re

@app.post("/api/transcribe", response_model=Dict[str, Any])
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Upload an audio file (WAV/WebM), transcribe it using Whisper,
    and extract structured medical entities.
    """
    # Verify file extension (only allow audio files)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".wav", ".mp3", ".webm", ".m4a", ".ogg", ".aac"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported audio format. Please upload WAV, MP3, WebM, M4A, or OGG."
        )

    # Save to a temporary file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_audio:
            shutil.copyfileobj(file.file, temp_audio)
            temp_path = temp_audio.name

        # Perform speech-to-text
        transcript_text = extractor.transcribe(temp_path)
        transcript_text = sanitize_text(transcript_text)

        # Extract structured entities and summary
        extracted_data = extractor.extract_entities(transcript_text)

        # Clean up the temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        return {
            "transcript": transcript_text,
            "patient_name": extracted_data["patient_name"],
            "encounter_date": extracted_data["encounter_date"],
            "symptoms": extracted_data["symptoms"],
            "diagnoses": extracted_data["diagnoses"],
            "prescriptions": extracted_data["prescriptions"],
            "clinical_notes": extracted_data["clinical_notes"]
        }

    except Exception as e:
        # Guarantee temp file clean up
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Audio processing failed: {str(e)}"
        )

@app.get("/api/encounters", response_model=List[Dict[str, Any]])
async def get_encounters(search: Optional[str] = None):
    """
    Fetch all encounters.
    Supports a search query to search across patient names, symptoms, or diagnoses.
    """
    try:
        query = {}
        if search:
            search = sanitize_text(search)
            # SQLite fallback query translation or direct search
            # For simplicity, our db find accepts direct dictionary matching.
            # We will search by patient name, symptom, or diagnosis.
            # If MongoDB is running, we can do $or regex.
            # If SQLite is running, our custom db.py supports $or query dictionaries.
            query = {
                "$or": [
                    {"patient_name": search},
                    {"encounter_date": search}
                ]
            }
            # Also support substring filtering in Python layer
            all_records = list(db.encounters.find())
            search_lower = search.lower()
            filtered_records = []
            for record in all_records:
                patient_name = record.get("patient_name", "").lower()
                notes = record.get("clinical_notes", "").lower()
                symptoms = [s.lower() for s in record.get("symptoms", [])]
                diagnoses = [d.lower() for d in record.get("diagnoses", [])]
                
                if (search_lower in patient_name or 
                    search_lower in notes or 
                    any(search_lower in s for s in symptoms) or 
                    any(search_lower in d for d in diagnoses)):
                    filtered_records.append(record)
            return filtered_records

        return list(db.encounters.find())
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database query failed: {str(e)}"
        )

@app.post("/api/encounters", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_encounter(encounter: EncounterSchema):
    """
    Save a new clinical encounter record.
    """
    try:
        record = encounter.dict()
        # Additional data sanitization
        record["patient_name"] = sanitize_text(record["patient_name"])
        record["clinical_notes"] = sanitize_text(record["clinical_notes"])
        
        result = db.encounters.insert_one(record)
        record["_id"] = result.inserted_id
        return record
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save record: {str(e)}"
        )

@app.put("/api/encounters/{id}", response_model=Dict[str, Any])
async def update_encounter(id: str, updates: EncounterUpdateSchema):
    """
    Update an existing clinical encounter record.
    """
    try:
        # Check if record exists
        existing = db.encounters.find_one({"_id": id})
        if not existing:
            # Try plain text ID match
            existing = db.encounters.find_one({"id": id})
            if not existing:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Clinical encounter record not found"
                )

        update_data = {k: v for k, v in updates.dict().items() if v is not None}
        
        # Sanitize string fields
        if "patient_name" in update_data:
            update_data["patient_name"] = sanitize_text(update_data["patient_name"])
        if "clinical_notes" in update_data:
            update_data["clinical_notes"] = sanitize_text(update_data["clinical_notes"])
        if "prescriptions" in update_data:
            update_data["prescriptions"] = [p.dict() for p in update_data["prescriptions"]]

        db.encounters.update_one({"_id": id}, {"$set": update_data})
        
        # Fetch updated record
        updated_record = db.encounters.find_one({"_id": id})
        return updated_record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update record: {str(e)}"
        )

@app.delete("/api/encounters/{id}", response_model=Dict[str, Any])
async def delete_encounter(id: str):
    """
    Delete a clinical encounter record.
    """
    try:
        existing = db.encounters.find_one({"_id": id})
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clinical encounter record not found"
            )

        db.encounters.delete_one({"_id": id})
        return {"status": "success", "message": f"Encounter {id} successfully deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete record: {str(e)}"
        )

# Serve frontend static assets (must be after api routes)
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
else:
    app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
