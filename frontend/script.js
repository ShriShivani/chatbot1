// Function to send user message to FastAPI backend
function sendMessage() {
    let inputField = document.getElementById("user-input");
    let userText = inputField.value.trim();
    if (userText === "") return;

    // Add user message to chat
    let chatBox = document.getElementById("chat-box");
    let userMessage = document.createElement("p");
    userMessage.className = "user-message";
    userMessage.innerText = userText;
    chatBox.appendChild(userMessage);

    // Scroll to latest message
    chatBox.scrollTop = chatBox.scrollHeight;
    
    // Send message to backend
    fetch("http://127.0.0.1:8000/chat", { 
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userText })
    })
    .then(response => response.json())
    .then(data => {
        if (data.reply) {  // Ensure bot reply exists
            let botMessage = document.createElement("p");
            botMessage.className = "bot-message";
            botMessage.innerText = data.reply;
            chatBox.appendChild(botMessage);

            // Scroll to latest message
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    })
    .catch(error => console.error("Error sending message:", error));

    // Clear input field
    inputField.value = "";
}

// Function to fetch initial message from FastAPI backend
async function getMessage() {
    try {
        let response = await fetch("http://127.0.0.1:8000/");
        let data = await response.json();
        document.getElementById("output").innerText = data.message;  // Display response
    } catch (error) {
        console.error("Error fetching data:", error);
    }
}

// Call getMessage when the page loads
window.onload = function() {
    getMessage();

    // Attach event listener to input field for "Enter" key submission
    document.getElementById("user-input").addEventListener("keypress", function(event) {
        if (event.key === "Enter") {
            sendMessage();
        }
    });
};