#!/usr/bin/env python3
import sys
import os

# Set Python path to find backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.db import get_db
from backend.ai import extractor

def test_database():
    print("Testing Database Layer (SQLite/MongoDB Fallback)...")
    # Force SQLite for testing
    os.environ["SQLITE_DB_PATH"] = "test_db.sqlite3"
    db = get_db()
    
    # 1. Clear database encounters
    conn = db.encounters
    # SQLiteCollection mimics collections, delete_one clears
    # For a clean start, we can clear test data if present
    conn.delete_one({"patient_name": "Test Patient"})
    
    # 2. Insert record
    test_record = {
        "patient_name": "Test Patient",
        "encounter_date": "July 01, 2026",
        "transcript": "Hello Doctor, my name is Test Patient.",
        "symptoms": ["Headache", "Fever"],
        "diagnoses": ["MIGRAINE"],
        "prescriptions": [{"drug": "Aspirin", "dosage": "500mg", "frequency": "once daily"}],
        "clinical_notes": "Encounter notes go here."
    }
    
    result = conn.insert_one(test_record)
    assert result.inserted_id is not None
    print(f"✅ Document inserted successfully with ID: {result.inserted_id}")
    
    # 3. Find record
    found = conn.find_one({"_id": result.inserted_id})
    assert found is not None
    assert found["patient_name"] == "Test Patient"
    print("✅ Document retrieved and checked successfully.")
    
    # 4. Clean up test db file
    try:
        if os.path.exists("test_db.sqlite3"):
            os.remove("test_db.sqlite3")
        print("✅ Test database cleaned up successfully.")
    except Exception as e:
        print(f"⚠️ Error cleaning test DB file: {e}")

def test_extraction():
    print("\nTesting NLP Extraction Pipeline (spaCy + Custom Rules)...")
    test_text = (
        "Hello Doctor, my name is Alice Cooper. I have been suffering from a bad cough and sore throat "
        "for three days. Also I have a mild fever. I think I might have bronchitis. "
        "Doctor prescribed Amoxicillin 500mg three times a day."
    )
    
    result = extractor.extract_entities(test_text)
    
    # Validate details
    print(f"Input text: '{test_text}'")
    print(f"Extracted Patient Name: {result['patient_name']}")
    print(f"Extracted Symptoms: {result['symptoms']}")
    print(f"Extracted Diagnoses: {result['diagnoses']}")
    print(f"Extracted Prescriptions: {result['prescriptions']}")
    
    assert result["patient_name"] == "Alice Cooper", f"Expected Alice Cooper, got {result['patient_name']}"
    assert "Cough" in result["symptoms"], "Cough symptom extraction failed"
    assert "Fever" in result["symptoms"], "Fever symptom extraction failed"
    assert "BRONCHITIS" in result["diagnoses"], "Bronchitis diagnosis extraction failed"
    assert len(result["prescriptions"]) > 0, "Prescription extraction failed"
    assert result["prescriptions"][0]["drug"] == "Amoxicillin", "Prescription drug name extraction failed"
    assert result["prescriptions"][0]["dosage"] == "500mg", "Prescription dosage extraction failed"
    
    print("✅ NLP Extraction verified successfully.")

if __name__ == "__main__":
    try:
        test_database()
        test_extraction()
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! The backend is ready to run.")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ Test verification failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test verification threw an exception: {e}")
        sys.exit(1)
