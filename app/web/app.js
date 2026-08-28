/**
 * RAG AI System - Frontend Logic (Consolidated)
 */

// --- DOM Elements ---
const chat = document.getElementById("chat");
const questionInput = document.getElementById("question");
const sendBtn = document.getElementById("sendBtn");
const dropZone = document.getElementById("dropZone");
const fileInput = document.getElementById("fileInput");
const fileNameDisplay = document.getElementById("fileName");
const progressBar = document.getElementById("progress");
const documentsContainer = document.getElementById("documents");

/* =========================================
   FILE MANAGEMENT (BUNDLE UPLOAD)
   ========================================= */
if (dropZone && fileInput) {
    dropZone.addEventListener("click", () => fileInput.click());
}

fileInput.style.display = "none"; 

fileInput.addEventListener("change", async () => {
    const files = fileInput.files;
    if (files.length === 0) return;
    await handleFiles(files);
});

dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
});

dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("dragover");
});

dropZone.addEventListener("drop", async (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    const files = e.dataTransfer.files;
    if (files.length > 0) await handleFiles(files);
});

async function handleFiles(files) {
    fileNameDisplay.textContent = `Analyzing bundle of ${files.length} file(s)...`;
    progressBar.style.width = "50%";

    try {
        const responseData = await uploadBundle(files);

        fileNameDisplay.textContent = "Analysis complete!";
        progressBar.style.width = "100%";

        const aiDiv = createMessageElement("ai system");
        aiDiv.innerHTML = `
            <b>📂 Documents Uploaded Successfully</b><br>
            ${[...files].map(f => "• " + f.name).join("<br>")}
        `;
        
        console.log("Extraction Data:", responseData);

    } catch (error) {
        console.error("Bundle upload failed:", error);
        alert("Failed to process the document bundle.");
        progressBar.style.width = "0%";
    }

    setTimeout(() => {
        fileNameDisplay.textContent = "";
        progressBar.style.width = "0%";
    }, 3000);

    loadDocuments();
}

async function uploadBundle(files) {
    const formData = new FormData();
    formData.append("project_name", "Document Analysis " + new Date().toLocaleTimeString());
    
    for (let i = 0; i < files.length; i++) {
        formData.append("files", files[i]);
    }

    const response = await fetch("/upload/bundle", {
        method: "POST",
        body: formData
    });

    if (!response.ok) {
        throw new Error(response.statusText);
    }
    
    return await response.json();
}


/* =========================================
   AGENT CHAT FUNCTIONALITY
   ========================================= */

function createMessageElement(type) {
    const div = document.createElement("div");
    div.className = `message ${type}`;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}

async function askAI() {
    const question = questionInput.value.trim();
    if (!question) return;

    // 1. Lock UI
    questionInput.disabled = true;
    sendBtn.disabled = true;

    // 2. Display user message
    createMessageElement("user").textContent = question;
    questionInput.value = "";
    
    const aiDiv = createMessageElement("ai thinking");
    aiDiv.textContent = "Agent is reasoning..."; // Updated UX copy

    try {
        // 🚀 Hit the new Multi-Agent Endpoint
        const response = await fetch("/api/v1/agents/agent", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: question }) // Mapped to the new Pydantic schema
        });

        if (!response.ok) throw new Error("Server error");
        
        const data = await response.json();
        aiDiv.classList.remove("thinking");

        // Use Marked.js to parse Markdown into beautiful HTML
        marked.setOptions({ breaks: true });
        
        // The new Agent response model returns 'answer'
        const formattedAnswer = data.answer ? marked.parse(data.answer) : "No answer provided.";

        aiDiv.innerHTML = `
            <div class="markdown-body">
                ${formattedAnswer}
            </div>
        `;

    } catch (error) {
        console.error("Chat Error:", error);
        aiDiv.classList.remove("thinking");
        aiDiv.classList.add("error");
        aiDiv.textContent = "⚠️ Error: Could not connect to the Agent service.";
    } finally {
        // 3. Unlock UI (Crucial)
        questionInput.disabled = false;
        sendBtn.disabled = false;
        questionInput.focus();
        chat.scrollTop = chat.scrollHeight;
    }
}

