// Elements
const micButton = document.getElementById("micButton");
const chatContainer = document.getElementById("chatContainer");
const introMessage = document.getElementById("botMessage");
const statusBadge = document.getElementById("statusBadge");
const toolsMenu = document.getElementById("toolsMenu");

// Mode state
let frontendOnline = navigator.onLine; // Browser network status
let backendReachable = false;          // Whether backend /ping responds
let currentMode = "offline";           // "online" | "offline" | "degraded"

// Helper to set the badge
function updateBadge() {
    if (!frontendOnline) {
        statusBadge.className = "offline";
        statusBadge.innerText = "Offline (browser)";
        currentMode = "offline";
    } else if (frontendOnline && backendReachable) {
        statusBadge.className = "online";
        statusBadge.innerText = "Online";
        currentMode = "online";
    } else if (frontendOnline && !backendReachable) {
        statusBadge.className = "degraded";
        statusBadge.innerText = "Degraded (no backend)";
        currentMode = "degraded";
    } else {
        statusBadge.className = "";
        statusBadge.innerText = "Checking…";
        currentMode = "offline";
    }
}

// Try contacting backend /ping endpoint to confirm backend reachability
async function checkBackendPing(timeout = 4000) {
    try {
        const controller = new AbortController();
        const id = setTimeout(() => controller.abort(), timeout);
        const res = await fetch("/ping", { method: "GET", signal: controller.signal });
        clearTimeout(id);

        if (!res.ok) {
            backendReachable = false;
        } else {
            const json = await res.json();
            // Ping returns { online: true/false, mode: "online"|"offline" }
            backendReachable = !!json.online;
            // If backend says offline, we should treat it as backendReachable=false
            // (json.online already captures that).
        }
    } catch (err) {
        backendReachable = false;
    } finally {
        updateBadge();
    }
}

// When initializing connectivity, ensure we call updateBadge after backend check
async function initConnectivity() {
    frontendOnline = navigator.onLine;
    updateBadge();
    await checkBackendPing();
    // poll backend every 10s
    setInterval(checkBackendPing, 10000);
}

// Listen to browser online/offline events
window.addEventListener("online", () => { frontendOnline = true; updateBadge(); checkBackendPing(); });
window.addEventListener("offline", () => { frontendOnline = false; updateBadge(); });

// Navigation
function navigatePage() {
    const selected = document.getElementById("toolsMenu").value;
    if (window.location.pathname !== selected) {
        window.location.href = selected;
    }
}

// Keep dropdown synced with current page
document.addEventListener("DOMContentLoaded", () => {
    if (toolsMenu) {
        toolsMenu.value = window.location.pathname.includes("reminders") ? "/reminders" : "/";
    }
});

