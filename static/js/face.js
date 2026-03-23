// Jarvis Face JS — with status polling and mic toggle

document.addEventListener("DOMContentLoaded", () => {

    // ---------------------------------------------------------
    // State
    // ---------------------------------------------------------
    let isSpeaking = false;
    let idlePhase = 0;
    let speakPhase = 0;
    let voiceEnabled = true;

    const eyes = document.querySelectorAll(".eye");

    // ---------------------------------------------------------
    // Send text to Jarvis via HTTP fetch
    // ---------------------------------------------------------
    async function sendToJarvis() {
        const input = document.getElementById("userInput");
        const text = input.value.trim();
        if (!text) return;
        input.value = "";

        try {
            const response = await fetch("/talk", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ message: text, session_id: 1 }),
                signal: AbortSignal.timeout(300000)
            });

            const data = await response.json();
            const reply = data.message || data.response || "";

            if (reply) {
                setTimeout(() => {
                    isSpeaking = true;
                    const audio = new Audio("/static/output.wav?" + Date.now());
                    audio.addEventListener("ended", () => { isSpeaking = false; });
                    audio.play().catch(err => {
                        console.warn("Audio play failed:", err);
                        isSpeaking = false;
                    });
                }, 300);
            }

        } catch (err) {
            console.error("Send failed:", err);
            isSpeaking = false;
        }
    }

    window.sendToJarvis = sendToJarvis;

    document.getElementById("userInput").addEventListener("keydown", (e) => {
        if (e.key === "Enter") sendToJarvis();
    });

    // ---------------------------------------------------------
    // Mic Toggle
    // ---------------------------------------------------------
    async function toggleFaceVoice() {
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
        const btn = document.getElementById("faceMicToggle");
        if (voiceEnabled) {
            btn.textContent = "🎤 Voice On";
            btn.className = "mic-on";
        } else {
            btn.textContent = "🔇 Voice Off";
            btn.className = "mic-off";
        }
    }

    document.getElementById("faceMicToggle").addEventListener("click", toggleFaceVoice);

    // ---------------------------------------------------------
    // Mobile Tap-to-Talk — uses phone browser mic via MediaRecorder
    // ---------------------------------------------------------
    let mediaRecorder  = null;
    let audioChunks    = [];
    let isRecording    = false;

    async function startMobileRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks = [];

            // Pick best supported mime type
            const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", ""]
                .find(t => t === "" || MediaRecorder.isTypeSupported(t));

            mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
            mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
            mediaRecorder.onstop = async () => {
                const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
                stream.getTracks().forEach(t => t.stop());
                await uploadAudioToJarvis(blob);
            };

            mediaRecorder.start(100);
            isRecording = true;

            const btn = document.getElementById("mobileMicBtn");
            btn.textContent = "⏹️ Stop";
            btn.classList.add("recording");
            document.getElementById("faceStatusText").textContent = "Recording... tap Stop when done";
            document.getElementById("faceStatusDot").className = "status-dot red";

        } catch (err) {
            console.error("Mic access failed:", err);
            document.getElementById("faceStatusText").textContent =
                "Mic blocked — see setup instructions";
        }
    }

    function stopMobileRecording() {
        if (mediaRecorder && mediaRecorder.state !== "inactive") {
            mediaRecorder.stop();
            isRecording = false;
            const btn = document.getElementById("mobileMicBtn");
            btn.textContent = "🎙️ Tap to Talk";
            btn.classList.remove("recording");
            document.getElementById("faceStatusText").textContent = "Processing...";
            document.getElementById("faceStatusDot").className = "status-dot blue";
        }
    }

    async function toggleMobileMic() {
        if (isRecording) {
            stopMobileRecording();
        } else {
            await startMobileRecording();
        }
    }

    async function uploadAudioToJarvis(blob) {
        const formData = new FormData();
        formData.append("audio", blob, "voice.webm");

        try {
            const res = await fetch("/stt/upload", { method: "POST", body: formData });
            const data = await res.json();

            if (data.text && data.text.trim()) {
                document.getElementById("userInput").value = data.text;
                document.getElementById("faceStatusText").textContent = "Sending...";
                await sendToJarvis();
            } else {
                document.getElementById("faceStatusText").textContent = "Didn't catch that — try again";
                document.getElementById("faceStatusDot").className = "status-dot green";
            }
        } catch (err) {
            console.error("Audio upload failed:", err);
            document.getElementById("faceStatusText").textContent = "Upload failed";
        }
    }

    document.getElementById("mobileMicBtn").addEventListener("click", toggleMobileMic);

    // ---------------------------------------------------------
    // Status Polling — polls /api/stt/status every 2 seconds
    // ---------------------------------------------------------
    function updateFaceStatus(status, enabled) {
        const dot = document.getElementById("faceStatusDot");
        const text = document.getElementById("faceStatusText");

        if (!enabled) {
            dot.className = "status-dot red";
            text.textContent = "Voice disabled";
            return;
        }

        switch (status) {
            case "listening":
                dot.className = "status-dot green";
                text.textContent = "Listening for Jarvis...";
                break;
            case "wake_detected":
                dot.className = "status-dot yellow";
                text.textContent = "Wake word detected!";
                break;
            case "recording":
                dot.className = "status-dot yellow";
                text.textContent = "Recording command...";
                break;
            case "processing":
                dot.className = "status-dot blue";
                text.textContent = "Jarvis is thinking...";
                break;
            case "speaking":
                dot.className = "status-dot purple";
                text.textContent = "Jarvis is speaking...";
                break;
            default:
                dot.className = "status-dot green";
                text.textContent = "Listening for Jarvis...";
        }
    }

    setInterval(async () => {
        try {
            const res = await fetch("/api/stt/status");
            const data = await res.json();
            updateFaceStatus(data.status, data.enabled);
        } catch (err) {}
    }, 2000);

    // ---------------------------------------------------------
    // Wake word response polling
    // ---------------------------------------------------------
    setInterval(async () => {
        try {
            const res = await fetch("/api/wake_poll");
            if (res.status === 204) return;
            const data = await res.json();
            if (data && data.message) {
                isSpeaking = true;
                const audio = new Audio("/static/output.wav?" + Date.now());
                audio.addEventListener("ended", () => { isSpeaking = false; });
                audio.play().catch(err => {
                    console.warn("Wake audio failed:", err);
                    isSpeaking = false;
                });
            }
        } catch (err) {}
    }, 2000);

    // ---------------------------------------------------------
    // Mouth Canvas Setup
    // ---------------------------------------------------------
    const mouthCanvas = document.getElementById("mouth-canvas");
    const mouthCtx = mouthCanvas.getContext("2d");
    mouthCanvas.width = 260;
    mouthCanvas.height = 40;

    function roundedRectPath(ctx, x, y, width, height, radius) {
        const r = Math.min(radius, height / 2, width / 2);
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + width - r, y);
        ctx.quadraticCurveTo(x + width, y, x + width, y + r);
        ctx.lineTo(x + width, y + height - r);
        ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
        ctx.lineTo(x + r, y + height);
        ctx.quadraticCurveTo(x, y + height, x, y + height - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    }

    function drawMouth(intensity) {
        const ctx = mouthCtx;
        const w = mouthCanvas.width;
        const h = mouthCanvas.height;
        ctx.clearRect(0, 0, w, h);

        const centerX = w / 2;
        const centerY = h / 2;
        const capsuleWidth  = w * 0.50;
        const capsuleHeight = h * 0.65;
        const radius = capsuleHeight / 2;
        const capsuleX = centerX - capsuleWidth / 2;
        const capsuleY = centerY - capsuleHeight / 2;

        ctx.save();
        ctx.lineWidth = 3;
        ctx.strokeStyle = "rgba(0, 180, 255, 0.9)";
        ctx.shadowColor = "rgba(0, 180, 255, 0.8)";
        ctx.shadowBlur = 12;
        roundedRectPath(ctx, capsuleX, capsuleY, capsuleWidth, capsuleHeight, radius);
        ctx.stroke();
        ctx.restore();

        const innerBgHeight = capsuleHeight * 0.45;
        const innerBgY = centerY - innerBgHeight / 2;
        ctx.save();
        ctx.fillStyle = "rgba(0, 60, 100, 0.45)";
        roundedRectPath(ctx, centerX - (capsuleWidth * 0.42), innerBgY, capsuleWidth * 0.84, innerBgHeight, innerBgHeight / 2);
        ctx.fill();
        ctx.restore();

        const maxInnerHalf = capsuleWidth * 0.30;
        const innerHalfWidth = maxInnerHalf * intensity;
        const energyHeight = innerBgHeight * 0.9;
        const energyY = centerY - energyHeight / 2;
        const energyWidth = Math.max(innerHalfWidth * 2, 6);

        ctx.save();
        ctx.fillStyle = "rgba(0, 200, 255, 1)";
        ctx.shadowColor = "rgba(0, 220, 255, 1)";
        ctx.shadowBlur = 18;
        roundedRectPath(ctx, centerX - energyWidth / 2, energyY, energyWidth, energyHeight, energyHeight / 2);
        ctx.fill();
        ctx.restore();
    }

    // ---------------------------------------------------------
    // Animation Loop
    // ---------------------------------------------------------
    function animate() {
        let intensity;
        if (isSpeaking) {
            speakPhase += 0.2;
            intensity = 0.3 + 0.7 * ((Math.sin(speakPhase) + 1) / 2);
        } else {
            idlePhase += 0.04;
            intensity = 0.68 + 0.58 * Math.sin(idlePhase);
        }
        drawMouth(intensity);
        requestAnimationFrame(animate);
    }
    animate();

    // ---------------------------------------------------------
    // Eye Tracking
    // ---------------------------------------------------------
    document.addEventListener("mousemove", (e) => {
        eyes.forEach(eye => {
            const rect = eye.getBoundingClientRect();
            const eyeCX = rect.left + rect.width / 2;
            const eyeCY = rect.top + rect.height / 2;
            const angle = Math.atan2(e.clientY - eyeCY, e.clientX - eyeCX);
            const dist = Math.min(Math.hypot(e.clientX - eyeCX, e.clientY - eyeCY), 6);
            const offsetX = Math.cos(angle) * dist * 0.5;
            const offsetY = Math.sin(angle) * dist * 0.3;
            eye.style.setProperty("--px", `${14 + offsetX}px`);
            eye.style.setProperty("--py", `${4 + offsetY}px`);
        });
    });

    // ---------------------------------------------------------
    // Eye Blinking
    // ---------------------------------------------------------
    function blink() {
        eyes.forEach(eye => eye.classList.add("blink"));
        setTimeout(() => eyes.forEach(eye => eye.classList.remove("blink")), 150);
        setTimeout(blink, 2000 + Math.random() * 4000);
    }
    blink();

}); // END DOMContentLoaded
