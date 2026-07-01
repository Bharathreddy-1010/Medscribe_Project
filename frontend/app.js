// MedScribe Frontend Application Controller

const API_BASE = window.location.origin.includes("file://") || window.location.origin === "null" || !window.location.origin ? "http://127.0.0.1:8000/api" : "/api";

// App State
let appState = {
    mediaRecorder: null,
    audioChunks: [],
    audioContext: null,
    analyser: null,
    dataArray: null,
    visualizerAnimationId: null,
    stream: null,
    
    // Timer state
    startTime: null,
    timerIntervalId: null,
    
    // Active Record State
    activeEncounterId: null, // If editing an existing one
    symptoms: [],
    diagnoses: [],
    prescriptions: [],
    
    // Lists cached from db
    encounters: []
};

// DOM Elements
const el = {
    btnRecord: document.getElementById("btn-record"),
    btnStop: document.getElementById("btn-stop"),
    btnSave: document.getElementById("btn-save"),
    btnEditTranscript: document.getElementById("btn-edit-transcript"),
    recordingTimer: document.getElementById("recording-timer"),
    recordingIndicator: document.getElementById("recording-indicator"),
    waveformCanvas: document.getElementById("waveform-canvas"),
    dropZone: document.getElementById("drop-zone"),
    fileInput: document.getElementById("file-input"),
    transcriptView: document.getElementById("transcript-view"),
    transcriptTextarea: document.getElementById("transcript-textarea"),
    processingSpinner: document.getElementById("processing-spinner"),
    
    // Form fields
    patientName: document.getElementById("patient-name"),
    encounterDate: document.getElementById("encounter-date"),
    symptomsContainer: document.getElementById("symptoms-container"),
    diagnosesContainer: document.getElementById("diagnoses-container"),
    prescriptionsTable: document.getElementById("prescriptions-table").querySelector("tbody"),
    clinicalNotes: document.getElementById("clinical-notes"),
    notesPreview: document.getElementById("notes-preview"),
    
    // Tag and prescription input rows
    inputSymptom: document.getElementById("input-symptom"),
    btnAddSymptom: document.getElementById("btn-add-symptom"),
    inputDiagnosis: document.getElementById("input-diagnosis"),
    btnAddDiagnosis: document.getElementById("btn-add-diagnosis"),
    inputDrug: document.getElementById("input-drug"),
    inputDosage: document.getElementById("input-dosage"),
    inputFrequency: document.getElementById("input-frequency"),
    btnAddPrescription: document.getElementById("btn-add-prescription"),
    
    // Tabs
    tabBtnWrite: document.getElementById("tab-btn-write"),
    tabBtnPreview: document.getElementById("tab-btn-preview"),
    
    // History
    searchHistory: document.getElementById("search-history"),
    historyGrid: document.getElementById("history-grid"),
    historyEmpty: document.getElementById("history-empty"),
    statusText: document.getElementById("status-text")
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
    setupEventListeners();
    fetchHistory();
    setDefaultDate();
    initCanvasPlaceholder();
});

// Set default date to today
function setDefaultDate() {
    const today = new Date();
    const options = { year: 'numeric', month: 'long', day: 'numeric' };
    el.encounterDate.value = today.toLocaleDateString('en-US', options);
}

// Draw a flat wave on canvas initially
function initCanvasPlaceholder() {
    const canvas = el.waveformCanvas;
    const ctx = canvas.getContext("2d");
    const width = canvas.width = canvas.parentElement.clientWidth;
    const height = canvas.height = canvas.parentElement.clientHeight;
    
    ctx.clearRect(0, 0, width, height);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "rgba(6, 182, 212, 0.4)";
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();
}