// Always include mode when calling backend so backend can behave accordingly.
async function askBackend(message) {
    // 1. Handle browser-offline right away
    if (!navigator.onLine) {
        console.warn("Browser offline — using local fallback.");
        const now = new Date();
        if (/time/i.test(message)) {
            const time = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
            return { response: `The current local time is ${time}.` };
        } else if (/date/i.test(message)) {
            const date = now.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
            return { response: `Today's date is ${date}.` };
        } else {
            return { response: "Offline mode active — I can only tell you the local date or time." };
        }
    }

    // 2. Otherwise try backend
    const payload = { message, mode: currentMode };
    try {
        const res = await fetch("/ask", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Backend not reachable");
        return await res.json();
    } catch (err) {
        console.warn("Backend unreachable — local fallback:", err.message);
        const now = new Date();
        if (/time/i.test(message)) {
            const time = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
            return { response: `The current local time is ${time}.` };
        } else if (/date/i.test(message)) {
            const date = now.toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" });
            return { response: `Today's date is ${date}.` };
        } else {
            return { response: "Offline mode active — I can only tell you the local date or time." };
        }
    }
}

async function playSpeech(text) {
    try {
        const payload = { text, mode: currentMode };
        const response = await fetch("/speak", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        // If backend returns JSON (offline_mode or error fallback), use browser TTS
        const contentType = response.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
            const json = await response.json();
            const t = json.text || text;
            // speak with browser TTS
            if ('speechSynthesis' in window) {
                const utter = new SpeechSynthesisUtterance(t);
                utter.rate = 1;
                utter.pitch = 1;
                speechSynthesis.speak(utter);
                return;
            } else {
                console.warn("Browser speechSynthesis not available; no audio.");
                return;
            }
        }

        // Otherwise, assume we got audio content
        if (response.ok && contentType.includes("audio/")) {
            const audioBlob = await response.blob();
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            await audio.play();
            return;
        }

        // fallback: speak locally
        if ('speechSynthesis' in window) {
            const utter = new SpeechSynthesisUtterance(text);
            speechSynthesis.speak(utter);
        }
    } catch (err) {
        console.error("Speech playback error:", err);
        if ('speechSynthesis' in window) {
            const utter = new SpeechSynthesisUtterance(text);
            speechSynthesis.speak(utter);
        }
    }
}

// Speech recognition + chat UI
if (micButton && chatContainer) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = "en-US";

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
            userMessage = userMessage.charAt(0).toUpperCase() + userMessage.slice(1);
            if (!userMessage.endsWith("?")) userMessage += "?";

            // Remove listening bubble
            const bubbles = document.querySelectorAll(".chat-bubble.bot");
            const lastBotBubble = bubbles[bubbles.length - 1];
            if (lastBotBubble && lastBotBubble.innerText.includes("Listening")) lastBotBubble.remove();

            // Show user message
            const userBubble = document.createElement("div");
            userBubble.classList.add("chat-bubble", "user");
            userBubble.innerText = userMessage;
            chatContainer.appendChild(userBubble);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            // Send to backend (with mode)
            const data = await askBackend(userMessage);
            let reply = data.response || "Sorry, I couldn't get a response.";

            // Small formatting cleanup (example: remove timezone name in parentheses)
            reply = reply.replace(/\s*\([A-Za-z_\/+-]+\)/g, "");       // remove (America/New_York)
            reply = reply.replace(/\.?(\d{6,})$/g, "");                // remove trailing microseconds if they show up
            reply = reply.trim();

            const botBubble = document.createElement("div");
            botBubble.classList.add("chat-bubble", "bot");
            botBubble.innerText = reply;
            chatContainer.appendChild(botBubble);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            // speak (will use /speak -> backend or fallback)
            await playSpeech(reply);
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);
        };
    } else {
        console.warn("SpeechRecognition not available in this browser.");
    }
}

