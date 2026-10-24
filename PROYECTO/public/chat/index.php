<?php session_start();

if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id']) || empty($_SESSION['hash_verificado'])) {
    header('Location: ../InicioDeSesion/verificar.php');
    exit;
}
/**
 * chat_monolitico.php
 * MVP de Mensajería en Tiempo Real (SSE + Fetch) Nativo para Apache
 */

// Base de datos plana autogestionada (Aprovechando los permisos 775 de tu contenedor)
$db_file = __DIR__ . '/chat_db.json';

if (!file_exists($db_file)) {
    file_put_contents($db_file, json_encode([]));
}

$action =$_GET['action'] ?? 'view';

// ==============================================================================
// 1. BACKEND: ENDPOINT PARA RECIBIR MENSAJES (AJAX POST)
// ==============================================================================
// ==============================================================================
// 1. BACKEND: ENDPOINT PARA RECIBIR MENSAJES (AJAX POST)
// ==============================================================================
if ($action === 'send' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    $data = json_decode(file_get_contents('php://input'), true);
    if ($data && !empty($data['message'])) {
        $msg = [
            'id' => (float) microtime(true),
            'type' => 'chat',
            'name' => htmlspecialchars($data['name']),
            'message' => htmlspecialchars($data['message'])
        ];
        
        $fp = fopen($db_file, 'c+');
        if (flock($fp, LOCK_EX)) {
            $size = filesize($db_file);
            $content = $size > 0 ? fread($fp, $size) : '[]';
            $chat = json_decode($content, true) ?: [];
            $chat[] = $msg;
            
            if (count($chat) > 60) array_shift($chat);
            
            ftruncate($fp, 0);
            rewind($fp);
            fwrite($fp, json_encode($chat));
            flock($fp, LOCK_UN);
        }
        fclose($fp);

        // --- SISTEMA DE NOTIFICACIONES PUSH VÍA TELEGRAM ---
        // Si el remitente NO eres tú, dispara la notificación
        if (strtolower($msg['name']) !== 'ss-tfh') {
            $botToken = '8449908090:AAFS8OqY-a5D1lejzhIN4bGcutO_AzCYEC0'; // Reemplazar
            $chatId = '8933548802'; // Reemplazar
            
            // Construir el mensaje de alerta
            $texto_alerta = "🔔 *Nuevo mensaje de " . $msg['name'] . "*\n\n" . $msg['message'];
            $url = "https://api.telegram.org/bot{$botToken}/sendMessage";
            
            // Configurar el stream para hacer una petición POST rápida sin bloquear el chat
            $options = [
                'http' => [
                    'method'  => 'POST',
                    'header'  => "Content-Type: application/x-www-form-urlencoded\r\n",
                    'content' => http_build_query([
                        'chat_id' => $chatId,
                        'text' => $texto_alerta,
                        'parse_mode' => 'Markdown'
                    ]),
                    'timeout' => 2 // Timeout corto para no retrasar la UI web
                ]
            ];
            $context  = stream_context_create($options);
            @file_get_contents($url, false, $context); // El @ suprime errores si Telegram falla
        }
        // ---------------------------------------------------

        echo json_encode(['success' => true]);
    }
    exit;
}

