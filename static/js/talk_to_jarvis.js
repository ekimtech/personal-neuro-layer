// Session ID injected by Flask into index.html as window.JARVIS_SESSION_ID
let session_id = (typeof window.JARVIS_SESSION_ID !== 'undefined') ? window.JARVIS_SESSION_ID : null;
let voiceEnabled = true;

// Make all links in chat open in a new tab
const renderer = new marked.Renderer();
renderer.link = function(token) {
  const href  = token.href  || token;
  const title = token.title || "";
  const text  = token.text  || href;
  return `<a href="${href}" target="_blank" rel="noopener noreferrer"${title ? ` title="${title}"` : ''}>${text}</a>`;
};
marked.setOptions({ renderer });

window.onload = () => {
  document.getElementById("sendButton").addEventListener("click", sendMessage);
  document.getElementById("newSessionButton").addEventListener("click", startNewSession);
  document.getElementById("toggleTools").addEventListener("click", toggleToolsSection);
  document.getElementById("micToggleButton").addEventListener("click", toggleVoice);
  loadSessions();

  // Markdown test button
  document.getElementById("mdTestButton").addEventListener("click", () => {
    const sample = "**bold text**\n\n*italic text*\n\n- Item one\n- Item two\n\n```python\ndef greet(name):\n    return f\"Hello, {name}\"\n```";
    appendBubble(sample, "jarvis");
  });

  // Start polling for wake word responses and status
  startWakeWordPolling();
  startStatusPolling();
};

function toggleToolsSection() {
  const container = document.getElementById("toolsContainer");
  const icon = document.getElementById("toolsIcon");
  container.classList.toggle("hidden");
  icon.classList.toggle("rotate-180");
}

// ============================================================
// MIC TOGGLE
// ============================================================

async function toggleVoice() {
  try {
    const res = await fetch("/api/stt/toggle", { method: "POST" });
    const data = await res.json();
    voiceEnabled = data.enabled;
    updateMicButton();
  } catch (err) {
    console.error("Toggle voice failed:", err);
  }
}

function updateMicButton() {
  const btn = document.getElementById("micToggleButton");
  if (voiceEnabled) {
    btn.textContent = "🎤 Voice On";
    btn.classList.remove("voice-off");
  } else {
    btn.textContent = "🔇 Voice Off";
    btn.classList.add("voice-off");
  }
}

// ============================================================
// STATUS POLLING
// Polls /api/stt/status every 2 seconds for Jarvis state
// ============================================================

function startStatusPolling() {
  setInterval(async () => {
    try {
      const res = await fetch("/api/stt/status");
      const data = await res.json();
      updateStatus(data.status, data.enabled);
    } catch (err) {
      // Silently ignore
    }
  }, 2000);
}

function updateStatus(status, enabled) {
  const statusEl = document.getElementById("jarvisStatus");
  const dotEl = document.getElementById("statusDot");

  if (!enabled) {
    statusEl.textContent = "Voice disabled";
    dotEl.className = "inline-block w-3 h-3 rounded-full bg-red-400";
    return;
  }

  switch (status) {
    case "listening":
      statusEl.textContent = "Listening for Jarvis...";
      dotEl.className = "inline-block w-3 h-3 rounded-full bg-green-400 animate-pulse";
      break;
    case "wake_detected":
      statusEl.textContent = "Wake word detected! Recording...";
      dotEl.className = "inline-block w-3 h-3 rounded-full bg-yellow-400 animate-pulse";
      break;
    case "recording":
      statusEl.textContent = "Recording your command...";
      dotEl.className = "inline-block w-3 h-3 rounded-full bg-yellow-400 animate-pulse";
      break;
    case "processing":
      statusEl.textContent = "Jarvis is thinking...";
      dotEl.className = "inline-block w-3 h-3 rounded-full bg-blue-400 animate-pulse";
      break;
    case "speaking":
      statusEl.textContent = "Jarvis is speaking...";
      dotEl.className = "inline-block w-3 h-3 rounded-full bg-purple-400 animate-pulse";
      break;
    default:
      statusEl.textContent = "Listening for Jarvis...";
      dotEl.className = "inline-block w-3 h-3 rounded-full bg-green-400 animate-pulse";
  }
}

// ============================================================
// WAKE WORD POLLING
// Polls /api/wake_poll every 2 seconds for background responses
// ============================================================

let isSpeaking = false;
let lastAudioTime = 0;

function startWakeWordPolling() {
  console.log("[WakeWord] Polling started!");
  setInterval(async () => {
    try {
      const res = await fetch("/api/wake_poll");
      if (res.status === 204) return;

      const data = await res.json();
      if (data && data.message) {
        console.log("[WakeWord] Received from queue:", data.message);

        // Show in chat
        appendBubble(data.message, "jarvis");

        // Only play if not already speaking
        if (!isSpeaking) {
          isSpeaking = true;
          lastAudioTime = Date.now();
          const audio = new Audio("/static/output.wav?" + lastAudioTime);
          audio.addEventListener("ended", () => { isSpeaking = false; });
          audio.play().catch((err) => {
            console.warn("Wake word audio playback failed:", err);
            isSpeaking = false;
          });
        }
      }
    } catch (err) {
      // Silently ignore polling errors
    }
  }, 2000);
}

