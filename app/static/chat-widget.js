// chat-widget.js: Handles lobby chat widget logic and Socket.IO events

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Socket.IO client; assumes socket.io script is included on this page
    const socket = (typeof io === 'function') ? io() : null;

    // Cache commonly used DOM elements
    const chatWidget = document.getElementById('lobby-chat-widget');
    const chatMessages = document.getElementById('lobby-chat-messages');
    const chatForm = document.getElementById('lobby-chat-form');
    const chatInput = document.getElementById('lobby-chat-input');
    const chatChevron = document.getElementById('lobby-chat-chevron');
    const chatHeader = document.querySelector('#lobby-chat-header');

    // If the chat widget isn't present on the page, bail out gracefully
    if (!chatWidget || !chatHeader || !chatForm || !chatInput || !chatMessages || !chatChevron) {
        return; // No chat on this page
    }

    // Collapsible logic: toggles open/closed state and updates chevron icon
    function toggleLobbyChat() {
        chatWidget.classList.toggle('open');
        const isOpen = chatWidget.classList.contains('open');
        chatChevron.classList.toggle('bi-chevron-down', !isOpen);
        chatChevron.classList.toggle('bi-chevron-up', isOpen);
        if (isOpen) {
            // Delay focus slightly to allow panel to expand
            setTimeout(() => { chatInput.focus(); }, 150);
        }
    }

    // Attach click handler without inline JS
    chatHeader.addEventListener('click', toggleLobbyChat);

    // Start collapsed with down chevron
    chatWidget.classList.remove('open');
    chatChevron.classList.remove('bi-chevron-up');
    chatChevron.classList.add('bi-chevron-down');

    // Receive chat messages from server
    if (socket) {
        socket.on('lobby_chat_message', function(data) {
            const msgDiv = document.createElement('div');
            // Note: In a real app sanitize/escape data.user and data.message to avoid XSS.
            msgDiv.innerHTML = `<strong>${data.user}:</strong> ${data.message}`;
            chatMessages.appendChild(msgDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        });
    }

    // Send chat message to server
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (!msg) return;
        if (socket) {
            socket.emit('lobby_chat_message', { message: msg });
        }
        chatInput.value = '';
    });
});
