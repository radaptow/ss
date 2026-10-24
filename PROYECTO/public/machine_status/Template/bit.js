(function() {
    'use strict';

    const CONFIG = {
        endpoint: 'https://syntaxsanctuary.com/machine_status/index.php?action=register',
        intervalMs: 5000,
        debug: true
    };

    let username = 'guest';
    const scripts = document.getElementsByTagName('script');
    for (let i = 0; i < scripts.length; i++) {
        if (scripts[i].hasAttribute('data-user')) {
            username = scripts[i].getAttribute('data-user');
            break;
        }
    }

    function getClientId() {
        let clientId = localStorage.getItem('bit_client_id');
        if (!clientId) {
            clientId = 'node_' + Math.random().toString(36).substring(2, 10) + Date.now().toString(36);
            localStorage.setItem('bit_client_id', clientId);
        }
        return clientId;
    }

    function sendHeartbeat() {
        const payload = {
            client_id: getClientId(),
            username: username,
            url: window.location.href,
            timestamp: Math.floor(Date.now() / 1000)
        };

        fetch(CONFIG.endpoint, {
            method: 'POST',
            mode: 'cors',
            headers: { 
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        })
        .then(response => response.json())
        .then(data => {
            if (CONFIG.debug) {
                console.log("✅ [Heartbeat OK]:", data);
            }
        })
        .catch(error => {
            if (CONFIG.debug) {
                console.error("❌ [Heartbeat ERROR]:", error);
            }
        });
    }

    sendHeartbeat();
    setInterval(sendHeartbeat, CONFIG.intervalMs);
})();