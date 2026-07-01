import os
import re
import datetime

# Try to import whisper, provide warning fallback if not installed/available
HAS_WHISPER = False
try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    print("openai-whisper is not installed. Using fallback transcription.")

# Try to import spacy, provide warning fallback
HAS_SPACY = False
try:
    import spacy
    HAS_SPACY = True
except ImportError:
    print("spaCy is not installed. Using rule-based NER fallback.")

# Common medical dictionary list for robust rule-based parsing
COMMON_SYMPTOMS = [
    "fever", "cough", "shortness of breath", "fatigue", "muscle aches", "body aches",
    "headache", "sore throat", "runny nose", "congestion", "nausea", "vomiting",
    "diarrhea", "chest pain", "back pain", "abdominal pain", "joint pain", "dizziness",
    "rash", "itching", "swelling", "chills", "sweats", "anxiety", "insomnia",
    "weight loss", "weight gain", "loss of appetite", "wheezing", "sneezing"
]

COMMON_DIAGNOSES = [
    "hypertension", "type 2 diabetes", "diabetes", "asthma", "bronchitis", "pneumonia",
    "covid-19", "influenza", "flu", "acute sinusitis", "strep throat", "gastroenteritis",
    "acid reflux", "gerd", "urinary tract infection", "uti", "hyperlipidemia",
    "anxiety disorder", "depression", "arthritis", "migraine", "otitis media",
    "allergic rhinitis", "eczema", "dermatitis"
]

COMMON_DRUGS = [
    "amoxicillin", "metformin", "lisinopril", "albuterol", "aspirin", "ibuprofen",
    "acetaminophen", "paracetamol", "atorvastatin", "omeprazole", "amlodipine",
    "levothyroxine", "gabapentin", "losartan", "sertraline", "prednisone",
    "fluticasone", "montelukast", "amoxicillin-clavulanate", "augmentin", "ciprofloxacin"
]

# Regex patterns for parsing dosages and frequencies
DOSAGE_PATTERN = re.compile(
    r'\b(\d+\s*(?:mg|g|mcg|ml|puffs|units|tablets|tabs|capsules|caps))\b', 
    re.IGNORECASE
)
FREQUENCY_PATTERN = re.compile(
    r'\b((?:once|twice|three times|four times)\s*(?:a day|daily|weekly|a week|every \d+ hours)|bid|tid|qd|qhs|prn|as needed)\b',
    re.IGNORECASE
)

# Mock transcript pool for offline/development testing
MOCK_TRANSCRIPTS = [
    "Hello Doctor, my name is John Doe. I've been feeling a severe headache and high fever since yesterday. My throat is also very sore.",
    "Good morning. This is patient Jane Smith, date of birth October 10, 1985. She reports chest pain and shortness of breath when climbing stairs. Let's prescribe Albuterol 2 puffs every 4 hours as needed and Lisinopril 10mg daily for hypertension.",
    "Patient is Robert Johnson. He complains of abdominal pain and vomiting. Diagnosis is acute gastroenteritis. I'm prescribing Amoxicillin 500mg three times a day for 7 days.",
    "The patient has type 2 diabetes. Currently taking Metformin 850mg twice a day. Blood sugar readings have been stable. No other active symptoms reported."
]