// Event Listeners Setup
function setupEventListeners() {
    // Recording controls
    el.btnRecord.addEventListener("click", startRecording);
    el.btnStop.addEventListener("click", stopRecording);
    
    // File upload
    el.fileInput.addEventListener("change", handleFileSelect);
    
    // Drag and drop events
    ["dragenter", "dragover"].forEach(eventName => {
        el.dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            el.dropZone.classList.add("dragover");
        }, false);
    });
    
    ["dragleave", "drop"].forEach(eventName => {
        el.dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            el.dropZone.classList.remove("dragover");
        }, false);
    });
    
    el.dropZone.addEventListener("drop", (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            uploadAudioFile(files[0]);
        }
    });

    // Tag additions
    el.btnAddSymptom.addEventListener("click", () => {
        const val = el.inputSymptom.value.trim();
        if (val) {
            addSymptomTag(val);
            el.inputSymptom.value = "";
        }
    });
    
    el.btnAddDiagnosis.addEventListener("click", () => {
        const val = el.inputDiagnosis.value.trim();
        if (val) {
            addDiagnosisTag(val);
            el.inputDiagnosis.value = "";
        }
    });

    el.btnAddPrescription.addEventListener("click", () => {
        const drug = el.inputDrug.value.trim();
        const dosage = el.inputDosage.value.trim() || "As directed";
        const frequency = el.inputFrequency.value.trim() || "Daily";
        if (drug) {
            addPrescriptionRow(drug, dosage, frequency);
            el.inputDrug.value = "";
            el.inputDosage.value = "";
            el.inputFrequency.value = "";
        }
    });

    // Transcript manual edit toggling
    el.btnEditTranscript.addEventListener("click", toggleTranscriptEdit);

    // Markdown tabs
    el.tabBtnWrite.addEventListener("click", showWriteTab);
    el.tabBtnPreview.addEventListener("click", showPreviewTab);

    // Form submission/Save
    document.getElementById("ehr-form").addEventListener("submit", (e) => e.preventDefault());
    el.btnSave.addEventListener("click", saveEncounter);

    // History search
    el.searchHistory.addEventListener("input", debounce((e) => {
        fetchHistory(e.target.value);
    }, 300));
}

// -------------------------------------------------------------
// Audio Recording Logic
// -------------------------------------------------------------
async function startRecording() {
    appState.audioChunks = [];
    
    try {
        appState.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        // Setup Media Recorder
        // Use standard mimeTypes supported in browsers
        let mimeType = "audio/webm";
        if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = "audio/ogg";
        }
        if (!MediaRecorder.isTypeSupported(mimeType)) {
            mimeType = ""; // fallback
        }
        
        appState.mediaRecorder = new MediaRecorder(appState.stream, mimeType ? { mimeType } : undefined);
        
        appState.mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                appState.audioChunks.push(event.data);
            }
        };
        
        appState.mediaRecorder.onstop = handleRecordingStop;
        
        // Start recording
        appState.mediaRecorder.start(250); // Get chunks every 250ms
        
        // UI Updates
        el.btnRecord.classList.add("hidden");
        el.btnStop.classList.remove("hidden");
        el.btnStop.removeAttribute("disabled");
        el.recordingIndicator.classList.remove("hidden");
        
        // Timer
        appState.startTime = Date.now();
        updateTimer();
        appState.timerIntervalId = setInterval(updateTimer, 1000);
        
        // Start Visualizer
        startVisualizer(appState.stream);
        
    } catch (err) {
        console.error("Error accessing microphone:", err);
        alert("Microphone access denied. Please grant microphone permissions and try again.");
    }
}

function stopRecording() {
    if (appState.mediaRecorder && appState.mediaRecorder.state !== "inactive") {
        appState.mediaRecorder.stop();
    }
    
    // Stop recording track streams
    if (appState.stream) {
        appState.stream.getTracks().forEach(track => track.stop());
    }
    
    // Stop Timer
    clearInterval(appState.timerIntervalId);
    el.recordingIndicator.classList.add("hidden");
    
    // UI resets
    el.btnRecord.classList.remove("hidden");
    el.btnStop.classList.add("hidden");
    el.btnStop.setAttribute("disabled", "true");
    
    // Stop visualizer animation
    if (appState.visualizerAnimationId) {
        cancelAnimationFrame(appState.visualizerAnimationId);
    }
    initCanvasPlaceholder();
}

function updateTimer() {
    const elapsedMs = Date.now() - appState.startTime;
    const totalSecs = Math.floor(elapsedMs / 1000);
    const mins = String(Math.floor(totalSecs / 60)).padStart(2, "0");
    const secs = String(totalSecs % 60).padStart(2, "0");
    el.recordingTimer.textContent = `${mins}:${secs}`;
}