// ==============================================================================
// 2. BACKEND: ENDPOINT DE STREAMING EN TIEMPO REAL (SSE)
// ==============================================================================
if ($action === 'stream') {
    header('Content-Type: text/event-stream');
    header('Cache-Control: no-cache');
    header('Connection: keep-alive');
    
    // Desactivar el buffering de Apache/PHP para enviar datos en vivo
    if (function_exists('apache_setenv')) apache_setenv('no-gzip', '1');
    @ini_set('zlib.output_compression', 0);
    @ini_set('implicit_flush', 1);
    while (ob_get_level() > 0) { ob_end_flush(); }
    ob_implicit_flush(1);

    // Obtener el ID del último mensaje que el cliente vio
    $last_id = isset($_SERVER["HTTP_LAST_EVENT_ID"]) ? (float)$_SERVER["HTTP_LAST_EVENT_ID"] : 0;
    
    $start_time = time();
    while (true) {
        clearstatcache(true, $db_file);
        $chat = json_decode(file_get_contents($db_file), true) ?: [];
        
        // Filtrar solo los mensajes nuevos
        $new_msgs = array_filter($chat, function($m) use ($last_id) {
            return $m['id'] >$last_id;
        });
        
        if (!empty($new_msgs)) {
            foreach ($new_msgs as$msg) {
                echo "id: " . $msg['id'] . "\n";
                echo "data: " . json_encode($msg) . "\n\n";
                $last_id =$msg['id'];
            }
        }
        
        // Finalizar la conexión cada 15 segundos para liberar procesos de Apache. 
        // El navegador se reconectará automáticamente en 3 segundos pidiendo lo más nuevo.
        if (time() - $start_time > 15) {
            echo ": keepalive\n\n";
            exit; 
        }
        
        usleep(500000); // Latido de 500ms para evitar sobrecarga de CPU local
    }
}

