// /static/js/talk_to_jarvis.js (Rebuilt for Stable Forms - Global Forms State)

import { IntrusionDetection } from './utilities/intrusion_detection.js';
import { handleNasQuery } from './utilities/nas.js'; // Keep if handleNasQuery still does client-side logic
import { handleWeatherQuery } from './utilities/weather.js';
import { handleRouterQuery } from './utilities/router.js'; // NEW: Import router handler
import { handleFormInitiation, processFormResponse } from './utilities/forms.js';
import { handleTimeQuery } from './utilities/time.js';
import { handleDateQuery } from './utilities/date.js';

let lastQuestion = ''; // Define lastQuestion in a wider scope

// =========================================================
// Global Helper Functions (do NOT interact with DOM on load)
// =========================================================

// NEW: Function to strip Markdown bold syntax (**) from text for speech
function stripMarkdownBold(text) {
    if (typeof text !== 'string') return text;
    return text.replace(/\*\*(.*?)\*\*/g, '$1'); // Replaces **text** with text
}

// Function for voice synthesis (Jarvis speaks his responses)
function speakResponse(responseText) {
    if (!responseText) return; // Add defensive check

    // IMPORTANT: Speak the stripped version, but append the original (with Markdown)
    const textToSpeak = stripMarkdownBold(responseText); // Use the new helper here!

    const utterance = new SpeechSynthesisUtterance(textToSpeak); // Speak the stripped text
    utterance.pitch = 0.9;
    utterance.rate = 0.95;
    utterance.volume = 0.8;
    const voices = window.speechSynthesis.getVoices();

    // Prioritize specific voice, fallback to default if not found
    utterance.voice = voices.find(voice => voice.name === "Google UK English Male") || voices[0];

    if (!utterance.voice) {
        console.warn("Selected voice not found, and no default voice available.");
        return; // Exit if no voice can be found
    }

    window.speechSynthesis.speak(utterance);
}

// Event listener for when voices are loaded (global property)
window.speechSynthesis.onvoiceschanged = () => {
    console.log("Voices updated and ready for use.");
};

// Function to append a message to the chat (SAFE & MODULAR)
function appendMessage(sender, text) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');

    // Ensure 'sender' is a valid CSS token
    messageDiv.classList.add('message');
    if (typeof sender === 'string' && /^[a-zA-Z0-9_-]+$/.test(sender)) {
        messageDiv.classList.add(sender);
    } else {
        console.warn(`Unsafe sender class skipped: ${sender}`);
    }

    const avatarDiv = document.createElement('div');
    avatarDiv.classList.add('message-avatar');
    avatarDiv.textContent = sender === 'user' ? 'You' : 'J';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.classList.add('message-bubble');

    // If response includes multiple lines (like diagnostics), format as <pre>
    const isMultiline = typeof text === 'string' && text.includes('\n');
    if (isMultiline) {
        const preBlock = document.createElement('pre');
        preBlock.textContent = text; // Use textContent for <pre> to preserve formatting
        bubbleDiv.appendChild(preBlock);
    } else {
        // For single line, use innerHTML to render Markdown (if any)
        bubbleDiv.innerHTML = text; // Render Markdown here
    }

    if (sender === 'user') {
        messageDiv.appendChild(bubbleDiv);
        messageDiv.appendChild(avatarDiv);
    } else {
        messageDiv.appendChild(avatarDiv);
        messageDiv.appendChild(bubbleDiv);
    }

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return messageDiv;
}

// NOTE: handleCommandResponse and initiateWebSearch are likely no longer needed
// if all multi-turn and action initiation is handled by the backend's structured response.
// They are left here for now, but flagged for review/removal.
async function handleCommandResponse() {
    console.warn("handleCommandResponse: This function might be deprecated or need significant refactoring based on new backend action handling.");
    // ... (original content of handleCommandResponse) ...
}

function initiateWebSearch(query) {
    console.warn("initiateWebSearch: This function should ideally be triggered by a backend action.");
    // ... (original content of initiateWebSearch) ...
}


// Expose speakResponse globally if needed (e.g., for Flask to call back)
window.speakResponse = speakResponse;