function handleRecordingStop() {
    const audioBlob = new Blob(appState.audioChunks, { type: "audio/webm" });
    const audioFile = new File([audioBlob], "recorded_consultation.webm", { type: "audio/webm" });
    uploadAudioFile(audioFile);
}

// -------------------------------------------------------------
// Canvas Live Waveform Visualizer
// -------------------------------------------------------------
function startVisualizer(stream) {
    appState.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = appState.audioContext.createMediaStreamSource(stream);
    appState.analyser = appState.audioContext.createAnalyser();
    appState.analyser.fftSize = 256;
    
    source.connect(appState.analyser);
    
    const bufferLength = appState.analyser.frequencyBinCount;
    appState.dataArray = new Uint8Array(bufferLength);
    
    const canvas = el.waveformCanvas;
    const canvasCtx = canvas.getContext("2d");
    const width = canvas.width = canvas.parentElement.clientWidth;
    const height = canvas.height = canvas.parentElement.clientHeight;
    
    function draw() {
        appState.visualizerAnimationId = requestAnimationFrame(draw);
        appState.analyser.getByteTimeDomainData(appState.dataArray);
        
        canvasCtx.fillStyle = "rgba(11, 15, 25, 1)";
        canvasCtx.fillRect(0, 0, width, height);
        
        canvasCtx.lineWidth = 3;
        
        // Draw elegant gradient path
        const gradient = canvasCtx.createLinearGradient(0, 0, width, 0);
        gradient.addColorStop(0, '#0d9488');
        gradient.addColorStop(0.5, '#06b6d4');
        gradient.addColorStop(1, '#3b82f6');
        canvasCtx.strokeStyle = gradient;
        
        canvasCtx.beginPath();
        
        const sliceWidth = width * 1.0 / bufferLength;
        let x = 0;
        
        for (let i = 0; i < bufferLength; i++) {
            const v = appState.dataArray[i] / 128.0;
            const y = v * height / 2;
            
            if (i === 0) {
                canvasCtx.moveTo(x, y);
            } else {
                canvasCtx.lineTo(x, y);
            }
            
            x += sliceWidth;
        }
        
        canvasCtx.lineTo(canvas.width, canvas.height / 2);
        canvasCtx.stroke();
    }
    
    draw();
}

// -------------------------------------------------------------
// File Selection & Upload
// -------------------------------------------------------------
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        uploadAudioFile(file);
    }
}