// Reminders code (same logic)
document.addEventListener("DOMContentLoaded", () => {
    // Init connectivity checks
    initConnectivity();

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

// Chatbot Logic (Home Page Only)
// if (micButton && chatContainer) {
//     const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
//     const recognition = new SpeechRecognition();
//     recognition.continuous = false;
//     recognition.interimResults = false;
//     recognition.lang = "en-US";

//     // Play AI speech
//     async function playSpeech(text) {
//         try {
//             const response = await fetch("/speak", {
//                 method: "POST",
//                 headers: { "Content-Type": "application/json" },
//                 body: JSON.stringify({ text })
//             });

//             if (!response.ok) {
//                 console.error("Speech API error:", await response.text());
//                 return;
//             }

//             const audioBlob = await response.blob();
//             const audioUrl = URL.createObjectURL(audioBlob);
//             const audio = new Audio(audioUrl);
//             audio.play().catch(err => console.error("Playback error:", err));
//         } catch (err) {
//             console.error("Speech playback error:", err);
//         }
//     }

//     micButton.addEventListener("click", () => {
//         micButton.classList.remove("large");
//         micButton.classList.add("small");
//         recognition.start();

//         if (introMessage) introMessage.style.display = "none";

//         const listeningBubble = document.createElement("div");
//         listeningBubble.classList.add("chat-bubble", "bot");
//         listeningBubble.innerText = "🎤 Listening...";
//         chatContainer.appendChild(listeningBubble);
//         chatContainer.scrollTop = chatContainer.scrollHeight;
//     });

//     recognition.onresult = async (event) => {
//         let userMessage = event.results[0][0].transcript.trim();

//         // Beautify user input
//         userMessage = userMessage.charAt(0).toUpperCase() + userMessage.slice(1);
//         if (!userMessage.endsWith("?")) userMessage += "?";

//         // Remove "Listening..." bubble
//         const bubbles = document.querySelectorAll(".chat-bubble.bot");
//         const lastBotBubble = bubbles[bubbles.length - 1];
//         if (lastBotBubble && lastBotBubble.innerText.includes("Listening")) {
//             lastBotBubble.remove();
//         }

//         // Show user’s message
//         const userBubble = document.createElement("div");
//         userBubble.classList.add("chat-bubble", "user");
//         userBubble.innerText = userMessage;
//         chatContainer.appendChild(userBubble);
//         chatContainer.scrollTop = chatContainer.scrollHeight;

//         // Send to backend
//         const response = await fetch("/ask", {
//             method: "POST",
//             headers: { "Content-Type": "application/json" },
//             body: JSON.stringify({ message: userMessage })
//         });

//         const data = await response.json();
//         let reply = data.response;

//         // Simplify bot output for time responses
//         if (reply.includes("is 202")) {
//             reply = reply.replace(/T\d{2}:\d{2}:\d{2}.*$/, "");
//             reply = reply.replace("is", "is around");
//         }

//         // Show bot reply
//         const botBubble = document.createElement("div");
//         botBubble.classList.add("chat-bubble", "bot");
//         botBubble.innerText = reply;
//         chatContainer.appendChild(botBubble);
//         chatContainer.scrollTop = chatContainer.scrollHeight;

//         // Speak reply
//         await playSpeech(reply);
//     };

//     recognition.onerror = (event) => {
//         console.error("Speech recognition error:", event.error);
//     };
// }

// // Reminders Logic
// document.addEventListener("DOMContentLoaded", () => {
//     const addBtn = document.getElementById("addReminderBtn");
//     const list = document.getElementById("reminderList");

//     if (addBtn && list) {
//         let reminders = JSON.parse(localStorage.getItem("reminders") || "[]");
//         renderReminders();

//         addBtn.addEventListener("click", () => {
//             const text = document.getElementById("reminderText").value.trim();
//             const priority = document.getElementById("priority").value;
//             if (!text) return;

//             const newReminder = { id: Date.now(), text, priority };
//             reminders.push(newReminder);
//             localStorage.setItem("reminders", JSON.stringify(reminders));

//             document.getElementById("reminderText").value = "";
//             renderReminders();
//         });

//         function renderReminders() {
//             list.innerHTML = "";
//             reminders.forEach(addReminderToList);
//         }

//         function addReminderToList(reminder) {
//             const li = document.createElement("li");
//             li.className = "reminder-item";

//             let icon = "🟢";
//             if (reminder.priority === "medium") icon = "🟡";
//             else if (reminder.priority === "high") icon = "🔴";

//             const textSpan = document.createElement("span");
//             textSpan.innerHTML = `<span class="reminder-priority">${icon}</span>${reminder.text}`;

//             const delBtn = document.createElement("button");
//             delBtn.className = "delete-btn";
//             delBtn.textContent = "✖";
//             delBtn.addEventListener("click", () => {
//                 reminders = reminders.filter(r => r.id !== reminder.id);
//                 localStorage.setItem("reminders", JSON.stringify(reminders));
//                 renderReminders();
//             });

//             li.appendChild(textSpan);
//             li.appendChild(delBtn);
//             list.appendChild(li);
//         }
//     }
// });
