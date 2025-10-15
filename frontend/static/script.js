const micButton = document.getElementById("micButton");
const chatContainer = document.getElementById("chatContainer");

micButton.addEventListener("click", async () => {
    // After first click, shrink mic and move to corner
    micButton.classList.remove("large");
    micButton.classList.add("small");

    // Example simulated voice input
    const userMessage = "What's the weather in New York?"

    // Create an append user bubble dynamically
    const userBubble = document.createElement("div");
    userBubble.classList.add("chat-bubble", "user");
    userBubble.innerText = userMessage;
    chatContainer.appendChild(userBubble);

    // Scroll to bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Send message to backend
    const response = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage })
    });

    const data = await response.json();

    // Create and append bot bubble
    const botBubble = document.createElement("div");
    botBubble.classList.add("chat-bubble", "bot");
    botBubble.innerText = data.response;
    chatContainer.appendChild(botBubble);

    chatContainer.scrollTop = chatContainer.scrollHeight
});

// When mic button is clicked -> simulate a voice question
// document.getElementById("micButton").addEventListener("click", async () => {
//     const userMessage = "What's the weather like right now?";
//     document.getElementById("userMessage").innerText = userMessage;

//     // Send message to backend (Flask)
//     const response = await fetch("/ask", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({ message: userMessage })
//     });

//     const data = await response.json();
//     document.getElementById("botMessage").innerText = data.response;
// });