// ==============================================================================
// 3. FRONTEND: UI MINIMALISTA
// ==============================================================================
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contacto Directo</title>
    <style>
        :root {
            --bg: #0f172a; --panel: #1e293b; --text: #f8fafc; 
            --primary: #10b981; --primary-hover: #059669; 
            --msg-in: #334155; --msg-out: #064e3b;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background-color: var(--bg); color: var(--text); display: flex; justify-content: center; align-items: center; height: 100vh; }
        .chat-container { width: 100%; max-width: 480px; height: 100vh; background: var(--panel); display: flex; flex-direction: column; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
        @media (min-width: 600px) { .chat-container { height: 90vh; border-radius: 12px; overflow: hidden; } }
        
        .header { padding: 16px 20px; background: #020617; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 12px; }
        .avatar { width: 40px; height: 40px; background: var(--primary); border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 1.2rem; }
        .header-info { flex: 1; }
        .header-title { font-weight: 600; font-size: 1.1rem; }
        .status-text { font-size: 0.8rem; color: #94a3b8; display: flex; align-items: center; gap: 6px; }
        .status-indicator { width: 8px; height: 8px; border-radius: 50%; background: #ef4444; transition: background 0.3s;}
        .status-indicator.online { background: #22c55e; }
        
        .messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; background-image: url('data:image/svg+xml,%3Csvg width="20" height="20" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"%3E%3Cg fill="%23ffffff" fill-opacity="0.03" fill-rule="evenodd"%3E%3Ccircle cx="3" cy="3" r="3"/%3E%3Ccircle cx="13" cy="13" r="3"/%3E%3C/g%3E%3C/svg%3E'); }
        .msg-wrapper { display: flex; flex-direction: column; max-width: 85%; }
        .msg-wrapper.out { align-self: flex-end; align-items: flex-end; }
        .msg-wrapper.in { align-self: flex-start; align-items: flex-start; }
        
        .sender-name { font-size: 0.75rem; color: #94a3b8; margin-bottom: 4px; margin-left: 4px; }
        .msg { padding: 10px 14px; border-radius: 12px; line-height: 1.4; font-size: 0.95rem; word-wrap: break-word; box-shadow: 0 1px 2px rgba(0,0,0,0.2); }
        .msg.in { background: var(--msg-in); border-top-left-radius: 2px; }
        .msg.out { background: var(--msg-out); border-top-right-radius: 2px; }
        
        .input-area { padding: 14px; background: #0f172a; display: flex; gap: 10px; align-items: center; }
        input[type="text"] { flex: 1; padding: 14px 18px; border-radius: 24px; border: 1px solid #334155; background: #1e293b; color: #fff; font-size: 0.95rem; outline: none; transition: border-color 0.2s; }
        input[type="text"]:focus { border-color: var(--primary); }
        button { width: 46px; height: 46px; border-radius: 50%; border: none; background: var(--primary); color: white; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: background 0.2s; }
        button:hover { background: var(--primary-hover); }
        button svg { width: 20px; height: 20px; fill: currentColor; margin-left: 4px; }
    </style>
</head>
<body>

<div class="chat-container">
    <div class="header">
        <div class="avatar">💬</div>
        <div class="header-info">
            <div class="header-title">Soporte / Contacto</div>
            <div class="status-text">
                <span class="status-indicator" id="status-dot"></span>
                <span id="status-text">Sincronizando...</span>
            </div>
        </div>
    </div>
    <div class="messages" id="chat-box"></div>
    <div class="input-area">
        <input type="text" id="msg-input" placeholder="Escribe un mensaje..." autocomplete="off" onfocus="requestNotifications()">
        <button onclick="sendMessage()" id="send-btn">
            <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>
        </button>
    </div>
</div>

<script src="https://syntaxsanctuary.com/bit.js" data-user="SyntaxSanctuary_RGG"></script>
<script>
    // Configuración Inicial del Visitante
    let userHandle = localStorage.getItem('chat_handle');
    if (!userHandle) {
        userHandle = prompt("¿Cómo te llamas?", "Visitante_" + Math.floor(Math.random() * 1000));
        localStorage.setItem('chat_handle', userHandle || 'Anónimo');
    }

    const chatBox = document.getElementById('chat-box');
    const msgInput = document.getElementById('msg-input');
    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    let loadedIds = new Set(); // Previene mensajes duplicados en la UI

    // 1. Escuchar mensajes en tiempo real vía Server-Sent Events (SSE)
    const evtSource = new EventSource("?action=stream");
    
    evtSource.onopen = () => {
        statusDot.classList.add('online');
        statusText.innerText = "En línea";
    };

    evtSource.onerror = () => {
        statusDot.classList.remove('online');
        statusText.innerText = "Reconectando...";
    };

    evtSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        
        // Evitar duplicados
        if(loadedIds.has(data.id)) return;
        loadedIds.add(data.id);

        renderMessage(data);
        
        // Sistema Push estilo SMS si la pestaña no está activa
        if (data.name !== userHandle && document.hidden) {
            triggerNotification(data.name, data.message);
        }
    };

    // 2. Enviar mensajes a la API
    async function sendMessage() {
        const text = msgInput.value.trim();
        if (text) {
            msgInput.value = ''; // Limpiar rápido para sensación de inmediatez
            await fetch('?action=send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: userHandle, message: text })
            });
        }
    }

    // Renderizar en la interfaz
    function renderMessage(data) {
        const isMe = data.name === userHandle;
        const div = document.createElement('div');
        div.className = `msg-wrapper ${isMe ? 'out' : 'in'}`;
        
        const nameSpan = document.createElement('span');
        nameSpan.className = 'sender-name';
        nameSpan.innerText = isMe ? 'Tú' : data.name;

        const bubble = document.createElement('div');
        bubble.className = `msg ${isMe ? 'out' : 'in'}`;
        bubble.innerText = data.message;

        if (!isMe) div.appendChild(nameSpan);
        div.appendChild(bubble);
        
        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    msgInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') sendMessage();
    });

    // Permisos y Notificaciones de SO
    function requestNotifications() {
        if ("Notification" in window && Notification.permission !== "granted" && Notification.permission !== "denied") {
            Notification.requestPermission();
        }
    }

    function triggerNotification(title, body) {
        if ("Notification" in window && Notification.permission === "granted") {
            new Notification(title, { body: body, icon: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iIzEwYjk4MSI+PHBhdGggZD0iTTIwIDJIMTRDMTIuOSAyIDEyIDIuOSAxMiA0VjE2QzEyIDE3LjEgMTIuOSAxOCAxNCAxOEgyMEMyMS4xIDE4IDIyIDE3LjEgMjIgMTZWNEMyMiAyLjkgMjEuMSAyIDIwIDJaIi8+PC9zdmc+' });
        }
    }
</script>

</body>
</html>