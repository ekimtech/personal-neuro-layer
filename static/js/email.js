export async function handleCommandResponse() {
    const responseInput = document.getElementById('command-response-input');
    const jarvisResponseDiv = document.getElementById('jarvis-response');
    const interactionDiv = document.getElementById('interaction');

    if (!responseInput || !jarvisResponseDiv || !interactionDiv) {
        console.warn("⚠️ Required DOM elements missing. Aborting command response.");
        return;
    }

    const nextAction = jarvisResponseDiv.dataset.nextAction;
    const userInput = responseInput.value;

    if (nextAction) {
        try {
            const response = await fetch(nextAction, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ response: userInput })
            });
            const data = await response.json();

            jarvisResponseDiv.innerText = data.prompt;
            jarvisResponseDiv.dataset.nextAction = data.next_action || "";
            jarvisResponseDiv.dataset.inputType = data.input_type || "text";

            // Clean up old input and button
            const oldInput = document.getElementById('command-response-input');
            if (oldInput) oldInput.remove();

            const oldButton = interactionDiv.querySelector('button');
            if (oldButton) {
                oldButton.removeEventListener('click', handleCommandResponse);
                oldButton.remove();
            }

            // Create new input and button
            const newInputField = document.createElement('input');
            newInputField.type = data.input_type || "text";
            newInputField.id = 'command-response-input';
            newInputField.placeholder = 'Enter your response here...';
            interactionDiv.appendChild(newInputField);

            const newSendButton = document.createElement('button');
            newSendButton.type = 'button';
            newSendButton.innerText = 'Send Response';
            newSendButton.addEventListener('click', handleCommandResponse);
            interactionDiv.appendChild(newSendButton);
        } catch (error) {
            console.error("Error sending command response:", error);
            jarvisResponseDiv.innerText = "Sorry, there was an error processing your response.";
        }
    }
}

export function handleEmailPrompt(data) {
    const jarvisResponseDiv = document.getElementById('jarvis-response');
    const interactionDiv = document.getElementById('interaction');

    if (!jarvisResponseDiv || !interactionDiv) {
        console.warn("⚠️ Required elements missing. Cannot update email prompt.");
        return;
    }

    jarvisResponseDiv.innerText = data.prompt || "Awaiting your response...";
    jarvisResponseDiv.dataset.nextAction = data.next_action || "";
    jarvisResponseDiv.dataset.inputType = data.input_type || "text";

    const existingInput = interactionDiv.querySelector('#command-response-input');
    if (existingInput) existingInput.remove();

    const existingButton = interactionDiv.querySelector('button');
    if (existingButton) {
        existingButton.removeEventListener('click', handleCommandResponse);
        existingButton.remove();
    }

    const inputField = document.createElement('input');
    inputField.type = data.input_type || "text";
    inputField.id = 'command-response-input';
    inputField.placeholder = 'Enter your response here...';
    interactionDiv.appendChild(inputField);

    const sendButton = document.createElement('button');
    sendButton.type = 'button';
    sendButton.innerText = 'Send Response';
    sendButton.addEventListener('click', handleCommandResponse);
    interactionDiv.appendChild(sendButton);
}

export async function initiateEmailConversation(route) {
    try {
        const response = await fetch(route, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        const data = await response.json();

        handleEmailPrompt(data);
    } catch (error) {
        console.error('Error initiating email conversation:', error);
        const jarvisResponseDiv = document.getElementById('jarvis-response');
        if (jarvisResponseDiv) {
            jarvisResponseDiv.innerText = "Oops - couldn't start an email flow.";
        } else {
            console.warn("⚠️ 'jarvis-response' element not found. Skipping error message display.");
        }
    }
}
