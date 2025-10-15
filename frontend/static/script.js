// When mic button is clicked -> simulate a voice question
document.getElementById("micButton").addEventListener("click", async () => {
    const userMessage = "What's the weather like right now?";
    document.getElementById("userMessage").innerText = userMessage;

    // Send message to backend (Flask)
    const response = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage })
    });

    const data = await response.json();
    document.getElementById("botMessage").innerText = data.response;
});