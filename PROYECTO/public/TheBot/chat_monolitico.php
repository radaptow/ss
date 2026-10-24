<?php
session_start();

if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id']) || empty($_SESSION['hash_verificado'])) {
    header('Location: ../InicioDeSesion/verificar.php');
    exit;
}

/**
 * chat_monolitico.php (v2.0 · ARYI Omega + Telegram Bidirectional Edition)
 * MVP de Mensajería en Tiempo Real (SSE + Fetch) Nativo para Apache (Windows/Linux)
 *
 * Mejoras clave integradas:
 * 1. Solución al bloqueo de sesión PHP (`session_write_close()`): evita que el stream SSE
 *    congele las peticiones `POST ?action=send` del mismo navegador.
 * 2. Puente Bidireccional con Telegram + ARYI Omega (`?action=tg_webhook` o sincronización
 *    directa con `aryi_omega.py` sobre `chat_db.json`).
 * 3. Seguridad en Telegram: cambiado de `Markdown` legacy a `HTML` escapado para que los
 *    caracteres `_` o `*` en los mensajes de visitantes nunca rompan el envío de alertas.
 * 4. Identidad de administrador verificada desde `$_SESSION` para impedir suplantación de `SS-TFH`.
 */

$db_file = __DIR__ . '/chat_db.json';
if (!file_exists($db_file)) {
    file_put_contents($db_file, json_encode([]));
}

// Configuración de Telegram (sincronizada con aryi_omega.py)
$BOT_TOKEN    = getenv('TELEGRAM_BOT_TOKEN') ?: '8449908090:AAFS8OqY-a5D1lejzhIN4bGcutO_AzCYEC0';
$CHAT_ID      = getenv('TELEGRAM_CHAT_ID')   ?: '8933548802';
$ADMIN_HANDLE = 'SS-TFH';

// Capturar datos de sesión necesarios y LIBERAR EL CANDADO DE SESIÓN inmediatamente
// (Sin esto, el bucle while(true) del SSE bloquea todos los POST ?action=send del usuario)
$session_user_id = $_SESSION['usuario_id'] ?? '';
$is_admin_session = !empty($_SESSION['es_admin']) || (strtolower((string)$session_user_id) === strtolower($ADMIN_HANDLE));
session_write_close();

$action = $_GET['action'] ?? 'view';

/**
 * Función auxiliar para guardar un mensaje en chat_db.json con bloqueo exclusivo (LOCK_EX)
 */
function append_chat_message(string $db_file, string $name, string $message, string $type = 'chat'): array {
    $msg = [
        'id'      => round(microtime(true), 4),
        'type'    => $type,
        'name'    => htmlspecialchars($name, ENT_QUOTES, 'UTF-8'),
        'message' => htmlspecialchars($message, ENT_QUOTES, 'UTF-8'),
        'ts'      => date('H:i')
    ];

    $fp = fopen($db_file, 'c+');
    if ($fp && flock($fp, LOCK_EX)) {
        clearstatcache(true, $db_file);
        $size    = filesize($db_file);
        $content = $size > 0 ? fread($fp, $size) : '[]';
        $chat    = json_decode($content, true);
        if (!is_array($chat)) {
            $chat = [];
        }
        $chat[] = $msg;

        if (count($chat) > 60) {
            $chat = array_slice($chat, -60);
        }

        ftruncate($fp, 0);
        rewind($fp);
        fwrite($fp, json_encode($chat, JSON_UNESCAPED_UNICODE));
        fflush($fp);
        flock($fp, LOCK_UN);
    }
    if ($fp) {
        fclose($fp);
    }
    return $msg;
}

