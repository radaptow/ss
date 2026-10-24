<?php
/**
 * Monolito Text-Only con Selector de Modelos - Ollama Streaming (stream = true)
 * Puerto por defecto: 11434 | Endpoint: http://100.115.1.71:11434/api/generate
 */
declare(strict_types=1);

session_start();

if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id']) || empty($_SESSION['hash_verificado'])) {
    header('Location: ../InicioDeSesion/verificar.php');
    exit;
}

$textModels = [
    'qwen3-coder:30b',
    'nemotron-3.5-bolt:latest',
    'muse-glimmer:latest',
    'qwen3.8:27b',
    'bonsai-2:27b',
    'bonsai-2:4b',
    'qwen2.5-coder:0.5b',
    'gemma2:9b',
    'aya:8b',
    'qwen2.5-coder:7b'
];

$ollamaUrl = 'http://100.115.1.71:11434/api/generate';

// Procesar petición API POST
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/x-ndjson; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    header('Cache-Control: no-store, no-cache, must-revalidate');
    header('X-Accel-Buffering: no');

    @ini_set('zlib.output_compression', '0');
    @ini_set('implicit_flush', '1');
    while (ob_get_level() > 0) { ob_end_flush(); }
    ob_implicit_flush(true);

    $rawInput = file_get_contents('php://input');
    $input    = json_decode($rawInput ?: '', true);

    if (!is_array($input) || empty(trim((string)($input['prompt'] ?? '')))) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'error' => 'El campo "prompt" es obligatorio.'], JSON_UNESCAPED_UNICODE) . "\n";
        exit;
    }

    $prompt = trim((string)$input['prompt']);
    $model  = trim((string)($input['model'] ?? 'qwen2.5-coder:0.5b'));
    
    // Validar que el modelo pertenezca a la lista permitida
    if (!in_array($model, $textModels, true)) {
        $model = 'qwen2.5-coder:0.5b';
    }

    $payload = [
        'model'   => $model,
        'prompt'  => $prompt,
        'stream'  => true,
        'options' => ['temperature' => isset($input['temperature']) ? (float)$input['temperature'] : 0.2]
    ];

    $startTimeNs  = hrtime(true);
    $firstChunkNs = null;

    $ch = curl_init($ollamaUrl);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode($payload, JSON_UNESCAPED_UNICODE),
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => false,
        CURLOPT_CONNECTTIMEOUT => 300,
        CURLOPT_TIMEOUT        => 0,
        CURLOPT_WRITEFUNCTION  => function ($ch, string $chunk) use ($startTimeNs, &$firstChunkNs): int {
            if ($firstChunkNs === null && trim($chunk) !== '') {
                $firstChunkNs = hrtime(true);
            }
            echo $chunk;
            flush();
            return strlen($chunk);
        }
    ]);

    $success   = curl_exec($ch);
    $curlErrno = curl_errno($ch);
    $curlError = curl_error($ch);
    $httpCode  = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $bridgeDurationMs = round((hrtime(true) - $startTimeNs) / 1e6, 2);
    $ttftBridgeMs     = $firstChunkNs !== null ? round(($firstChunkNs - $startTimeNs) / 1e6, 2) : $bridgeDurationMs;

    if ($curlErrno !== 0 || $success === false || $httpCode >= 400) {
        echo json_encode([
            'ok'            => false,
            'error'         => $curlError ?: "Error HTTP {$httpCode} desde Ollama (:11434).",
            'endpoint'      => $ollamaUrl,
            'php_bridge_ms' => $bridgeDurationMs
        ], JSON_UNESCAPED_UNICODE) . "\n";
        exit;
    }

    echo json_encode([
        'bridge_summary' => true,
        'ok'             => true,
        'endpoint'       => $ollamaUrl,
        'php_bridge_ms'  => $bridgeDurationMs,
        'php_ttft_ms'    => $ttftBridgeMs
    ], JSON_UNESCAPED_UNICODE) . "\n";
    exit;
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Monolito Text-Only con Selector</title>
    <style>
        :root { --bg: #0f172a; --surface: #1e293b; --surface-alt: #0b1120; --border: #334155; --text: #f8fafc; --muted: #94a3b8; --primary: #38bdf8; --success: #22c55e; --warning: #f59e0b; --danger: #ef4444; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background-color: var(--bg); color: var(--text); font-family: system-ui, sans-serif; padding: 1.5rem; line-height: 1.5; }
        .container { max-width: 1000px; margin: 0 auto; display: grid; gap: 1rem; }
        header, .card { background: var(--surface); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.25rem; display: flex; flex-direction: column; gap: 0.85rem; }
        header { flex-direction: row; justify-content: space-between; align-items: center; }
        textarea, select, button { width: 100%; background: var(--surface-alt); border: 1px solid var(--border); border-radius: 0.5rem; color: var(--text); padding: 0.7rem; font-family: monospace; }
        textarea { min-height: 90px; resize: vertical; }
        select { margin-bottom: 0.5rem; }
        button { background: var(--primary); color: #082f49; font-weight: 600; cursor: pointer; width: auto; padding: 0.6rem 1.2rem; }
        button:hover { background: #0284c7; color: #fff; }
        .grid-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.6rem; }
        .metric { background: var(--surface-alt); border: 1px solid var(--border); border-radius: 0.4rem; padding: 0.6rem; }
        .m-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; }
        .m-val { font-family: monospace; font-size: 0.95rem; font-weight: bold; color: var(--primary); margin-top: 0.2rem; }
        pre { background: var(--surface-alt); border: 1px solid var(--border); border-radius: 0.5rem; padding: 0.8rem; font-family: monospace; font-size: 0.8rem; max-height: 220px; overflow: auto; white-space: pre-wrap; }
        .badge { font-size: 0.75rem; padding: 0.3rem 0.6rem; border-radius: 0.4rem; border: 1px solid var(--border); background: var(--surface-alt); color: var(--muted); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Monolito Text-Only (10 Modelos)</h1>
                <p style="color: var(--muted); font-size: 0.85rem;">Selecciona el modelo de texto para la inferencia</p>
            </div>
            <span id="badge" class="badge">Listo</span>
        </header>

        <section class="card">
            <form id="f">
                <label>Seleccionar Modelo de Texto:</label>
                <select id="model-select">
                    <?php foreach ($textModels as $m): ?>
                        <option value="<?= htmlspecialchars($m) ?>" <?= $m === 'qwen2.5-coder:0.5b' ? 'selected' : '' ?>><?= htmlspecialchars($m) ?></option>
                    <?php endforeach; ?>
                </select>

                <label>Prompt:</label>
                <textarea id="p" required>Escribe una función en PHP que valide un correo electrónico.</textarea>
                
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.5rem;">
                    <span style="font-size:0.8rem; color:var(--muted);">Temperatura: <strong id="t-val">0.2</strong> <input type="range" id="t" min="0" max="1" step="0.1" value="0.2"></span>
                    <button type="submit" id="btn">Transmitir Stream</button>
                </div>
            </form>
            <h3>Salida en Vivo:</h3>
            <pre id="out">Pulsa el botón para iniciar...</pre>
        </section>

        <section class="card">
            <h3>Telemetría del Flujo</h3>
            <div class="grid-metrics">
                <div class="metric"><div class="m-label">Velocidad (t/s)</div><div id="m-tps" class="m-val">--</div></div>
                <div class="metric"><div class="m-label">Primer Token (TTFT)</div><div id="m-ttft" class="m-val">--</div></div>
                <div class="metric"><div class="m-label">Duración Total</div><div id="m-tot" class="m-val">--</div></div>
                <div class="metric"><div class="m-label">Tokens Totales</div><div id="m-tok" class="m-val">--</div></div>
            </div>
            <pre id="json-out">{}</pre>
        </section>
    </div>

    <script>
    'use strict';
    const UI = {
        f: document.getElementById('f'), modelSelect: document.getElementById('model-select'),
        p: document.getElementById('p'), t: document.getElementById('t'),
        tv: document.getElementById('t-val'), btn: document.getElementById('btn'), badge: document.getElementById('badge'),
        out: document.getElementById('out'), json: document.getElementById('json-out'),
        tps: document.getElementById('m-tps'), ttft: document.getElementById('m-ttft'),
        tot: document.getElementById('m-tot'), tok: document.getElementById('m-tok')
    };
    UI.t.addEventListener('input', e => UI.tv.textContent = e.target.value);

    UI.f.addEventListener('submit', async (e) => {
        e.preventDefault();
        UI.out.textContent = '';
        UI.badge.textContent = 'Transmitiendo...';
        UI.btn.disabled = true;
        const start = performance.now();
        let firstTok = null, chunks = 0, finalPacket = null, bridgePacket = null;

        try {
            const res = await fetch('', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    model: UI.modelSelect.value,
                    prompt: UI.p.value,
                    temperature: parseFloat(UI.t.value)
                })
            });
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buf = '';

            while(true) {
                const {value, done} = await reader.read();
                if(done) break;
                buf += decoder.decode(value, {stream: true});
                const lines = buf.split('\n');
                buf = lines.pop() || '';

                for(const line of lines) {
                    if(!line.trim()) continue;
                    const pkt = JSON.parse(line);
                    if(pkt.bridge_summary) { bridgePacket = pkt; continue; }
                    if(pkt.response) {
                        if(!firstTok) { firstTok = performance.now(); UI.ttft.textContent = `${(firstTok - start).toFixed(1)} ms`; }
                        chunks++;
                        UI.out.textContent += pkt.response;
                        UI.tps.textContent = `${(chunks / Math.max(0.01, (performance.now() - firstTok)/1000)).toFixed(1)} t/s`;
                    }
                    if(pkt.done) finalPacket = pkt;
                }
            }
            const total = (performance.now() - start).toFixed(1);
            UI.tot.textContent = `${total} ms`;
            if(finalPacket) {
                UI.tok.textContent = `${(finalPacket.prompt_eval_count||0) + (finalPacket.eval_count||chunks)}`;
                UI.json.textContent = JSON.stringify({final: finalPacket, bridge: bridgePacket}, null, 2);
            }
            UI.badge.textContent = 'Completado';
        } catch(err) {
            UI.out.textContent = `Error: ${err.message}`;
            UI.badge.textContent = 'Error';
        } finally {
            UI.btn.disabled = false;
        }
    });
    </script>
</body>
</html>