async function uploadAudioFile(file) {
    // Clear form state
    appState.activeEncounterId = null;
    appState.symptoms = [];
    appState.diagnoses = [];
    appState.prescriptions = [];
    renderTags();
    renderPrescriptions();
    
    // Toggle Loading
    el.processingSpinner.classList.remove("hidden");
    el.statusText.textContent = "Analyzing Audio...";
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const response = await fetch(`${API_BASE}/transcribe`, {
            method: "POST",
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`Server returned error status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Load transcription
        el.transcriptView.textContent = data.transcript;
        el.transcriptTextarea.value = data.transcript;
        
        // Load parsed EHR fields
        el.patientName.value = data.patient_name;
        el.encounterDate.value = data.encounter_date;
        
        // Tags
        appState.symptoms = data.symptoms;
        appState.diagnoses = data.diagnoses;
        appState.prescriptions = data.prescriptions;
        
        renderTags();
        renderPrescriptions();
        
        // Notes
        el.clinicalNotes.value = data.clinical_notes;
        el.notesPreview.innerHTML = parseMarkdown(data.clinical_notes);
        
        // Activate Save button
        el.btnSave.removeAttribute("disabled");
        el.statusText.textContent = "EHR Parsed successfully";
        
    } catch (err) {
        console.error("Transcription failed:", err);
        alert(`Failed to transcribe audio: ${err.message}`);
        el.statusText.textContent = "Processing Failed";
    } finally {
        el.processingSpinner.classList.add("hidden");
    }
}

// -------------------------------------------------------------
// Tags & Prescription Rendering
// -------------------------------------------------------------
function addSymptomTag(symptom) {
    symptom = capitalize(symptom);
    if (!appState.symptoms.includes(symptom)) {
        appState.symptoms.push(symptom);
        renderTags();
        generateUpdatedNotes();
    }
}

function removeSymptomTag(index) {
    appState.symptoms.splice(index, 1);
    renderTags();
    generateUpdatedNotes();
}

function addDiagnosisTag(diagnosis) {
    diagnosis = diagnosis.toUpperCase();
    if (!appState.diagnoses.includes(diagnosis)) {
        appState.diagnoses.push(diagnosis);
        renderTags();
        generateUpdatedNotes();
    }
}

function removeDiagnosisTag(index) {
    appState.diagnoses.splice(index, 1);
    renderTags();
    generateUpdatedNotes();
}

function renderTags() {
    // Render Symptoms
    el.symptomsContainer.innerHTML = "";
    appState.symptoms.forEach((s, idx) => {
        const tag = document.createElement("div");
        tag.className = "tag symptom";
        tag.innerHTML = `${s} <span class="tag-remove" onclick="removeSymptomTag(${idx})">×</span>`;
        el.symptomsContainer.appendChild(tag);
    });

    // Render Diagnoses
    el.diagnosesContainer.innerHTML = "";
    appState.diagnoses.forEach((d, idx) => {
        const tag = document.createElement("div");
        tag.className = "tag diagnosis";
        tag.innerHTML = `${d} <span class="tag-remove" onclick="removeDiagnosisTag(${idx})">×</span>`;
        el.diagnosesContainer.appendChild(tag);
    });
}

function addPrescriptionRow(drug, dosage, frequency) {
    appState.prescriptions.push({
        drug: capitalize(drug),
        dosage,
        frequency
    });
    renderPrescriptions();
    generateUpdatedNotes();
}

function removePrescriptionRow(index) {
    appState.prescriptions.splice(index, 1);
    renderPrescriptions();
    generateUpdatedNotes();
}

function renderPrescriptions() {
    el.prescriptionsTable.innerHTML = "";
    if (appState.prescriptions.length === 0) {
        const row = document.createElement("tr");
        row.innerHTML = `<td colspan="4" style="text-align: center; color: var(--text-secondary); font-style: italic;">No medications prescribed.</td>`;
        el.prescriptionsTable.appendChild(row);
        return;
    }

    appState.prescriptions.forEach((p, idx) => {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td><strong>${p.drug}</strong></td>
            <td>${p.dosage}</td>
            <td>${p.frequency}</td>
            <td><button type="button" class="btn-card-action delete" onclick="removePrescriptionRow(${idx})" style="font-size: 14px;">🗑️</button></td>
        `;
        el.prescriptionsTable.appendChild(row);
    });
}

// -------------------------------------------------------------
// Transcript editing
// -------------------------------------------------------------
function toggleTranscriptEdit() {
    const isViewing = el.transcriptTextarea.classList.contains("hidden");
    if (isViewing) {
        // Switch to Edit Mode
        el.transcriptTextarea.value = el.transcriptView.textContent;
        el.transcriptView.classList.add("hidden");
        el.transcriptTextarea.classList.remove("hidden");
        el.btnEditTranscript.textContent = "✅";
    } else {
        // Save changes back
        const updatedText = el.transcriptTextarea.value;
        el.transcriptView.textContent = updatedText;
        el.transcriptTextarea.classList.add("hidden");
        el.transcriptView.classList.remove("hidden");
        el.btnEditTranscript.textContent = "✏️";
        
        // Re-extract tags dynamically if needed
        reprocessText(updatedText);
    }
}

