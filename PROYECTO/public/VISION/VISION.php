<?php
/**
 * Monolito Multimodal con Selector de Modelos - Ollama Vision Telemetry (stream = false)
 * Puerto por defecto: 11434 | Endpoint: http://100.115.1.71:11434/api/generate
 */
declare(strict_types=1);

session_start();

if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id']) || empty($_SESSION['hash_verificado'])) {
    header('Location: ../InicioDeSesion/verificar.php');
    exit;
}

$visionModels = [
    'moondream:latest',
    'virtuanista/lfm2.5-8b-a1b-uncensored:q8_0',
    'llava-phi3:latest',
    'llama3.2-vision:latest'
];

$ollamaUrl = 'http://100.115.1.71:11434/api/generate';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    header('Content-Type: application/json; charset=utf-8');
    header('X-Content-Type-Options: nosniff');
    header('Cache-Control: no-store, no-cache, must-revalidate');

    $rawInput = file_get_contents('php://input');
    $input    = json_decode($rawInput ?: '', true);

    if (!is_array($input) || empty(trim((string)($input['prompt'] ?? '')))) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'error' => 'El campo "prompt" es obligatorio.'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    if (empty($input['image_base64']) || !is_string($input['image_base64'])) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'error' => 'El campo "image_base64" es obligatorio.'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $prompt = trim((string)$input['prompt']);
    $model  = trim((string)($input['model'] ?? 'moondream:latest'));
    
    if (!in_array($model, $visionModels, true)) {
        $model = 'moondream:latest';
    }

    $rawB64 = trim($input['image_base64']);
    if (str_contains($rawB64, ',')) { $rawB64 = explode(',', $rawB64, 2)[1]; }

    $imageBinary = base64_decode($rawB64, true);
    if ($imageBinary === false || strlen($imageBinary) < 32) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'error' => 'Base64 de imagen no válido.'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $imgMeta = @getimagesizefromstring($imageBinary);
    $imageTelemetry = [
        'width'      => is_array($imgMeta) ? (int)$imgMeta[0] : 0,
        'height'     => is_array($imgMeta) ? (int)$imgMeta[1] : 0,
        'mime'       => is_array($imgMeta) && isset($imgMeta['mime']) ? (string)$imgMeta['mime'] : 'image/unknown',
        'size_bytes' => strlen($imageBinary),
        'megapixels' => is_array($imgMeta) ? round(($imgMeta[0] * $imgMeta[1]) / 1e6, 3) : 0.0
    ];

    $payload = [
        'model'   => $model,
        'prompt'  => $prompt,
        'images'  => [$rawB64],
        'stream'  => false,
        'options' => ['temperature' => isset($input['temperature']) ? (float)$input['temperature'] : 0.2]
    ];

    $startNs = hrtime(true);
    $ch = curl_init($ollamaUrl);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => json_encode($payload, JSON_UNESCAPED_UNICODE),
        CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 300,
        CURLOPT_TIMEOUT        => 0,
    ]);

    $responseBody = curl_exec($ch);
    $curlErrno    = curl_errno($ch);
    $curlError    = curl_error($ch);
    $httpCode     = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $bridgeDurationMs = round((hrtime(true) - $startNs) / 1e6, 2);

    if ($curlErrno !== 0 || $responseBody === false) {
        http_response_code(502);
        echo json_encode([
            'ok'            => false,
            'error'         => 'No se pudo conectar con Ollama en el puerto 11434.',
            'details'       => $curlError,
            'php_bridge_ms' => $bridgeDurationMs
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $ollamaData = json_decode((string)$responseBody, true);
    if ($httpCode >= 400 || !is_array($ollamaData)) {
        http_response_code($httpCode >= 400 ? $httpCode : 500);
        echo json_encode([
            'ok'            => false,
            'error'         => $ollamaData['error'] ?? 'Error en Ollama.',
            'php_bridge_ms' => $bridgeDurationMs
        ], JSON_UNESCAPED_UNICODE);
        exit;
    }

    echo json_encode([
        'ok'            => true,
        'php_bridge_ms' => $bridgeDurationMs,
        'input_image'   => $imageTelemetry,
        'ollama'        => $ollamaData
    ], JSON_UNESCAPED_UNICODE);
    exit;
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Monolito Multimodal con Selector</title>
    <style>
        :root { --bg: #0f172a; --surface: #1e293b; --surface-alt: #0b1120; --border: #334155; --text: #f8fafc; --muted: #94a3b8; --primary: #38bdf8; --success: #22c55e; --warning: #f59e0b; --danger: #ef4444; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background-color: var(--bg); color: var(--text); font-family: system-ui, sans-serif; padding: 1.5rem; line-height: 1.5; }
        .container { max-width: 1100px; margin: 0 auto; display: grid; gap: 1rem; }
        header, .card { background: var(--surface); border: 1px solid var(--border); border-radius: 0.75rem; padding: 1.25rem; display: flex; flex-direction: column; gap: 0.85rem; }
        header { flex-direction: row; justify-content: space-between; align-items: center; }
        textarea, select, button, input[type="file"] { width: 100%; background: var(--surface-alt); border: 1px solid var(--border); border-radius: 0.5rem; color: var(--text); padding: 0.7rem; font-family: monospace; }
        textarea { min-height: 80px; resize: vertical; }
        select { margin-bottom: 0.5rem; }
        button { background: var(--primary); color: #082f49; font-weight: 600; cursor: pointer; width: auto; padding: 0.6rem 1.2rem; }
        button:hover { background: #0284c7; color: #fff; }
        .btn-sec { background: var(--surface-alt); color: var(--text); border: 1px solid var(--border); }
        .grid-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.6rem; }
        .metric { background: var(--surface-alt); border: 1px solid var(--border); border-radius: 0.4rem; padding: 0.6rem; }
        .m-label { font-size: 0.7rem; color: var(--muted); text-transform: uppercase; }
        .m-val { font-family: monospace; font-size: 0.95rem; font-weight: bold; color: var(--primary); margin-top: 0.2rem; }
        pre { background: var(--surface-alt); border: 1px solid var(--border); border-radius: 0.5rem; padding: 0.8rem; font-family: monospace; font-size: 0.8rem; max-height: 220px; overflow: auto; white-space: pre-wrap; }
        .badge { font-size: 0.75rem; padding: 0.3rem 0.6rem; border-radius: 0.4rem; border: 1px solid var(--border); background: var(--surface-alt); color: var(--muted); }
        .preview { max-width: 100%; max-height: 180px; border-radius: 0.4rem; border: 1px solid var(--border); display: block; margin: 0.5rem auto; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Monolito Multimodal (4 Modelos Vision)</h1>
                <p style="color: var(--muted); font-size: 0.85rem;">Selecciona el modelo multimodal para analizar la imagen</p>
            </div>
            <span id="badge" class="badge">Listo</span>
        </header>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <section class="card">
                <h3>Modelo, Imagen y Prompt</h3>
                <form id="f">
                    <label>Seleccionar Modelo de Visión:</label>
                    <select id="model-select">
                        <?php foreach ($visionModels as $vm): ?>
                            <option value="<?= htmlspecialchars($vm) ?>"><?= htmlspecialchars($vm) ?></option>
                        <?php endforeach; ?>
                    </select>

                    <label>Subir imagen o generar lámina de prueba:</label>
                    <div style="display: flex; gap: 0.5rem;">
                        <input type="file" id="file" accept="image/*">
                        <button type="button" id="sample-btn" class="btn-sec">Lámina Test</button>
                    </div>
                    <img id="prev" class="preview" alt="Vista previa">
                    
                    <label style="margin-top:0.5rem;">Instrucción / Pregunta (Prompt):</label>
                    <textarea id="p" required>Describe this image in detail, including main objects and text.</textarea>
                    
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:0.5rem;">
                        <span style="font-size:0.8rem; color:var(--muted);">Temp: <strong id="t-val">0.2</strong> <input type="range" id="t" min="0" max="1" step="0.1" value="0.2"></span>
                        <button type="submit" id="btn">Analizar Multimodal</button>
                    </div>
                </form>
            </section>

            <section class="card">
                <h3>Respuesta Visual del Modelo</h3>
                <pre id="out">Sube una imagen y envía la petición...</pre>
                
                <h3>Telemetría Multimodal</h3>
                <div class="grid-metrics">
                    <div class="metric"><div class="m-label">Velocidad (t/s)</div><div id="m-tps" class="m-val">--</div></div>
                    <div class="metric"><div class="m-label">Encoder Visual</div><div id="m-vis" class="m-val">--</div></div>
                    <div class="metric"><div class="m-label">Duración Total</div><div id="m-tot" class="m-val">--</div></div>
                    <div class="metric"><div class="m-label">Dimensiones</div><div id="m-dim" class="m-val">--</div></div>
                </div>
                <pre id="json-out">{}</pre>
            </section>
        </div>
    </div>

    <script>
    'use strict';
    let b64Img = '';

    function makeTestCanvas() {
        const c = document.createElement('canvas');
        c.width = 500; c.height = 300;
        const ctx = c.getContext('2d');
        ctx.fillStyle = '#0f172a'; ctx.fillRect(0, 0, 500, 300);
        ctx.fillStyle = '#38bdf8'; ctx.font = 'bold 20px sans-serif';
        ctx.fillText('VISION TEST CARD', 30, 50);
        ctx.fillStyle = '#22c55e'; ctx.font = '16px monospace';
        ctx.fillText('STATUS: OPERATIONAL', 30, 90);
        ctx.fillStyle = '#ef4444'; ctx.beginPath(); ctx.arc(100, 180, 40, 0, Math.PI*2); ctx.fill();
        ctx.fillStyle = '#f59e0b'; ctx.beginPath(); ctx.arc(250, 180, 40, 0, Math.PI*2); ctx.fill();
        b64Img = c.toDataURL('image/png');
        document.getElementById('prev').src = b64Img;
    }

    document.getElementById('file').addEventListener('change', (e) => {
        const file = e.target.files?.[0];
        if(!file) return;
        const r = new FileReader();
        r.onload = (evt) => {
            b64Img = evt.target.result;
            document.getElementById('prev').src = b64Img;
        };
        r.readAsDataURL(file);
    });

    document.getElementById('sample-btn').addEventListener('click', makeTestCanvas);
    makeTestCanvas();

    document.getElementById('f').addEventListener('submit', async (e) => {
        e.preventDefault();
        const out = document.getElementById('out');
        const badge = document.getElementById('badge');
        const btn = document.getElementById('btn');
        
        out.textContent = 'Procesando imagen y consultando Ollama...';
        badge.textContent = 'Analizando...';
        btn.disabled = true;

        try {
            const res = await fetch('', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    model: document.getElementById('model-select').value,
                    prompt: document.getElementById('p').value,
                    image_base64: b64Img,
                    temperature: parseFloat(document.getElementById('t').value)
                })
            });
            const data = await res.json();
            if(!data.ok) throw new Error(data.error || 'Error en servidor');

            out.textContent = data.ollama.response;
            document.getElementById('m-tps').textContent = `${(data.ollama.eval_count / (data.ollama.eval_duration / 1e9)).toFixed(1)} t/s`;
            document.getElementById('m-vis').textContent = `${(data.ollama.prompt_eval_duration / 1e6).toFixed(1)} ms`;
            document.getElementById('m-tot').textContent = `${(data.ollama.total_duration / 1e6).toFixed(1)} ms`;
            document.getElementById('m-dim').textContent = `${data.input_image.width}x${data.input_image.height}`;
            document.getElementById('json-out').textContent = JSON.stringify(data, null, 2);
            badge.textContent = 'Éxito';
        } catch(err) {
            out.textContent = `Error: ${err.message}`;
            badge.textContent = 'Error';
        } finally {
            btn.disabled = false;
        }
    });
    </script>
</body>
</html>