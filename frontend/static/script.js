const micButton = document.getElementById("micButton");
const chatContainer = document.getElementById("chatContainer");

// Speech recognition
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const recognition = new SpeechRecognition();
recognition.continuous = false;
recognition.interimResults = false;
recognition.lang = "en-US";

// Play AI speech function
async function playSpeech(text) {
    try {
        const response = await fetch("/speak", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text })
        });

        const arrayBuffer = await response.arrayBuffer();
        const audioBlob = new Blob([arrayBuffer], { type: "audio/mpeg" });
        const audioUrl = URL.createObjectURL(audioBlob);

        const audio = new Audio(audioUrl);
        audio.play();
    } catch (err) {
        console.error("Speech playback error:", err);
    }
}

micButton.addEventListener("click", () => {
    micButton.classList.remove("large");
    micButton.classList.add("small");
    recognition.start();

    const listeningBubble = document.createElement("div");
    listeningBubble.classList.add("chat-bubble", "bot");
    listeningBubble.innerText = "🎤 Listening...";
    chatContainer.appendChild(listeningBubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;
});

recognition.onresult = async (event) => {
    const userMessage = event.results[0][0].transcript;

    // Replace "listening..." bubble
    const bubbles = document.querySelectorAll(".chat-bubble.bot");
    const lastBotBubble = bubbles[bubbles.length - 1];
    if (lastBotBubble && lastBotBubble.innerText.includes("Listening")) {
        lastBotBubble.remove();
    }

    // Show user’s message
    const userBubble = document.createElement("div");
    userBubble.classList.add("chat-bubble", "user");
    userBubble.innerText = userMessage;
    chatContainer.appendChild(userBubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Send to backend
    const response = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage })
    });

    const data = await response.json();

    // Show bot reply
    const botBubble = document.createElement("div");
    botBubble.classList.add("chat-bubble", "bot");
    botBubble.innerText = data.response;
    chatContainer.appendChild(botBubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Speak the reply
    await playSpeech(data.response);
};

recognition.onerror = (event) => {
    console.error("Speech recognition error:", event.error);
};

// micButton.addEventListener("click", async () => {
//     // After first click, shrink mic and move to corner
//     micButton.classList.remove("large");
//     micButton.classList.add("small");

//     // Example simulated voice input
//     const userMessage = "What's the weather in New York?"

//     // Create an append user bubble dynamically
//     const userBubble = document.createElement("div");
//     userBubble.classList.add("chat-bubble", "user");
//     userBubble.innerText = userMessage;
//     chatContainer.appendChild(userBubble);

//     // Scroll to bottom
//     chatContainer.scrollTop = chatContainer.scrollHeight;

//     // Send message to backend
//     const response = await fetch("/ask", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({ message: userMessage })
//     });

//     const data = await response.json();

//     // Create and append bot bubble
//     const botBubble = document.createElement("div");
//     botBubble.classList.add("chat-bubble", "bot");
//     botBubble.innerText = data.response;
//     chatContainer.appendChild(botBubble);

//     chatContainer.scrollTop = chatContainer.scrollHeight
// });

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