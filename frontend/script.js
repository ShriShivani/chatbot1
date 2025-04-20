// 🔐 Persistent User ID and Conversation ID using localStorage
let user_id = localStorage.getItem("user_id") || `user_${Math.floor(Math.random() * 1000000)}`;
localStorage.setItem("user_id", user_id);

let conversation_id = localStorage.getItem("conversation_id") || null;

// Send message to FastAPI backend
function sendMessage() {
    const inputField = document.getElementById("user-input");
    const chatBox = document.getElementById("chat-box");
    const userText = inputField.value.trim();

    if (!userText) return;

    // Show user message
    const userMessage = document.createElement("p");
    userMessage.className = "user-message";
    userMessage.innerText = userText;
    chatBox.appendChild(userMessage);
    chatBox.scrollTop = chatBox.scrollHeight;

    // Prepare payload
    const payload = {
        message: userText,
        user_id: user_id,
        conversation_id: conversation_id
    };

    fetch("http://127.0.0.1:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.reply) {
            const botMessage = document.createElement("p");
            botMessage.className = "bot-message";
            botMessage.innerText = data.reply;
            chatBox.appendChild(botMessage);
            chatBox.scrollTop = chatBox.scrollHeight;

            // Update stored conversation ID
            if (data.conversation_id) {
                conversation_id = data.conversation_id;
                localStorage.setItem("conversation_id", conversation_id);
            }
        }
    })
    .catch(error => {
        console.error("Error sending message:", error);
        const errorMsg = document.createElement("p");
        errorMsg.className = "bot-message";
        errorMsg.innerText = "❌ Something went wrong. Please try again.";
        chatBox.appendChild(errorMsg);
    });

    inputField.value = "";
}

// Initial backend greeting
async function getMessage() {
    try {
        let response = await fetch("http://127.0.0.1:8000/");
        let data = await response.json();
        document.getElementById("output").innerText = data.message;
    } catch (error) {
        console.error("Error fetching backend greeting:", error);
    }
}

// Enable "Enter" key to send messages
window.onload = function () {
    getMessage();
    document.getElementById("user-input").addEventListener("keypress", function (event) {
        if (event.key === "Enter") {
            sendMessage();
        }
    });
};

// ✅ Upload resume and match jobs
function uploadResume() {
    const fileInput = document.getElementById("resume-file");
    const file = fileInput.files[0];
    const chatBox = document.getElementById("chat-box");

    if (!file) {
        alert("📂 Please choose a PDF file to upload.");
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    // Show status
    const statusMsg = document.createElement("p");
    statusMsg.className = "bot-message";
    statusMsg.innerText = "📤 Uploading resume and analyzing...";
    chatBox.appendChild(statusMsg);
    chatBox.scrollTop = chatBox.scrollHeight;

    fetch("http://127.0.0.1:8000/upload-resume/", {
        method: "POST",
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.summary || data.skills_detected) {
            const resumeInfo = document.createElement("p");
            resumeInfo.className = "bot-message";
            resumeInfo.innerHTML = `
                <strong>🧠 Summary:</strong> ${data.summary || "N/A"}<br>
                <strong>🛠 Skills:</strong> ${data.skills_detected?.join(", ") || "N/A"}
            `;
            chatBox.appendChild(resumeInfo);
        }

        if (data.resume_id) {
            fetch(`http://127.0.0.1:8000/match-jobs/${data.resume_id}`)
                .then(res => res.json())
                .then(jobData => {
                    const jobReply = document.createElement("p");
                    jobReply.className = "bot-message";

                    if (jobData.matched_jobs && jobData.matched_jobs.length > 0) {
                        jobReply.innerHTML = `📄 <strong>Jobs matching your resume:</strong><br>${jobData.matched_jobs.map(job =>
                            `✅ ${job.job_title} at ${job.employer_name} (${job.job_city || "Remote"}, ${job.job_country || ""})`
                        ).join("<br>")}`;
                    } else {
                        jobReply.innerText = "⚠ No relevant jobs found based on your resume.";
                    }

                    chatBox.appendChild(jobReply);
                    chatBox.scrollTop = chatBox.scrollHeight;
                })
                .catch(err => {
                    const errorMsg = document.createElement("p");
                    errorMsg.className = "bot-message";
                    errorMsg.innerText = "❌ Error matching jobs. Please try again later.";
                    chatBox.appendChild(errorMsg);
                    console.error("Matching jobs error:", err);
                });
        } else {
            const failMsg = document.createElement("p");
            failMsg.className = "bot-message";
            failMsg.innerText = "⚠ Resume processed, but no ID was returned.";
            chatBox.appendChild(failMsg);
        }

        chatBox.scrollTop = chatBox.scrollHeight;
    })
    .catch(error => {
        const errorMsg = document.createElement("p");
        errorMsg.className = "bot-message";
        errorMsg.innerText = "❌ Error uploading resume. Please try again later.";
        chatBox.appendChild(errorMsg);
        console.error("Resume upload error:", error);
    });

    fileInput.value = "";
}