// ==============================================================================
// 1. BACKEND: ENDPOINT PARA RECIBIR MENSAJES (AJAX POST)
// ==============================================================================
if ($action === 'send' && $_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json; charset=utf-8');
    $data = json_decode(file_get_contents('php://input'), true);

    if ($data && !empty(trim((string)($data['message'] ?? '')))) {
        $raw_name = trim((string)($data['name'] ?? 'Anónimo'));
        $raw_msg  = trim((string)$data['message']);

        // Evitar que un visitante se ponga manualmente "SS-TFH" si no es la sesión admin
        if (strtolower($raw_name) === strtolower($ADMIN_HANDLE) && !$is_admin_session) {
            $raw_name = 'Visitante_' . substr(md5($session_user_id), 0, 4);
        }

        $msg = append_chat_message($db_file, $raw_name, $raw_msg, 'chat');

        // --- SISTEMA DE NOTIFICACIONES PUSH VÍA TELEGRAM (HTML SEGURO) ---
        if (strtolower($raw_name) !== strtolower($ADMIN_HANDLE)) {
            $safe_sender = htmlspecialchars($raw_name, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
            $safe_body   = htmlspecialchars($raw_msg, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');

            $texto_alerta = "🔔 <b>Nuevo mensaje web de {$safe_sender}</b>\n\n{$safe_body}\n\n"
                          . "<i>Responde en Telegram con:</i> <code>/web tu respuesta</code>";
            $url = "https://api.telegram.org/bot{$BOT_TOKEN}/sendMessage";

            $options = [
                'http' => [
                    'method'  => 'POST',
                    'header'  => "Content-Type: application/x-www-form-urlencoded\r\n",
                    'content' => http_build_query([
                        'chat_id'    => $CHAT_ID,
                        'text'       => $texto_alerta,
                        'parse_mode' => 'HTML'
                    ]),
                    'timeout' => 2
                ]
            ];
            $context = stream_context_create($options);
            @file_get_contents($url, false, $context);
        }

        echo json_encode(['success' => true, 'msg' => $msg]);
    } else {
        echo json_encode(['success' => false, 'error' => 'Mensaje vacío']);
    }
    exit;
}

// ==============================================================================
// 2. BACKEND: ENDPOINT DE STREAMING EN TIEMPO REAL (SSE)
// ==============================================================================
if ($action === 'stream') {
    header('Content-Type: text/event-stream; charset=utf-8');
    header('Cache-Control: no-cache, no-store, must-revalidate');
    header('Connection: keep-alive');
    header('X-Accel-Buffering: no');

    if (function_exists('apache_setenv')) {
        @apache_setenv('no-gzip', '1');
    }
    @ini_set('zlib.output_compression', '0');
    @ini_set('implicit_flush', '1');
    while (ob_get_level() > 0) {
        ob_end_flush();
    }
    ob_implicit_flush(true);

    // Soportar tanto HTTP_LAST_EVENT_ID como parámetro GET last_id
    $last_id = 0.0;
    if (isset($_SERVER['HTTP_LAST_EVENT_ID']) && is_numeric($_SERVER['HTTP_LAST_EVENT_ID'])) {
        $last_id = (float)$_SERVER['HTTP_LAST_EVENT_ID'];
    } elseif (isset($_GET['last_id']) && is_numeric($_GET['last_id'])) {
        $last_id = (float)$_GET['last_id'];
    }

    $start_time = time();
    while (true) {
        if (connection_aborted()) {
            exit;
        }

        clearstatcache(true, $db_file);
        $fp = fopen($db_file, 'r');
        $chat = [];
        if ($fp && flock($fp, LOCK_SH)) {
            $size    = filesize($db_file);
            $content = $size > 0 ? fread($fp, $size) : '[]';
            $chat    = json_decode($content, true) ?: [];
            flock($fp, LOCK_UN);
        }
        if ($fp) {
            fclose($fp);
        }

        $new_msgs = array_filter($chat, function ($m) use ($last_id) {
            return isset($m['id']) && (float)$m['id'] > $last_id;
        });

        if (!empty($new_msgs)) {
            foreach ($new_msgs as $msg) {
                echo "id: " . $msg['id'] . "\n";
                echo "data: " . json_encode($msg, JSON_UNESCAPED_UNICODE) . "\n\n";
                $last_id = (float)$msg['id'];
            }
            @flush();
        }

        if (time() - $start_time > 15) {
            echo ": keepalive\n\n";
            @flush();
            exit;
        }

        usleep(450000); // 450ms
    }
}

// ==============================================================================
// 3. FRONTEND: UI MINIMALISTA CON SOPORTE @aryi Y RESPUESTAS DE TELEGRAM
// ==============================================================================
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Contacto Directo · Syntax Sanctuary</title>
    <style>
        :root {
            --bg: #0f172a; --panel: #1e293b; --text: #f8fafc;
            --primary: #10b981; --primary-hover: #059669;
            --msg-in: #334155; --msg-out: #064e3b; --msg-ai: #312e81;
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
        .status-indicator { width: 8px; height: 8px; border-radius: 50%; background: #ef4444; transition: background 0.3s; }
        .status-indicator.online { background: #22c55e; }

        .messages { flex: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 12px; background-image: url('data:image/svg+xml,%3Csvg width="20" height="20" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg"%3E%3Cg fill="%23ffffff" fill-opacity="0.03" fill-rule="evenodd"%3E%3Ccircle cx="3" cy="3" r="3"/%3E%3Ccircle cx="13" cy="13" r="3"/%3E%3C/g%3E%3C/svg%3E'); }
        .msg-wrapper { display: flex; flex-direction: column; max-width: 85%; }
        .msg-wrapper.out { align-self: flex-end; align-items: flex-end; }
        .msg-wrapper.in { align-self: flex-start; align-items: flex-start; }

        .sender-name { font-size: 0.75rem; color: #94a3b8; margin-bottom: 4px; margin-left: 4px; }
        .msg { padding: 10px 14px; border-radius: 12px; line-height: 1.4; font-size: 0.95rem; word-wrap: break-word; white-space: pre-wrap; box-shadow: 0 1px 2px rgba(0,0,0,0.2); }
        .msg.in { background: var(--msg-in); border-top-left-radius: 2px; }
        .msg.out { background: var(--msg-out); border-top-right-radius: 2px; }
        .msg.ai { background: var(--msg-ai); border: 1px solid #6366f1; border-top-left-radius: 2px; }

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
            <div class="header-title">Soporte Directo &amp; ARYI Omega</div>
            <div class="status-text">
                <span class="status-indicator" id="status-dot"></span>
                <span id="status-text">Sincronizando...</span>
            </div>
        </div>
    </div>
    <div class="messages" id="chat-box"></div>
    <div class="input-area">
        <input type="text" id="msg-input" placeholder="Escribe un mensaje (o usa @aryi)..." autocomplete="off" onfocus="requestNotifications()">
        <button onclick="sendMessage()" id="send-btn" title="Enviar">
            <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>
        </button>
    </div>
</div>

<script src="https://syntaxsanctuary.com/bit.js" data-user="SyntaxSanctuary_RGG"></script>
<script>
    let userHandle = localStorage.getItem('chat_handle');
    if (!userHandle) {
        userHandle = prompt("¿Cómo te llamas?", "Visitante_" + Math.floor(Math.random() * 1000));
        localStorage.setItem('chat_handle', userHandle || 'Anónimo');
    }

    const chatBox    = document.getElementById('chat-box');
    const msgInput   = document.getElementById('msg-input');
    const statusDot  = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const loadedIds  = new Set();
    let lastEventId  = 0;

    function decodeHtmlEntities(str) {
        const txt = document.createElement('textarea');
        txt.innerHTML = str;
        return txt.value;
    }

    const evtSource = new EventSource("?action=stream");

    evtSource.onopen = () => {
        statusDot.classList.add('online');
        statusText.innerText = "En línea (Telegram + ARYI Bridge)";
    };

    evtSource.onerror = () => {
        statusDot.classList.remove('online');
        statusText.innerText = "Reconectando stream...";
    };

    evtSource.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (loadedIds.has(data.id)) return;
        loadedIds.add(data.id);
        lastEventId = Math.max(lastEventId, data.id);

        renderMessage(data);

        if (data.name !== userHandle && document.hidden) {
            triggerNotification(decodeHtmlEntities(data.name), decodeHtmlEntities(data.message));
        }
    };

    async function sendMessage() {
        const text = msgInput.value.trim();
        if (!text) return;
        msgInput.value = '';
        try {
            await fetch('?action=send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: userHandle, message: text })
            });
        } catch (err) {
            console.error("Error enviando mensaje:", err);
        }
    }

    function renderMessage(data) {
        const cleanName = decodeHtmlEntities(data.name);
        const cleanMsg  = decodeHtmlEntities(data.message);
        const isMe      = cleanName === userHandle;
        const isAI      = cleanName === 'ARYI_OMEGA';

        const div = document.createElement('div');
        div.className = `msg-wrapper ${isMe ? 'out' : 'in'}`;

        const nameSpan = document.createElement('span');
        nameSpan.className = 'sender-name';
        nameSpan.innerText = isMe ? 'Tú' : (isAI ? '🤖 ARYI OMEGA' : cleanName);

        const bubble = document.createElement('div');
        bubble.className = `msg ${isMe ? 'out' : (isAI ? 'ai' : 'in')}`;
        bubble.innerText = cleanMsg;

        if (!isMe) div.appendChild(nameSpan);
        div.appendChild(bubble);

        chatBox.appendChild(div);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    msgInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') sendMessage();
    });

    function requestNotifications() {
        if ("Notification" in window && Notification.permission !== "granted" && Notification.permission !== "denied") {
            Notification.requestPermission();
        }
    }

    function triggerNotification(title, body) {
        if ("Notification" in window && Notification.permission === "granted") {
            new Notification(title, {
                body: body,
                icon: 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iIzEwYjk4MSI+PHBhdGggZD0iTTIwIDJIMTRDMTIuOSAyIDEyIDIuOSAxMiA0VjE2QzEyIDE3LjEgMTIuOSAxOCAxNCAxOEgyMEMyMS4xIDE4IDIyIDE3LjEgMjIgMTZWNEMyMiAyLjkgMjEuMSAyIDIwIDJaIi8+PC9zdmc+'
            });
        }
    }
</script>

</body>
</html>