// =========================================================
// DOMContentLoaded: All code interacting with HTML elements
// that exist when the page initially loads goes here.
// =========================================================
document.addEventListener('DOMContentLoaded', function() {
    const chatInput = document.getElementById('chatInput'); // Main chat input
    const sendButton = document.getElementById('sendButton'); // Main chat send button
    const chatMessages = document.getElementById('chatMessages');
    const backButton = document.getElementById('backButton');
    const jarvisStateHolder = document.getElementById('jarvis-state-holder'); // Hidden div for state flag

    // Get references to the fixed form input elements
    const mainChatControls = document.getElementById('main-chat-controls');
    const dynamicFormContainer = document.getElementById('dynamic-form-container');
    const dynamicInputField = document.getElementById('dynamic-form-input');
    const dynamicSendButton = document.getElementById('dynamic-form-send-button');
    
    // 🧠 Populate Session Sidebar
fetch('/api/sessions')
  .then(res => res.json())
  .then(data => {
    const list = document.getElementById('session-list');
    list.innerHTML = '';

    if (data.length === 0) {
      list.innerHTML = '<li class="text-gray-400">No sessions yet.</li>';
      return;
    }

    data.forEach(session => {
      const item = document.createElement('li');
      item.className = 'bg-gray-700 p-3 rounded-lg hover:bg-gray-600 cursor-pointer';
      item.textContent = `${session.title} (${new Date(session.timestamp).toLocaleString()})`;
      item.dataset.sessionId = session.id;

      item.addEventListener('click', () => {
        console.log('Resume session:', session.id);
        // TODO: Resume logic goes here
      });

      list.appendChild(item);
    });
  })
  .catch(err => {
    console.error('Failed to load sessions:', err);
  });

    // Intent detection utility for email triggers
    function detectEmailIntent(text) {
        const patterns = [
            /send.*email/i,
            /write.*email/i,
            /email.*to/i,
            /compose.*email/i,
            /send.*emal/i, // NEW: Added to catch common typo 'emal'
            /write.*emal/i, // NEW: Added to catch common typo 'emal'
            /emal.*to/i,    // NEW: Added to catch common typo 'emal'
            /compose.*emal/i // NEW: Added to catch common typo 'emal'
        ];
        return patterns.some(p => p.test(text)) ? '/ai/email/init' : null;
    }

    // ✅ Email initiation function defined above chat handling logic
    async function initiateEmailConversation(triggerMatch) {
        chatInput.setAttribute('data-next-action', '/ai/email/process_recipient');
        chatInput.setAttribute('data-input-type', 'text');

        const openingPrompt = 'Who should I email?';
        appendMessage('jarvis', openingPrompt);
        speakResponse(openingPrompt);
    }
    
    // NEW: Function to detect document form intent
    function detectDocumentIntent(text) {
        const invoicePatterns = [/create.*invoice/i, /make.*invoice/i];
        const letterPatterns = [/create.*letter/i, /write.*letter/i, /compose.*letter/i];
        const estimatePatterns = [/create.*estimate/i, /make.*estimate/i];

        if (invoicePatterns.some(p => p.test(text))) {
            return 'action:create_invoice';
        }
        if (letterPatterns.some(p => p.test(text))) {
            return 'action:create_letter';
        }
        if (estimatePatterns.some(p => p.test(text))) {
            return 'action:create_estimate';
        }

        return null;
    }

    // 1. Handle Jarvis chat form submission (using /talk endpoint)
    async function sendMessage() {
        const userInput = chatInput.value.trim();
        if (userInput === '') return;

        lastQuestion = userInput; // Update lastQuestion

        // Append user message immediately
        appendMessage('user', userInput);
        chatInput.value = ''; // Clear input field immediately
        sendButton.disabled = true; // Disable main chat send button while processing
        
        // ✅ Save session to backend
        await fetch('/api/sessions', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: userInput,
            timestamp: Date.now()
          })
        });

        // Show a thinking message
        const thinkingMessageDiv = appendMessage('jarvis', 'Jarvis is thinking...');
        const thinkingBubble = thinkingMessageDiv.querySelector('.message-bubble'); // Get the bubble element

        try {
            // Check for client-side form flow state (using the dataset flag)
            const formType = jarvisStateHolder.dataset.formType;
            if (formType) {
                // If a form flow is active, process the response through utilities/forms.js
                await processFormResponse(userInput, appendMessage, speakResponse);
                thinkingMessageDiv.remove(); // Remove the "Jarvis is thinking..." message
                return; // Exit as form response is handled
            }

            // --- NEW: Frontend-side Command Handling (Order matters: specific before general) ---
            let commandHandled = false;

            // Handle NAS queries (from utilities/nas.js)
            commandHandled = await handleNasQuery(userInput, appendMessage, speakResponse);
            if (commandHandled) {
                thinkingMessageDiv.remove(); // Hide thinking bubble
                return; // Command handled, stop further processing
            }

            // Handle Weather queries (from utilities/weather.js)
            commandHandled = await handleWeatherQuery(userInput, appendMessage, speakResponse);
            if (commandHandled) {
                thinkingMessageDiv.remove(); // Hide thinking bubble
                return; // Command handled, stop further processing
            }

            // Handle Time queries (from utilities/time.js)
            commandHandled = await handleTimeQuery(userInput, appendMessage, speakResponse);
            if (commandHandled) {
                thinkingMessageDiv.remove(); // Hide thinking bubble
                return; // Command handled, stop further processing
            }

            // Handle Date queries (from utilities/date.js)
            commandHandled = await handleDateQuery(userInput, appendMessage, speakResponse);
            if (commandHandled) {
                thinkingMessageDiv.remove(); // Hide thinking bubble
                return; // Command handled, stop further processing
            }

            // NEW: Handle Router queries (from utilities/router.js)
            commandHandled = await handleRouterQuery(userInput, appendMessage, speakResponse);
            if (commandHandled) {
                thinkingMessageDiv.remove(); // Hide thinking bubble
                return; // Command handled, stop further processing
            }
            // --- END NEW: Frontend-side Command Handling ---

            // Step 1: Detect email intent and override flow (if not handled by direct commands)
            const emailTriggerMatch = detectEmailIntent(userInput);
            if (emailTriggerMatch) {
                await initiateEmailConversation(emailTriggerMatch);
                thinkingMessageDiv.remove(); // Clean up placeholder
                return; // Exit early — email flow is triggered
            }

            // NEW: Step 2: Detect document intent and trigger the correct form
            const documentTriggerMatch = detectDocumentIntent(userInput);
            if (documentTriggerMatch) {
                await handleFormInitiation(documentTriggerMatch, jarvisStateHolder, appendMessage, speakResponse);
                thinkingMessageDiv.remove(); // Clean up placeholder
                return; // Exit early — document flow is triggered
            }

            // Step 2: Handle ongoing flow via data-next-action if present (if not handled by direct commands or email trigger)
            const nextAction = chatInput.getAttribute('data-next-action');
            if (nextAction) {
                const response = await fetch(nextAction, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ response: userInput })
                });
                const data = await response.json();

                // DEBUG: Log full response
                console.log('Email flow response:', data);

                // Step 2.5: Prompt for final confirmation
                if (data.next_action === '/ai/email/process_confirmation') {
                    const confirmationPrompt = `Okay, sending to ${data.recipient}, with subject '${data.subject}', and body '${data.body}'. Confirm? (yes/no)`;

                    chatInput.setAttribute('data-next-action', '/ai/email/process_confirmation');
                    chatInput.setAttribute('data-input-type', 'text');

                    appendMessage('jarvis', confirmationPrompt);
                    speakResponse(confirmationPrompt); // Speak confirmation prompt

                    thinkingMessageDiv.remove();
                    return;
                }

                // Step 2.6: Send final email
                if (data.next_action === '/ai/email/send') {
                    try {
                        const sendRes = await fetch('/ai/email/send', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ send: true })
                        });

                        const result = await sendRes.json();
                        const finalMessage = result.message || "✅ Email sent!";
                        appendMessage('jarvis', finalMessage);
                        speakResponse(finalMessage); // Speak final message
                    } catch (error) {
                        console.error('Email send failed:', error);
                        appendMessage('jarvis', '❌ Something went wrong sending the email.');
                        speakResponse('Something went wrong sending the email.'); // Speak error
                    }

                    chatInput.removeAttribute('data-next-action');
                    chatInput.removeAttribute('data-input-type');
                    thinkingMessageDiv.remove();
                    return;
                }

                // Step 2.7: Catch intermediate prompts like subject/body
                if (data.prompt) {
                    appendMessage('jarvis', data.prompt);
                    speakResponse(data.prompt); // Speak prompt

                    // Update flow direction
                    if (data.next_action) {
                        chatInput.setAttribute('data-next-action', data.next_action);
                    }
                    if (data.input_type) {
                        chatInput.setAttribute('data-input-type', data.input_type);
                    }

                    thinkingMessageDiv.remove();
                    return;
                }

                // Step 2.8: Default fallback — flow updated or reset
                if (data.next_action) {
                    chatInput.setAttribute('data-next-action', data.next_action);
                    chatInput.setAttribute('data-input-type', data.input_type || 'text');
                } else {
                    chatInput.removeAttribute('data-next-action');
                    chatInput.removeAttribute('data-input-type');
                }

                thinkingMessageDiv.remove();
                return;
            }


            // Default /talk endpoint call for general AI interaction or new action initiation
            const response = await fetch('/talk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: userInput })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
            }

            const responseData = await response.json();
            let jarvisReply = responseData?.choices?.[0]?.message?.content;
            const action = responseData?.action; // Get the action object from the response

            if (!jarvisReply) {
                console.error("⚠️ No response from Jan.");
                thinkingBubble.textContent = "Jarvis didn’t respond—try again or check the server.";
                speakResponse("Jarvis didn’t respond—try again or check the server."); // Speak error
                return;
            }

            // Handle potential echo (if Jarvis repeats the user input)
            if (jarvisReply && jarvisReply.startsWith(userInput)) {
                jarvisReply = jarvisReply.replace(userInput, '').trim();
            }

            // Update the thinking message with the actual reply
            thinkingBubble.textContent = jarvisReply;
            speakResponse(jarvisReply); // Speak the reply

            // --- Handle Structured Actions from Backend ---
            if (action) {
                console.log("Backend requested action:", action);
                if (action.type === "initiate_form") {
                    if (action.form_name === "invoice") {
                        handleFormInitiation("action:create_invoice", jarvisStateHolder, appendMessage, speakResponse);
                    } else if (action.form_name === "estimate") {
                        handleFormInitiation("action:create_estimate", jarvisStateHolder, appendMessage, speakResponse);
                    } else if (action.form_name === "letter") {
                        handleFormInitiation("action:create_letter", jarvisStateHolder, appendMessage, speakResponse);
                    } else if (action.form_name === "email_compose") {
                        console.log("Initiating email compose flow...");
                        appendMessage('jarvis', `Okay, who am I sending the email to?`);
                        chatInput.setAttribute('data-next-action', '/ai/email/process_recipient');
                        chatInput.setAttribute('data-input-type', 'text');

                        speakResponse("Okay, who am I sending the email to?");
                    }
                } else if (action.type === "backend_call") {
                    console.log(`Performing backend call: ${action.endpoint} with payload:`, action.payload);
                    const backendCallResponse = await fetch(action.endpoint, {
                        method: 'POST', // Note: Your backend /sys/weather is GET, so this might need adjustment if used for weather
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(action.payload)
                    });
                    const backendCallData = await backendCallResponse.json();
                    // Display the result of the backend call
                    appendMessage('jarvis', backendCallData.response || backendCallData.weather);
                    speakResponse(backendCallData.response || backendCallData.weather); // Speak the backend call data
                }
                // Add more action types here as your backend defines them (e.g., "redirect_to_page", "show_modal")
            }

        } catch (error) {
            console.error('Error sending message:', error);
            thinkingBubble.textContent = `Error: ${error.message}. Please try again.`;
            speakResponse(`Error: ${error.message}. Please try again.`);
        } finally {
            sendButton.disabled = false; // Re-enable button
            chatInput.focus(); // Focus on input field
            chatMessages.scrollTop = chatMessages.scrollHeight; // Scroll to bottom again
        }
    }

    // Event listeners for the main chat input and send button
    sendButton.addEventListener('click', sendMessage);

    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) { // Send on Enter, new line on Shift+Enter
            e.preventDefault(); // Prevent default new line
            sendMessage();
        }
    });

    // Adjust textarea height dynamically
    chatInput.addEventListener('input', function() {
        this.style.height = 'auto'; // Reset height
        this.style.height = (this.scrollHeight) + 'px'; // Set to scroll height
        // Limit max height to prevent it from growing too large
        if (this.scrollHeight > 150) { // Example max height
            this.style.overflowY = 'auto';
            this.style.height = '150px';
        } else {
            this.style.overflowY = 'hidden';
        }
    });

    // Back button functionality
    backButton.addEventListener('click', function() {
        window.location.href = '/'; // Navigate back to the home page (which is '/')
    });

    // Initial focus on main chat input
    chatInput.focus();

    // 3. Ensure logs only update if the page has "firewallLogs"
    if (document.getElementById("firewallLogs")) {
        IntrusionDetection.fetchLogs();
    }

    // Initial message display for existing conversation (if any)
    // This part replaces your original {% if conversation %} block in HTML
    // You'll need to pass the conversation data
});
