#!/usr/bin/env python3
import os
import sys
import subprocess
import webbrowser
import time

def print_splash():
    splash = """
========================================================================
   __  ___        _ ___            _ _          
  /  |/  /__  ___/ / __/__________(_) /  ___ 
 / /|_/ / _ \/ _  /\ \/ __/ __/ __/ / _ \/ -_)
/_/  /_/\___/\_,_/\___/\__/_/ /_/ /_/_.__/\__/ 
                                             
  Ambient Clinical Audio Summarizer & EHR Auto-Parser
========================================================================
    """
    print(splash)
    print("⚡ Starting MedScribe Backend and Static Server...")
    print("⚡ Serving Frontend + REST API on http://127.0.0.1:8000")
    print("------------------------------------------------------------------------")

def check_dependencies():
    # Detect virtual env
    venv_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
    if not os.path.exists(venv_dir):
        print("❌ Warning: Virtual environment '.venv' not found.")
        print("Please set it up using: python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt")
        return False
    return True

def run_server():
    # Use python inside the venv to launch uvicorn
    venv_bin = "bin"
    if sys.platform == "win32":
        venv_bin = "Scripts"
    
    python_executable = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", venv_bin, "python")
    
    if not os.path.exists(python_executable):
        python_executable = "python3" # Fallback to system python

    # Launch uvicorn
    cmd = [
        python_executable, 
        "-m", 
        "uvicorn", 
        "backend.main:app", 
        "--host", "127.0.0.1", 
        "--port", "8000",
        "--reload"
    ]
    
    # Automatically open browser after 1.5 seconds
    try:
        print("⏳ Waiting for server to initialize...")
        time.sleep(1.5)
        print("🌐 Opening web browser at http://127.0.0.1:8000...")
        webbrowser.open("http://127.0.0.1:8000")
    except Exception as e:
        print(f"⚠️ Could not open browser: {e}")

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 MedScribe stopped. Thank you for using MedScribe!")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")

if __name__ == "__main__":
    print_splash()
    check_dependencies()
    run_server()