async function reprocessText(text) {
    if (!text.trim()) return;
    
    // We can simulate re-extraction locally to speed up or query a simple API
    // To be clean, we can make an internal check or rely on local NLP rules
    // Let's send a dummy update or parse client-side to make the UI instant!
    // We will extract elements client-side to avoid uploading file again
    
    // Extract name
    const nameMatch = text.match(/\b(?:name is|patient is|patient name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b/);
    if (nameMatch) {
        el.patientName.value = nameMatch.group ? nameMatch[1] : nameMatch;
    }
    
    // Simple word matches for symptoms
    const words = text.toLowerCase();
    const testSymptoms = ["fever", "cough", "shortness of breath", "fatigue", "headache", "throat", "vomiting", "nausea"];
    testSymptoms.forEach(s => {
        if (words.includes(s) && !appState.symptoms.includes(capitalize(s))) {
            appState.symptoms.push(capitalize(s));
        }
    });

    const testDiagnoses = ["hypertension", "diabetes", "asthma", "bronchitis", "pneumonia", "gerd", "uti"];
    testDiagnoses.forEach(d => {
        if (words.includes(d) && !appState.diagnoses.includes(d.toUpperCase())) {
            appState.diagnoses.push(d.toUpperCase());
        }
    });

    renderTags();
    generateUpdatedNotes();
}

// -------------------------------------------------------------
// Notes Tabs & Markdown
// -------------------------------------------------------------
function showWriteTab() {
    el.tabBtnWrite.classList.add("active");
    el.tabBtnPreview.classList.remove("active");
    el.clinicalNotes.classList.remove("hidden");
    el.notesPreview.classList.add("hidden");
}

function showPreviewTab() {
    el.tabBtnWrite.classList.remove("active");
    el.tabBtnPreview.classList.add("active");
    el.clinicalNotes.classList.add("hidden");
    
    // Render Markdown
    const notesText = el.clinicalNotes.value;
    el.notesPreview.innerHTML = parseMarkdown(notesText);
    el.notesPreview.classList.remove("hidden");
}

function parseMarkdown(md) {
    if (!md) return "<i>No clinical notes summary available.</i>";
    
    let html = md
        .replace(/### (.*)/g, '<h3>$1</h3>')
        .replace(/#### (.*)/g, '<h4>$1</h4>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/- (.*)/g, '<li>$1</li>');
        
    // Wrap lists nicely
    html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
    return html.replace(/\n/g, '<br>');
}

// Generate updated markdown summary based on current form details
function generateUpdatedNotes() {
    const dateVal = el.encounterDate.value;
    const nameVal = el.patientName.value || "Unknown Patient";
    
    let notes = `### Clinical Encounter Summary\n\n`;
    notes += `**Date:** ${dateVal}  \n`;
    notes += `**Patient:** ${nameVal}  \n\n`;
    
    notes += `#### Chief Complaint & Symptoms\n`;
    if (appState.symptoms.length > 0) {
        notes += appState.symptoms.map(s => `- ${s}`).join("\n") + "\n\n";
    } else {
        notes += `No specific active symptoms reported.\n\n`;
    }
    
    notes += `#### Diagnosis\n`;
    if (appState.diagnoses.length > 0) {
        notes += appState.diagnoses.map(d => `- ${d}`).join("\n") + "\n\n";
    } else {
        notes += `Pending further clinical evaluation.\n\n`;
    }
    
    notes += `#### Treatment Plan & Prescriptions\n`;
    if (appState.prescriptions.length > 0) {
        notes += appState.prescriptions.map(p => `- **${p.drug}**: ${p.dosage}, ${p.frequency}`).join("\n") + "\n";
    } else {
        notes += `No prescription drugs ordered during this encounter.\n`;
    }
    
    el.clinicalNotes.value = notes;
    el.notesPreview.innerHTML = parseMarkdown(notes);
}

// -------------------------------------------------------------
// Database Encounters CRUD Operations
// -------------------------------------------------------------
async function fetchHistory(searchQuery = "") {
    let url = `${API_BASE}/encounters`;
    if (searchQuery) {
        url += `?search=${encodeURIComponent(searchQuery)}`;
    }
    
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error("History fetch failed");
        
        const data = await response.json();
        appState.encounters = data;
        renderHistoryGrid();
    } catch (err) {
        console.error("Error fetching encounters:", err);
        el.statusText.textContent = "History Load Error";
    }
}

function renderHistoryGrid() {
    el.historyGrid.innerHTML = "";
    
    if (appState.encounters.length === 0) {
        el.historyGrid.classList.add("hidden");
        el.historyEmpty.classList.remove("hidden");
        return;
    }
    
    el.historyEmpty.classList.add("hidden");
    el.historyGrid.classList.remove("hidden");
    
    appState.encounters.forEach(item => {
        const card = document.createElement("div");
        card.className = "history-card";
        
        // Highlight active card
        if (appState.activeEncounterId === item._id) {
            card.style.borderColor = "var(--accent-cyan)";
            card.style.background = "rgba(6, 182, 212, 0.05)";
        }
        
        card.addEventListener("click", (e) => {
            // Prevent loading card on action button clicks
            if (e.target.tagName !== "BUTTON") {
                loadEncounter(item);
            }
        });
        
        // Render tags snippet
        let tagsHtml = "";
        item.symptoms.slice(0, 3).forEach(s => {
            tagsHtml += `<span class="history-card-tag sym">${s}</span>`;
        });
        item.diagnoses.slice(0, 2).forEach(d => {
            tagsHtml += `<span class="history-card-tag dia">${d}</span>`;
        });
        
        card.innerHTML = `
            <div class="history-card-header">
                <span class="history-card-name">${item.patient_name}</span>
                <span class="history-card-date">${item.encounter_date}</span>
            </div>
            <div class="history-card-details">
                <div class="history-card-tags">${tagsHtml}</div>
            </div>
            <div class="history-card-actions">
                <button class="btn-card-action load">Edit Record ↗</button>
                <button class="btn-card-action delete" onclick="deleteEncounter('${item._id}')">Delete</button>
            </div>
        `;
        
        el.historyGrid.appendChild(card);
    });
}

function loadEncounter(item) {
    appState.activeEncounterId = item._id;
    
    el.patientName.value = item.patient_name;
    el.encounterDate.value = item.encounter_date;
    el.transcriptView.textContent = item.transcript;
    el.transcriptTextarea.value = item.transcript;
    
    appState.symptoms = [...item.symptoms];
    appState.diagnoses = [...item.diagnoses];
    appState.prescriptions = [...item.prescriptions];
    
    renderTags();
    renderPrescriptions();
    
    el.clinicalNotes.value = item.clinical_notes;
    el.notesPreview.innerHTML = parseMarkdown(item.clinical_notes);
    
    el.btnSave.removeAttribute("disabled");
    renderHistoryGrid(); // Update highlights
    el.statusText.textContent = `Editing: ${item.patient_name}`;
}

async function saveEncounter() {
    const payload = {
        patient_name: el.patientName.value.trim(),
        encounter_date: el.encounterDate.value.trim(),
        transcript: el.transcriptView.textContent,
        symptoms: appState.symptoms,
        diagnoses: appState.diagnoses,
        prescriptions: appState.prescriptions,
        clinical_notes: el.clinicalNotes.value
    };
    
    if (!payload.patient_name || !payload.encounter_date) {
        alert("Patient Name and Encounter Date are required.");
        return;
    }
    
    const isUpdate = appState.activeEncounterId !== null;
    const url = isUpdate 
        ? `${API_BASE}/encounters/${appState.activeEncounterId}` 
        : `${API_BASE}/encounters`;
        
    const method = isUpdate ? "PUT" : "POST";
    
    try {
        el.statusText.textContent = "Saving Record...";
        const response = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) throw new Error("Failed to save encounter");
        
        const saved = await response.json();
        
        appState.activeEncounterId = saved._id;
        el.statusText.textContent = "Record Saved";
        
        // Refresh grid
        await fetchHistory();
        
    } catch (err) {
        console.error("Save failed:", err);
        alert(`Error saving clinical record: ${err.message}`);
        el.statusText.textContent = "Save Failed";
    }
}

async function deleteEncounter(id) {
    if (!confirm("Are you sure you want to delete this clinical encounter record?")) return;
    
    try {
        const response = await fetch(`${API_BASE}/encounters/${id}`, {
            method: "DELETE"
        });
        
        if (!response.ok) throw new Error("Delete failed");
        
        if (appState.activeEncounterId === id) {
            // Reset active form if we deleted the loaded record
            appState.activeEncounterId = null;
            el.patientName.value = "";
            setDefaultDate();
            el.transcriptView.textContent = "";
            appState.symptoms = [];
            appState.diagnoses = [];
            appState.prescriptions = [];
            renderTags();
            renderPrescriptions();
            el.clinicalNotes.value = "";
            el.notesPreview.innerHTML = "";
            el.btnSave.setAttribute("disabled", "true");
        }
        
        el.statusText.textContent = "Record Deleted";
        await fetchHistory();
    } catch (err) {
        console.error("Delete failed:", err);
        alert(`Failed to delete record: ${err.message}`);
    }
}

// -------------------------------------------------------------
// Utilities
// -------------------------------------------------------------
function capitalize(str) {
    if (!str) return "";
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