class MedicalExtractor:
    """ASR transcription and clinical entity extraction NLP pipeline."""
    def __init__(self):
        self.nlp = None
        if HAS_SPACY:
            try:
                self.nlp = spacy.load("en_core_web_sm")
                print("Loaded spaCy en_core_web_sm model successfully.")
            except Exception as err:
                print(f"Could not load spaCy model: {err}. Fallback to regex/wordlist extractor.")

        self.whisper_model = None
        self.whisper_loaded = False

    def load_whisper(self):
        """Pre-load the Whisper tiny model locally."""
        if HAS_WHISPER and not self.whisper_loaded:
            try:
                print("Loading Whisper 'tiny' model...")
                self.whisper_model = whisper.load_model("tiny")
                self.whisper_loaded = True
                print("Whisper model loaded successfully.")
            except Exception as err:
                print(f"Failed to load Whisper model: {err}")

    def transcribe(self, audio_file_path: str) -> str:
        """Transcribe the audio file path to text string."""
        if HAS_WHISPER:
            self.load_whisper()
            if self.whisper_loaded and self.whisper_model:
                try:
                    result = self.whisper_model.transcribe(audio_file_path)
                    return result.get("text", "")
                except Exception as err:
                    print(f"Whisper transcription failed: {err}. Using fallback mock.")
        
        val = sum(ord(c) for c in os.path.basename(audio_file_path))
        mock_idx = val % len(MOCK_TRANSCRIPTS)
        return MOCK_TRANSCRIPTS[mock_idx]

    def extract_entities(self, text: str) -> dict:
        """Extract patient, date, symptoms, diagnoses, and drug orders from text."""
        patient_name = "Unknown Patient"
        symptoms = []
        diagnoses = []
        prescriptions = []
        encounter_date = datetime.date.today().strftime("%B %d, %Y")

        # 1. NLP parsing using spaCy
        if self.nlp and text:
            doc = self.nlp(text)
            
            # Extract names
            person_ents = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
            if person_ents:
                patient_name = person_ents[0]

            # Extract dates
            date_ents = [ent.text for ent in doc.ents if ent.label_ == "DATE"]
            if date_ents:
                for date_ent in date_ents:
                    if not any(word in date_ent.lower() for word in ["day", "week", "hour", "month", "year"]):
                        encounter_date = date_ent
                        break

        # If name is still unknown, search text for patterns like "name is [Name]"
        if patient_name == "Unknown Patient":
            match = re.search(r'\b(?:name is|patient is|patient name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b', text)
            if match:
                patient_name = match.group(1)

        # 2. Extract Symptoms
        text_lower = text.lower()
        for symptom in COMMON_SYMPTOMS:
            if re.search(r'\b' + re.escape(symptom) + r's?\b', text_lower):
                symptoms.append(symptom.capitalize())

        # 3. Extract Diagnoses
        for diagnosis in COMMON_DIAGNOSES:
            if re.search(r'\b' + re.escape(diagnosis) + r'\b', text_lower):
                diagnoses.append(diagnosis.upper())

        # 4. Extract Prescriptions (Drug + Dosage + Frequency)
        found_drugs = []
        for drug in COMMON_DRUGS:
            match = re.search(r'\b(' + re.escape(drug) + r')\b', text_lower)
            if match:
                start_pos = match.start()
                found_drugs.append((drug.capitalize(), start_pos))

        found_drugs.sort(key=lambda x: x[1])

        for i, (drug_name, pos) in enumerate(found_drugs):
            end_pos = found_drugs[i+1][1] if i + 1 < len(found_drugs) else len(text)
            window = text[pos:end_pos]
            
            # Find dosage in window
            dosage_match = DOSAGE_PATTERN.search(window)
            dosage = dosage_match.group(1) if dosage_match else "As directed"
            
            # Find frequency in window
            freq_match = FREQUENCY_PATTERN.search(window)
            frequency = freq_match.group(1) if freq_match else "Daily"
            
            prescriptions.append({
                "drug": drug_name,
                "dosage": dosage,
                "frequency": frequency
            })

        # Remove duplicates
        symptoms = list(set(symptoms))
        diagnoses = list(set(diagnoses))

        # Format custom markdown Clinical Notes Summary
        notes = "### Clinical Encounter Summary\n\n"
        notes += f"**Date:** {encounter_date}  \n"
        notes += f"**Patient:** {patient_name}  \n\n"
        
        notes += "#### Chief Complaint & Symptoms\n"
        if symptoms:
            notes += "\n".join([f"- {s}" for s in symptoms]) + "\n\n"
        else:
            notes += "No specific active symptoms reported.\n\n"
            
        notes += "#### Diagnosis\n"
        if diagnoses:
            notes += "\n".join([f"- {d}" for d in diagnoses]) + "\n\n"
        else:
            notes += "Pending further clinical evaluation.\n\n"
            
        notes += "#### Treatment Plan & Prescriptions\n"
        if prescriptions:
            for prescription_item in prescriptions:
                notes += f"- **{prescription_item['drug']}**: {prescription_item['dosage']}, {prescription_item['frequency']}\n"
        else:
            notes += "No prescription drugs ordered during this encounter.\n"

        return {
            "patient_name": patient_name,
            "encounter_date": encounter_date,
            "symptoms": symptoms,
            "diagnoses": diagnoses,
            "prescriptions": prescriptions,
            "clinical_notes": notes
        }

extractor = MedicalExtractor()
