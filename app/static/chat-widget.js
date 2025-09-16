// chat-widget.js: Handles lobby chat widget logic and Socket.IO events

document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    const chatWidget = document.getElementById('lobby-chat-widget');
    const chatMessages = document.getElementById('lobby-chat-messages');
    const chatForm = document.getElementById('lobby-chat-form');
    const chatInput = document.getElementById('lobby-chat-input');
    const chatChevron = document.getElementById('lobby-chat-chevron');

    // Collapsible logic
    function toggleLobbyChat() {
        chatWidget.classList.toggle('open');
        if (chatWidget.classList.contains('open')) {
            chatChevron.classList.remove('bi-chevron-down');
            chatChevron.classList.add('bi-chevron-up');
            setTimeout(() => { chatInput.focus(); }, 200);
        } else {
            chatChevron.classList.remove('bi-chevron-up');
            chatChevron.classList.add('bi-chevron-down');
        }
    }
    window.toggleLobbyChat = toggleLobbyChat;

    // Start collapsed
    chatWidget.classList.remove('open');
    chatChevron.classList.remove('bi-chevron-up');
    chatChevron.classList.add('bi-chevron-down');

    // Receive chat messages
    socket.on('lobby_chat_message', function(data) {
        const msgDiv = document.createElement('div');
        msgDiv.innerHTML = `<strong>${data.user}:</strong> ${data.message}`;
        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });

    // Send chat message
    chatForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const msg = chatInput.value.trim();
        if (msg) {
            socket.emit('lobby_chat_message', { message: msg });
            chatInput.value = '';
        }
    });
});
