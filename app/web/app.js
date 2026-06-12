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
        
        // Log the backend response just in case you need to debug extraction data
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
    // Generalized the project name
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
   CHAT FUNCTIONALITY
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
    aiDiv.textContent = "Thinking...";

    try {
        const response = await fetch("/query/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question })
        });

        if (!response.ok) throw new Error("Server error");
        
        const data = await response.json();
        aiDiv.classList.remove("thinking");

        // Use Marked.js to parse Markdown into beautiful HTML
        marked.setOptions({ breaks: true });
        const formattedAnswer = data.answer ? marked.parse(data.answer) : "No answer provided.";

        // Format the answer with sources
        aiDiv.innerHTML = `
            <div class="markdown-body">
                ${formattedAnswer}
            </div>
            ${data.sources && data.sources.length > 0 
                ? `<div class="sources" style="margin-top:15px; font-size:0.85em; color:#666; border-top: 1px solid #eee; padding-top: 8px;">
                    <strong>Sources:</strong> ${data.sources.join(", ")}
                </div>` 
                : ""
            }
        `;

    } catch (error) {
        console.error("Chat Error:", error);
        aiDiv.classList.remove("thinking");
        aiDiv.classList.add("error");
        aiDiv.textContent = "⚠️ Error: Could not connect to service.";
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
            
            const delBtn = document.createElement("button");
            delBtn.className = "delete-btn";
            delBtn.innerHTML = "🗑️";
            delBtn.onclick = () => deleteDocument(doc);

            div.appendChild(delBtn);
            documentsContainer.appendChild(div);
        });
    } catch (error) {
        documentsContainer.innerHTML = "<p class='error-state'>Error loading documents.</p>";
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