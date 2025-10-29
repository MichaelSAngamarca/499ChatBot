// Speech Recognition Setup
const micButton = document.getElementById("micButton");
const chatContainer = document.getElementById("chatContainer");
const introMessage = document.getElementById("botMessage");

// Navigation
function navigatePage() {
    const selected = document.getElementById("toolsMenu").value;
    if (window.location.pathname !== selected) {
        window.location.href = selected;
    }
}

// Keep dropdown synced with current page
document.addEventListener("DOMContentLoaded", () => {
    const toolsMenu = document.getElementById("toolsMenu");
    if (toolsMenu) {
        const current = window.location.pathname;
        toolsMenu.value = current.includes("reminders") ? "/reminders" : "/";
    }
});

// Chatbot Logic (Home Page Only)
if (micButton && chatContainer) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    // Play AI speech
    async function playSpeech(text) {
        try {
            const response = await fetch("/speak", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });

            if (!response.ok) {
                console.error("Speech API error:", await response.text());
                return;
            }

            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            audio.play().catch(err => console.error("Playback error:", err));
        } catch (err) {
            console.error("Speech playback error:", err);
        }
    }

    micButton.addEventListener("click", () => {
        micButton.classList.remove("large");
        micButton.classList.add("small");
        recognition.start();

        if (introMessage) introMessage.style.display = "none";

        const listeningBubble = document.createElement("div");
        listeningBubble.classList.add("chat-bubble", "bot");
        listeningBubble.innerText = "🎤 Listening...";
        chatContainer.appendChild(listeningBubble);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    });

    recognition.onresult = async (event) => {
        let userMessage = event.results[0][0].transcript.trim();

        // Beautify user input
        userMessage = userMessage.charAt(0).toUpperCase() + userMessage.slice(1);
        if (!userMessage.endsWith("?")) userMessage += "?";

        // Remove "Listening..." bubble
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
        let reply = data.response;

        // Simplify bot output for time responses
        if (reply.includes("is 202")) {
            reply = reply.replace(/T\d{2}:\d{2}:\d{2}.*$/, "");
            reply = reply.replace("is", "is around");
        }

        // Show bot reply
        const botBubble = document.createElement("div");
        botBubble.classList.add("chat-bubble", "bot");
        botBubble.innerText = reply;
        chatContainer.appendChild(botBubble);
        chatContainer.scrollTop = chatContainer.scrollHeight;

        // Speak reply
        await playSpeech(reply);
    };

    recognition.onerror = (event) => {
        console.error("Speech recognition error:", event.error);
    };
}

// Reminders Logic
document.addEventListener("DOMContentLoaded", () => {
    const addBtn = document.getElementById("addReminderBtn");
    const list = document.getElementById("reminderList");

    if (addBtn && list) {
        let reminders = JSON.parse(localStorage.getItem("reminders") || "[]");
        renderReminders();

        addBtn.addEventListener("click", () => {
            const text = document.getElementById("reminderText").value.trim();
            const priority = document.getElementById("priority").value;
            if (!text) return;

            const newReminder = { id: Date.now(), text, priority };
            reminders.push(newReminder);
            localStorage.setItem("reminders", JSON.stringify(reminders));

            document.getElementById("reminderText").value = "";
            renderReminders();
        });

        function renderReminders() {
            list.innerHTML = "";
            reminders.forEach(addReminderToList);
        }

        function addReminderToList(reminder) {
            const li = document.createElement("li");
            li.className = "reminder-item";

            let icon = "🟢";
            if (reminder.priority === "medium") icon = "🟡";
            else if (reminder.priority === "high") icon = "🔴";

            const textSpan = document.createElement("span");
            textSpan.innerHTML = `<span class="reminder-priority">${icon}</span>${reminder.text}`;

            const delBtn = document.createElement("button");
            delBtn.className = "delete-btn";
            delBtn.textContent = "✖";
            delBtn.addEventListener("click", () => {
                reminders = reminders.filter(r => r.id !== reminder.id);
                localStorage.setItem("reminders", JSON.stringify(reminders));
                renderReminders();
            });

            li.appendChild(textSpan);
            li.appendChild(delBtn);
            list.appendChild(li);
        }
    }
});