/* =========================================
   DOCUMENT MANAGEMENT
   ========================================= */

async function loadDocuments() {
    try {
        const response = await fetch("/documents");
        const data = await response.json();
        documentsContainer.innerHTML = "";

        if (!data.documents || data.documents.length === 0) {
            documentsContainer.innerHTML = "<p class='empty-state'>No documents uploaded yet.</p>";
            return;
        }

        data.documents.forEach(doc => {
            const div = document.createElement("div");
            div.className = "document-item";
            div.innerHTML = `<span class="doc-name">${doc}</span>`;
            
            // Container for buttons
            const actionsDiv = document.createElement("div");
            actionsDiv.className = "doc-actions";
            
            // New Analyze Button
            const analyzeBtn = document.createElement("button");
            analyzeBtn.className = "analyze-btn";
            analyzeBtn.innerHTML = "⚡ Analyze";
            analyzeBtn.style.marginRight = "8px"; // Quick inline styling
            analyzeBtn.onclick = () => triggerFullAnalysis(doc);
            
            // Delete Button
            const delBtn = document.createElement("button");
            delBtn.className = "delete-btn";
            delBtn.innerHTML = "🗑️";
            delBtn.onclick = () => deleteDocument(doc);

            actionsDiv.appendChild(analyzeBtn);
            actionsDiv.appendChild(delBtn);
            
            div.appendChild(actionsDiv);
            documentsContainer.appendChild(div);
        });
    } catch (error) {
        documentsContainer.innerHTML = "<p class='error-state'>Error loading documents.</p>";
    }
}

async function triggerFullAnalysis(filename) {
    // 1. Show processing state
    const aiDiv = createMessageElement("ai thinking");
    aiDiv.innerHTML = `Running Multi-Agent Analysis on <b>${filename}</b>...<br><small>This may take a minute.</small>`;

    try {
        // 2. Call the dedicated sequential pipeline endpoint
        const response = await fetch("/api/v1/agents/analyze-rag", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ file_path: `uploads/${filename}` }) 
        });

        if (!response.ok) throw new Error("Server error");
        
        const result = await response.json();
        aiDiv.classList.remove("thinking");

        // 3. Format the heavy JSON payload into a readable report
        if (result.status === "success") {
            const data = result.data;
            aiDiv.innerHTML = `
                <div class="markdown-body">
                    <h3>📄 Executive Summary: ${filename}</h3>
                    <p>${data.summary.summary}</p>
                    
                    <h4>🔑 Key Points</h4>
                    <ul>${data.summary.key_points.map(p => `<li>${p}</li>`).join('')}</ul>
                    
                    <h4>⚠️ Risk Assessment</h4>
                    <p><b>Overall Risk Level:</b> ${data.risk.risk_level}</p>
                    <ul>${data.risk.risks.map(r => `<li>${r}</li>`).join('')}</ul>
                    
                    <h4>📦 Bill of Quantities (${data.boq.boq_items.length} items)</h4>
                    <p><i>Ask the chat for specific BOQ calculations.</i></p>
                </div>
            `;
        } else {
            aiDiv.classList.add("error");
            aiDiv.textContent = "Analysis failed: " + result.message;
        }

    } catch (error) {
        console.error("Analysis Error:", error);
        aiDiv.classList.remove("thinking");
        aiDiv.classList.add("error");
        aiDiv.textContent = "⚠️ Error: Could not complete document analysis.";
    }
}

async function deleteDocument(filename) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;
    try {
        await fetch(`/delete/${filename}`, { method: "DELETE" });
        loadDocuments();
    } catch (error) {
        alert("Error deleting document.");
    }
}

// Final Event Listeners
sendBtn.onclick = askAI;
questionInput.onkeydown = (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        askAI();
    }
};

// Initial Load
loadDocuments();