async function sendMessage() {
  const input = document.getElementById("chatInput");
  const message = input.value.trim();
  if (!message) return;

  appendBubble(message, "user");
  input.value = "";

  try {
    const response = await fetch("/talk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message, session_id: session_id }),
      signal: AbortSignal.timeout(300000)
    });

    const data = await response.json();
    console.log("Raw from server:", data);

    let msg = data.message || data.response || "Jarvis returned no message.";
    if (data.items && Array.isArray(data.items) && data.items.length > 0) {
      msg += "\n" + data.items.join("\n");
    }

    appendBubble(msg, "jarvis");

    // Skip audio for script runner responses (no_tts flag)
    if (!data.no_tts && !isSpeaking) {
      isSpeaking = true;
      lastAudioTime = Date.now();
      const jarvisVoice = new Audio("/static/output.wav?" + lastAudioTime);
      jarvisVoice.addEventListener("ended", () => { isSpeaking = false; });
      jarvisVoice.play().catch((err) => {
        console.warn("Audio playback failed:", err);
        isSpeaking = false;
      });
    }
  } catch (err) {
    console.error("Send failed:", err);
  }
}

function appendBubble(text, sender) {
  const chatMessages = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = "message " + sender;

  const avatar = document.createElement("div");
  avatar.className = "message-avatar";
  avatar.textContent = sender === "jarvis" ? "J" : "U";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  if (typeof text === "object") {
    text = "<pre>" + JSON.stringify(text, null, 2) + "</pre>";
  }

  let normalized = text.replace(/\\n/g, "\n");
  normalized = normalized.replace(/```(\w+)\s/g, "```$1\n");
  normalized = normalized.replace(/\s```/g, "\n```\n");

  console.log("Raw text from server:", text);
  console.log("Normalized for marked:", normalized);

  bubble.innerHTML = marked.parse(normalized);

  div.appendChild(avatar);
  div.appendChild(bubble);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function loadSessions() {
  try {
    const res = await fetch("/api/sessions");
    const { sessions } = await res.json();
    const sidebar = document.getElementById("sessionSidebar");
    sidebar.innerHTML = "<h2 class='font-semibold mb-2'>Jarvis Sessions</h2>";

    sessions.forEach((s) => {
      const div = document.createElement("div");
      div.className = "session-item flex justify-between items-center";

      const title = s.title || new Date(s.timestamp * 1000).toLocaleString();

      div.innerHTML =
        "<span class='session-title flex-1 truncate'>" + title + "</span>" +
        "<button class='rename-btn text-blue-400 hover:text-blue-500 ml-1' title='Rename'>✏</button>" +
        "<button class='delete-btn text-red-400 hover:text-red-500 ml-1' title='Delete'>✖</button>";

      div.onclick = () => switchSession(s.id);

      // Rename button
      div.querySelector(".rename-btn").onclick = (e) => {
        e.stopPropagation();
        const titleSpan = div.querySelector(".session-title");
        const currentTitle = titleSpan.textContent;
        const input = document.createElement("input");
        input.type = "text";
        input.value = currentTitle;
        input.className = "session-rename-input flex-1 bg-gray-700 text-white text-sm rounded px-1";
        titleSpan.replaceWith(input);
        input.focus();
        input.select();

        const saveRename = async () => {
          const newTitle = input.value.trim();
          if (newTitle && newTitle !== currentTitle) {
            await fetch("/api/session/" + s.id + "/rename", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ title: newTitle })
            });
            s.title = newTitle;
          }
          const newSpan = document.createElement("span");
          newSpan.className = "session-title flex-1 truncate";
          newSpan.textContent = newTitle || currentTitle;
          input.replaceWith(newSpan);
        };

        input.addEventListener("keydown", (ev) => {
          if (ev.key === "Enter") saveRename();
          if (ev.key === "Escape") {
            const newSpan = document.createElement("span");
            newSpan.className = "session-title flex-1 truncate";
            newSpan.textContent = currentTitle;
            input.replaceWith(newSpan);
          }
        });
        input.addEventListener("blur", saveRename);
      };

      // Delete button
      div.querySelector(".delete-btn").onclick = async (e) => {
        e.stopPropagation();
        await fetch("/api/session/" + s.id, { method: "DELETE" });
        div.remove();
      };

      sidebar.appendChild(div);
    });
  } catch (err) {
    console.error("Session load failed:", err);
  }
}

async function startNewSession() {
  try {
    const res = await fetch("/api/session", { method: "POST" });
    const newSession = await res.json();
    session_id = newSession.id;
    await loadSessions();
  } catch (err) {
    console.error("New session failed:", err);
  }
}

async function switchSession(id) {
  session_id = id;
  const res = await fetch("/api/turns/" + id);
  const turns = await res.json();
  const chat = document.getElementById("chatMessages");
  chat.innerHTML = "";
  turns.forEach((t) => appendBubble(t.message, t.speaker));
}