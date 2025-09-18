// chat-widget.js: Handles lobby chat widget logic and Socket.IO events

document.addEventListener('DOMContentLoaded', function() {
    // Initialize Socket.IO client; assumes socket.io script is included on this page
    const socket = (typeof io === 'function') ? io() : null;

    // Chat widget elements
    const chatWidget = document.getElementById('lobby-chat-widget');
    const chatChevron = document.getElementById('lobby-chat-chevron');
    const chatToggleBtn = document.getElementById('lobby-chat-toggle-btn');
    const chatBody = chatWidget ? chatWidget.querySelector('.mud-chat-body') : null;

    if (!chatWidget || !chatChevron || !chatToggleBtn || !chatBody) return;

    // Collapsible logic for new tabbed chat
    function toggleLobbyChat() {
        chatWidget.classList.toggle('open');
        const isOpen = chatWidget.classList.contains('open');
        chatChevron.classList.toggle('bi-chevron-down', !isOpen);
        chatChevron.classList.toggle('bi-chevron-up', isOpen);
        if (isOpen) {
            setTimeout(() => {
                const activeInput = chatBody.querySelector('.tab-pane.active .form-control');
                if (activeInput) activeInput.focus();
            }, 150);
        }
    }
    chatToggleBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        toggleLobbyChat();
    });
    // Start collapsed
    chatWidget.classList.remove('open');
    chatChevron.classList.remove('bi-chevron-up');
    chatChevron.classList.add('bi-chevron-down');

    // Chat message logic for tabbed chat
    function setupTabChat(tabId) {
        const chatMessages = document.getElementById(`lobby-chat-messages-${tabId}`);
        const chatForm = document.getElementById(`lobby-chat-form-${tabId}`);
        const chatInput = document.getElementById(`lobby-chat-input-${tabId}`);
        if (!chatMessages || !chatForm || !chatInput) return;

        // Receive chat messages (example: only for 'general' tab)
        if (socket && tabId === 'general') {
            socket.on('lobby_chat_message', function(data) {
                const msgDiv = document.createElement('div');
                msgDiv.innerHTML = `<strong>${data.user}:</strong> ${data.message}`;
                chatMessages.appendChild(msgDiv);
                chatMessages.scrollTop = chatMessages.scrollHeight;
            });
        }

        // Send chat message
        chatForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const msg = chatInput.value.trim();
            if (!msg) return;
            if (socket && tabId === 'general') {
                socket.emit('lobby_chat_message', { message: msg });
            }
            chatInput.value = '';
        });
    }

    // Setup for General tab
    setupTabChat('general');

    // Listen for new tabs (area/whisper) and set up their chat logic
    window.addChatTab = function(id, label) {
        // ...existing code for tab creation...
        // After tab and pane are created:
        setupTabChat(id);
    };
});
