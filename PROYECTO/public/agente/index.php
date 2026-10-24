<?php declare(strict_types=1);
session_start();

if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id']) || empty($_SESSION['hash_verificado'])) {
    header('Location: ../InicioDeSesion/verificar.php');
    exit;
}

// ============================================================
// 1. BLINDAJE DE EJECUCIÓN PARA HARDWARE LOCAL (i7 / 32GB / 6GB VRAM)
// ============================================================
ini_set('display_errors', '0');
ini_set('display_startup_errors', '0');
ini_set('log_errors', '1');
error_reporting(E_ALL);

// Timeouts infinitos (0) para permitir intercambio entre 6GB VRAM y 32GB RAM
set_time_limit(0);
ini_set('max_execution_time', '0');
ini_set('max_input_time', '-1');
ini_set('memory_limit', '512M');

ob_start();
session_start();

// ============================================================
// 2. CONFIGURACIÓN DEL SISTEMA Y ENDPOINTS (WINDOWS DOCKER)
// ============================================================
$PASSWORD_SECRETA     = "ss-tfh-free"; // Cambia esto por tu contraseña segura
$DOCKER_IP            = '100.115.1.71';
$DEFAULT_OLLAMA_MODEL = 'qwen2.5-coder:0.5b';


$API_STT         = "http://{$DOCKER_IP}:8000/v1/audio/transcriptions";
$API_OLLAMA_GEN  = "http://{$DOCKER_IP}:11434/api/generate";
$API_OLLAMA_TAGS = "http://{$DOCKER_IP}:11434/api/tags";
$API_OLLAMA_PS   = "http://{$DOCKER_IP}:11434/api/ps";
$API_TTS         = "http://{$DOCKER_IP}:5050/tts";
$API_SD          = "http://{$DOCKER_IP}:7860/sdapi/v1/txt2img";

// Archivo de estado para Cola FIFO y Telemetría
$tempDir = sys_get_temp_dir();
if (!is_writable($tempDir)) {
    $tempDir = __DIR__;
}
$TELEMETRY_FILE = rtrim($tempDir, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR . 'aryi_queue_telemetry_v5.json';

// ============================================================
// 3. MOTOR DE BLINDAJE JSON Y STREAMING ANTI-524 (CLOUDFLARE)
// ============================================================
$IS_API_REQUEST   = isset($_GET['action']);
$STREAM_MODE_OPEN = false;

function sendSafeJson(array $payload, int $httpCode = 200): never {
    global $STREAM_MODE_OPEN;
    if ($STREAM_MODE_OPEN) {
        echo "\n" . json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE) . "\n";
        if (ob_get_level() > 0) {
            @ob_flush();
        }
        flush();
        exit;
    }

    while (ob_get_level() > 0) {
        @ob_end_clean();
    }
    if (!headers_sent()) {
        http_response_code($httpCode);
        header('Content-Type: application/json; charset=utf-8');
        header('Cache-Control: no-store, no-cache, must-revalidate');
        header('X-Content-Type-Options: nosniff');
    }
    $json = json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
    echo ($json !== false) ? $json : '{"ok":false,"error":"Error interno serializando JSON."}';
    exit;
}

/**
 * Abre inmediatamente el canal HTTP 200 con Cloudflare/Apache enviando 4KB de padding
 * para evitar el corte por timeout de 100s de Cloudflare (Error HTTP 524).
 */
function openAnti524Stream(string $ticketId, string $phaseLabel): void {
    global $STREAM_MODE_OPEN;
    $STREAM_MODE_OPEN = true;

    while (ob_get_level() > 0) {
        @ob_end_clean();
    }
    @ini_set('zlib.output_compression', '0');
    @ini_set('implicit_flush', '1');
    if (function_exists('apache_setenv')) {
        @apache_setenv('no-gzip', '1');
    }

    if (!headers_sent()) {
        http_response_code(200);
        header('Content-Type: application/x-ndjson; charset=utf-8');
        header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
        header('X-Accel-Buffering: no');
        header('Content-Encoding: none');
    }

    $initPacket = json_encode([
        'type'   => 'init',
        'ok'     => true,
        'ticket' => $ticketId,
        'phase'  => $phaseLabel,
        'pad'    => str_repeat('.', 4096)
    ], JSON_UNESCAPED_UNICODE);

    echo $initPacket . "\n";
    if (ob_get_level() > 0) {
        @ob_flush();
    }
    flush();
}

function emitStreamLine(array $payload): void {
    echo json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE) . "\n";
    if (ob_get_level() > 0) {
        @ob_flush();
    }
    flush();
}

if ($IS_API_REQUEST) {
    set_error_handler(function (int $severity, string $message, string $file, int $line): bool {
        if (!(error_reporting() & $severity)) {
            return false;
        }
        throw new ErrorException($message, 0, $severity, $file, $line);
    });

    set_exception_handler(function (Throwable $e): void {
        sendSafeJson([
            'type'  => 'error',
            'ok'    => false,
            'error' => 'Excepción en servidor: ' . $e->getMessage()
        ], 500);
    });

    register_shutdown_function(function (): void {
        $err = error_get_last();
        if ($err !== null && in_array($err['type'], [E_ERROR, E_PARSE, E_CORE_ERROR, E_COMPILE_ERROR, E_USER_ERROR], true)) {
            sendSafeJson([
                'type'  => 'error',
                'ok'    => false,
                'error' => 'Error fatal de PHP: ' . $err['message']
            ], 500);
        }
    });
}

// ============================================================
// 4. MOTOR DE COLA ESTRICTA (FIFO) Y TELEMETRÍA
// ============================================================
function getDefaultTelemetryState(): array {
    return [
        'queue'   => [],
        'metrics' => [
            'stt'    => ['avg_ms' => 3200,  'last_ms' => 3200,  'count' => 1, 'label' => 'Whisper STT'],
            'ollama' => ['avg_ms' => 14000, 'last_ms' => 14000, 'count' => 1, 'label' => 'Ollama LLM'],
            'tts'    => ['avg_ms' => 4200,  'last_ms' => 4200,  'count' => 1, 'label' => 'Motor Voz TTS'],
            'sd'     => ['avg_ms' => 26000, 'last_ms' => 26000, 'count' => 1, 'label' => 'Stable Diffusion']
        ]
    ];
}

function mutateTelemetryState(string $file, callable $callback): array {
    $fp = @fopen($file, 'c+');
    if (!$fp) {
        $dummy = getDefaultTelemetryState();
        $res   = $callback($dummy, microtime(true));
        return is_array($res) ? $res : $dummy;
    }

    flock($fp, LOCK_EX);
    $raw   = stream_get_contents($fp);
    $state = ($raw !== false && $raw !== '') ? json_decode($raw, true) : null;
    if (!is_array($state) || !isset($state['queue'], $state['metrics'])) {
        $state = getDefaultTelemetryState();
    }

    $now = microtime(true);

    // Limpieza automática de tickets inactivos:
    // - En espera ('queued'/'ready'): si el cliente cierra pestaña o pierde red por > 10s -> pierde turno.
    // - En GPU ('processing'): el callback de cURL actualiza cada 1.2s; si lleva > 25s sin latido -> libera cola.
    foreach ($state['queue'] as $id => $item) {
        $lastBeat = (float)($item['updated_at'] ?? $now);
        $status   = (string)($item['status'] ?? 'queued');
        $timeout  = ($status === 'processing') ? 25.0 : 10.0;
        if (($now - $lastBeat) > $timeout) {
            unset($state['queue'][$id]);
        }
    }

    // Ordenar estrictamente por llegada (FIFO)
    uasort($state['queue'], fn($a, $b) => ($a['created_at'] <=> $b['created_at']));

    // Promover al #1 de la fila si está esperando
    $firstKey = array_key_first($state['queue']);
    if ($firstKey !== null && $state['queue'][$firstKey]['status'] === 'queued') {
        $state['queue'][$firstKey]['status']      = 'ready';
        $state['queue'][$firstKey]['promoted_at'] = $now;
    }

    $result = $callback($state, $now);

    ftruncate($fp, 0);
    rewind($fp);
    fwrite($fp, (string)json_encode($state, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE));
    fflush($fp);
    flock($fp, LOCK_UN);
    fclose($fp);

    return is_array($result) ? $result : $state;
}

function purgeOperatorTickets(string $file, string $operatorId): void {
    if ($operatorId === '') return;
    mutateTelemetryState($file, function (&$state, $now) use ($operatorId) {
        foreach ($state['queue'] as $id => $item) {
            if (($item['operator_id'] ?? '') === $operatorId) {
                unset($state['queue'][$id]);
            }
        }
        uasort($state['queue'], fn($a, $b) => ($a['created_at'] <=> $b['created_at']));
        $firstKey = array_key_first($state['queue']);
        if ($firstKey !== null && $state['queue'][$firstKey]['status'] === 'queued') {
            $state['queue'][$firstKey]['status']      = 'ready';
            $state['queue'][$firstKey]['promoted_at'] = $now;
        }
        return $state;
    });
}

function touchAndCheckTicket(string $file, string $ticketId): bool {
    $valid = false;
    mutateTelemetryState($file, function (&$state, $now) use ($ticketId, &$valid) {
        if (isset($state['queue'][$ticketId])) {
            $state['queue'][$ticketId]['updated_at'] = $now;
            $valid = true;
        }
        return $state;
    });
    return $valid;
}

function buildTelemetrySnapshot(string $file, string $ticketId): array {
    return mutateTelemetryState($file, function (&$state, $now) use ($ticketId) {
        if ($ticketId !== '' && isset($state['queue'][$ticketId])) {
            $state['queue'][$ticketId]['updated_at'] = $now;
        }

        uasort($state['queue'], fn($a, $b) => ($a['created_at'] <=> $b['created_at']));
        $queueList  = array_values($state['queue']);
        $totalQueue = count($queueList);
        $position   = 0;
        $etaMs      = 0.0;
        $myItem     = null;
        $firstItem  = $queueList[0] ?? null;

        foreach ($queueList as $idx => $item) {
            $taskKey = $item['task'] ?? 'ollama';
            $taskAvg = (float)($state['metrics'][$taskKey]['avg_ms'] ?? 10000);

            if ($item['status'] === 'processing' && !empty($item['started_at'])) {
                $elapsedCurrent = ($now - (float)$item['started_at']) * 1000.0;
                $remaining      = max(2000.0, $taskAvg - $elapsedCurrent);
            } else {
                $remaining = $taskAvg;
            }

            if ($item['id'] === $ticketId) {
                $position = $idx + 1;
                $myItem   = $item;
                $etaMs   += $remaining;
                break;
            } else {
                $etaMs += $remaining;
            }
        }

        $activeTaskLabel = 'GPU Libre';
        if ($firstItem) {
            $tKey            = $firstItem['task'] ?? 'ollama';
            $tName           = $state['metrics'][$tKey]['label'] ?? strtoupper($tKey);
            $activeTaskLabel = "Procesando petición #1 ({$tName})";
        }

        return [
            'ok'                => true,
            'ticket'            => $ticketId,
            'status'            => $myItem['status'] ?? 'none',
            'turn'              => $position,
            'can_execute'       => ($position === 1 && in_array($myItem['status'] ?? '', ['ready', 'processing'], true)),
            'queue_total'       => $totalQueue,
            'active_task_label' => $activeTaskLabel,
            'elapsed_ms'        => $myItem ? round(($now - (float)$myItem['created_at']) * 1000) : 0,
            'eta_ms'            => round($etaMs),
            'metrics'           => $state['metrics']
        ];
    });
}

function finishTicketAndRecordMetric(string $file, string $ticketId, string $taskType, float $durationMs): void {
    mutateTelemetryState($file, function (&$state, $now) use ($ticketId, $taskType, $durationMs) {
        unset($state['queue'][$ticketId]);

        if (isset($state['metrics'][$taskType]) && $durationMs > 80) {
            $oldAvg = (float)$state['metrics'][$taskType]['avg_ms'];
            $count  = (int)$state['metrics'][$taskType]['count'];
            $newAvg = ($count <= 1) ? $durationMs : (($oldAvg * 0.7) + ($durationMs * 0.3));
            $state['metrics'][$taskType]['avg_ms']  = round($newAvg);
            $state['metrics'][$taskType]['last_ms'] = round($durationMs);
            $state['metrics'][$taskType]['count']   = $count + 1;
        }

        uasort($state['queue'], fn($a, $b) => ($a['created_at'] <=> $b['created_at']));
        $firstKey = array_key_first($state['queue']);
        if ($firstKey !== null && $state['queue'][$firstKey]['status'] === 'queued') {
            $state['queue'][$firstKey]['status']      = 'ready';
            $state['queue'][$firstKey]['promoted_at'] = $now;
        }
        return $state;
    });
}

function lockServerTurnForExecution(string $file, string $ticketId, string $operatorId, string $taskType): void {
    $lastPing = microtime(true);
    while (true) {
        if (connection_aborted()) {
            purgeOperatorTickets($file, $operatorId);
            exit;
        }

        $allowed   = false;
        $cancelled = false;
        $turnPos   = 1;

        mutateTelemetryState($file, function (&$state, $now) use ($ticketId, $taskType, &$allowed, &$cancelled, &$turnPos) {
            if (!isset($state['queue'][$ticketId])) {
                $cancelled = true;
                return $state;
            }

            $state['queue'][$ticketId]['updated_at'] = $now;
            uasort($state['queue'], fn($a, $b) => ($a['created_at'] <=> $b['created_at']));
            $keys    = array_keys($state['queue']);
            $turnPos = (int)array_search($ticketId, $keys, true) + 1;

            if ($turnPos === 1) {
                $state['queue'][$ticketId]['status']     = 'processing';
                $state['queue'][$ticketId]['task']       = $taskType;
                $state['queue'][$ticketId]['started_at'] = $state['queue'][$ticketId]['started_at'] ?? $now;
                $allowed = true;
            }
            return $state;
        });

        if ($cancelled) {
            sendSafeJson(['type' => 'error', 'ok' => false, 'error' => 'Tu turno fue cancelado o la sesión se cerró.'], 409);
        }
        if ($allowed) {
            break;
        }

        if ((microtime(true) - $lastPing) >= 2.5) {
            $lastPing = microtime(true);
            emitStreamLine(['type' => 'ping', 'turn' => $turnPos, 'phase' => "Esperando liberación de turno (#{$turnPos})..."]);
        }
        usleep(300000);
    }
}

// ============================================================
// 5. GESTOR DE 6GB VRAM Y DIAGNÓSTICO DE CONTENEDORES DOCKER
// ============================================================
function getOllamaLoadedModels(string $apiPsUrl): array {
    $ch = curl_init($apiPsUrl);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 2,
        CURLOPT_TIMEOUT        => 4
    ]);
    $raw      = curl_exec($ch);
    $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    $loaded = [];
    if ($raw !== false && $httpCode === 200) {
        $data = json_decode((string)$raw, true);
        if (isset($data['models']) && is_array($data['models'])) {
            foreach ($data['models'] as $m) {
                if (!empty($m['name'])) {
                    $sizeVram = (int)($m['size_vram'] ?? $m['size'] ?? 0);
                    $loaded[] = [
                        'name'    => (string)$m['name'],
                        'vram_gb' => $sizeVram > 0 ? round($sizeVram / (1024 * 1024 * 1024), 2) : 0
                    ];
                }
            }
        }
    }
    return $loaded;
}

function unloadAllOllamaModelsFromVram(string $apiPsUrl, string $apiGenUrl, string $fallbackModel = ''): array {
    $loaded = getOllamaLoadedModels($apiPsUrl);
    $names  = array_column($loaded, 'name');
    if ($fallbackModel !== '' && !in_array($fallbackModel, $names, true)) {
        $names[] = $fallbackModel;
    }

    $unloaded = [];
    foreach ($names as $modelName) {
        $ch = curl_init($apiGenUrl);
        curl_setopt_array($ch, [
            CURLOPT_POST           => true,
            CURLOPT_POSTFIELDS     => json_encode(['model' => $modelName, 'keep_alive' => 0]),
            CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 3,
            CURLOPT_TIMEOUT        => 10
        ]);
        curl_exec($ch);
        curl_close($ch);
        $unloaded[] = $modelName;
    }
    return $unloaded;
}

function checkDockerPort(string $ip, int $port, float $timeoutSec = 1.2): array {
    $t0  = microtime(true);
    $fp  = @fsockopen($ip, $port, $errno, $errstr, $timeoutSec);
    $ms  = round((microtime(true) - $t0) * 1000);
    if ($fp) {
        fclose($fp);
        return ['online' => true, 'ms' => $ms];
    }
    return ['online' => false, 'ms' => null];
}

// ============================================================
// 6. SISTEMA DE LOGIN Y EVACUACIÓN DE TURNO AL SALIR
// ============================================================
$current_url = strtok($_SERVER["REQUEST_URI"] ?? '/', '?');

if (empty($_SESSION['operator_id'])) {
    $_SESSION['operator_id'] = 'op_' . bin2hex(random_bytes(8));
}
if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

$operator_id = (string)$_SESSION['operator_id'];
$csrf_token  = (string)$_SESSION['csrf_token'];

if (isset($_GET['salir'])) {
    purgeOperatorTickets($TELEMETRY_FILE, $operator_id);
    $_SESSION = [];
    session_destroy();
    while (ob_get_level() > 0) {
        @ob_end_clean();
    }
    header("Location: " . $current_url);
    exit;
}

$error_msg = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['password']) && !$IS_API_REQUEST) {
    $intentos = (int)($_SESSION['login_attempts'] ?? 0);
    $bloqueo  = (int)($_SESSION['lockout_time'] ?? 0);

    if ($intentos >= 5 && (time() - $bloqueo) < 60) {
        $restante  = 60 - (time() - $bloqueo);
        $error_msg = "Demasiados intentos. Espera {$restante} segundos.";
    } elseif (hash_equals($PASSWORD_SECRETA, (string)$_POST['password'])) {
        session_regenerate_id(true);
        $_SESSION['logeado']        = true;
        $_SESSION['login_attempts'] = 0;
        $_SESSION['operator_id']    = 'op_' . bin2hex(random_bytes(8));
        $_SESSION['csrf_token']     = bin2hex(random_bytes(32));
        while (ob_get_level() > 0) {
            @ob_end_clean();
        }
        header("Location: " . $current_url);
        exit;
    } else {
        $_SESSION['login_attempts'] = $intentos + 1;
        $_SESSION['lockout_time']   = time();
        $error_msg = "Contraseña incorrecta.";
    }
}

$autenticado = isset($_SESSION['logeado']) && $_SESSION['logeado'] === true;

// Liberar sesión de PHP inmediatamente para permitir llamadas paralelas sin bloqueo
session_write_close();

// ============================================================
// 7. CONTROLADOR DE ENDPOINTS API
// ============================================================
if ($IS_API_REQUEST) {
    if (!$autenticado) {
        sendSafeJson(['ok' => false, 'error' => 'Sesión cerrada o expirada. Inicia sesión nuevamente.'], 401);
    }

    $action = (string)$_GET['action'];

    // 7.1 TELEMETRÍA Y ESTADO DE TURNO (GET)
    if ($action === 'telemetry') {
        $ticketId = preg_replace('/[^a-zA-Z0-9_\-]/', '', (string)($_GET['ticket'] ?? ''));
        $snap     = buildTelemetrySnapshot($TELEMETRY_FILE, $ticketId);
        if (isset($_GET['include_vram'])) {
            $snap['vram_models'] = getOllamaLoadedModels($API_OLLAMA_PS);
        }
        sendSafeJson($snap);
    }

    // 7.2 DIAGNÓSTICO DE SALUD DE CONTENEDORES DOCKER (GET)
    if ($action === 'health') {
        sendSafeJson([
            'ok'       => true,
            'services' => [
                'stt'    => checkDockerPort($DOCKER_IP, 8000),
                'ollama' => checkDockerPort($DOCKER_IP, 11434),
                'tts'    => checkDockerPort($DOCKER_IP, 5050),
                'sd'     => checkDockerPort($DOCKER_IP, 7860)
            ],
            'vram_models' => getOllamaLoadedModels($API_OLLAMA_PS)
        ]);
    }

    // 7.3 LISTADO DINÁMICO DE MODELOS OLLAMA (GET)
    if ($action === 'models') {
        $ch = curl_init($API_OLLAMA_TAGS);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_CONNECTTIMEOUT => 3,
            CURLOPT_TIMEOUT        => 7
        ]);
        $raw      = curl_exec($ch);
        $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $models = [];
        if ($raw !== false && $httpCode === 200) {
            $decoded = json_decode((string)$raw, true);
            if (is_array($decoded) && isset($decoded['models']) && is_array($decoded['models'])) {
                foreach ($decoded['models'] as $m) {
                    $name      = (string)($m['name'] ?? '');
                    $sizeBytes = (int)($m['size'] ?? 0);
                    $sizeGb    = $sizeBytes > 0 ? round($sizeBytes / (1024 * 1024 * 1024), 1) . ' GB' : '';
                    $quant     = (string)($m['details']['quantization_level'] ?? '');
                    $paramSize = (string)($m['details']['parameter_size'] ?? '');
                    $metaParts = array_filter([$paramSize, $quant, $sizeGb]);
                    if ($name !== '') {
                        $models[] = [
                            'name'  => $name,
                            'label' => $name . (!empty($metaParts) ? ' (' . implode(' • ', $metaParts) . ')' : '')
                        ];
                    }
                }
            }
        }

        $foundDefault = false;
        foreach ($models as $m) {
            if ($m['name'] === $DEFAULT_OLLAMA_MODEL) {
                $foundDefault = true;
                break;
            }
        }
        if (!$foundDefault) {
            array_unshift($models, [
                'name'  => $DEFAULT_OLLAMA_MODEL,
                'label' => $DEFAULT_OLLAMA_MODEL . ' (Predeterminado)'
            ]);
        }

        sendSafeJson([
            'ok'            => true,
            'default_model' => $DEFAULT_OLLAMA_MODEL,
            'models'        => $models,
            'vram_models'   => getOllamaLoadedModels($API_OLLAMA_PS),
            'online'        => ($raw !== false && $httpCode === 200)
        ]);
    }

    // 7.4 SALIR DE LA COLA / CANCELAR TURNO (POST o Beacon)
    if ($action === 'leave_queue') {
        $ticketId = preg_replace('/[^a-zA-Z0-9_\-]/', '', (string)($_GET['ticket'] ?? $_POST['ticket'] ?? ''));
        mutateTelemetryState($TELEMETRY_FILE, function (&$state, $now) use ($ticketId, $operator_id) {
            if ($ticketId !== '' && isset($state['queue'][$ticketId])) {
                unset($state['queue'][$ticketId]);
            } else {
                foreach ($state['queue'] as $id => $item) {
                    if (($item['operator_id'] ?? '') === $operator_id) {
                        unset($state['queue'][$id]);
                    }
                }
            }
            uasort($state['queue'], fn($a, $b) => ($a['created_at'] <=> $b['created_at']));
            $firstKey = array_key_first($state['queue']);
            if ($firstKey !== null && $state['queue'][$firstKey]['status'] === 'queued') {
                $state['queue'][$firstKey]['status']      = 'ready';
                $state['queue'][$firstKey]['promoted_at'] = $now;
            }
            return $state;
        });
        sendSafeJson(['ok' => true, 'message' => 'Turno liberado correctamente.']);
    }

    // Validar CSRF para todas las peticiones POST
    $headerCsrf = (string)($_SERVER['HTTP_X_CSRF_TOKEN'] ?? '');
    if (!hash_equals($csrf_token, $headerCsrf)) {
        sendSafeJson(['ok' => false, 'error' => 'Token CSRF inválido. Recarga la página.'], 403);
    }

    // 7.5 LIBERAR 6GB DE VRAM EN OLLAMA (keep_alive: 0)
    if ($action === 'free_vram') {
        $input    = json_decode((string)file_get_contents('php://input'), true) ?: [];
        $fallback = trim((string)($input['model'] ?? $DEFAULT_OLLAMA_MODEL));
        $unloaded = unloadAllOllamaModelsFromVram($API_OLLAMA_PS, $API_OLLAMA_GEN, $fallback);
        sendSafeJson([
            'ok'          => true,
            'unloaded'    => $unloaded,
            'vram_models' => getOllamaLoadedModels($API_OLLAMA_PS),
            'message'     => 'Memoria VRAM de Ollama liberada (keep_alive: 0).'
        ]);
    }

    // 7.6 SOLICITAR TURNO EN LA COLA FIFO (POST ?action=enqueue)
    if ($action === 'enqueue') {
        $input = json_decode((string)file_get_contents('php://input'), true) ?: [];
        $task  = (string)($input['task'] ?? 'ollama');
        if (!in_array($task, ['stt', 'ollama', 'tts', 'sd'], true)) {
            $task = 'ollama';
        }
        $ticketId = 'tk_' . bin2hex(random_bytes(6));

        mutateTelemetryState($TELEMETRY_FILE, function (&$state, $now) use ($ticketId, $operator_id, $task) {
            $isEmpty = empty($state['queue']);
            $state['queue'][$ticketId] = [
                'id'          => $ticketId,
                'operator_id' => $operator_id,
                'task'        => $task,
                'status'      => $isEmpty ? 'ready' : 'queued',
                'created_at'  => $now,
                'started_at'  => null,
                'updated_at'  => $now
            ];
            return $state;
        });

        sendSafeJson(buildTelemetrySnapshot($TELEMETRY_FILE, $ticketId));
    }

    // Validar Ticket ID para ejecución en GPU
    $ticketId = preg_replace('/[^a-zA-Z0-9_\-]/', '', (string)($_SERVER['HTTP_X_TICKET_ID'] ?? ''));
    if ($ticketId === '') {
        sendSafeJson(['ok' => false, 'error' => 'Falta identificador de turno (Ticket ID).'], 400);
    }

    /**
     * Callback cURL Anti-524:
     * Mantiene vivo el turno en el servidor, aborta cURL si el usuario canceló/salió,
     * y emite un paquete NDJSON cada 3 segundos para evitar el timeout 524 de Cloudflare.
     */
    $makeAnti524ProgressCallback = function (string $phaseText, float $t0, float &$lastOutputTime) use ($TELEMETRY_FILE, $ticketId): Closure {
        $lastTicketTouch = 0.0;
        return function ($resource, $dlTotal = 0, $dlNow = 0, $ulTotal = 0, $ulNow = 0) use ($TELEMETRY_FILE, $ticketId, $phaseText, $t0, &$lastOutputTime, &$lastTicketTouch): int {
            if (connection_aborted()) {
                return 1;
            }
            $now = microtime(true);

            if (($now - $lastTicketTouch) >= 1.2) {
                $lastTicketTouch = $now;
                if (!touchAndCheckTicket($TELEMETRY_FILE, $ticketId)) {
                    return 1; // Turno cancelado o sesión cerrada -> abortar cURL
                }
            }

            if (($now - $lastOutputTime) >= 3.0) {
                $lastOutputTime = $now;
                emitStreamLine([
                    'type'       => 'ping',
                    'phase'      => $phaseText,
                    'elapsed_ms' => round(($now - $t0) * 1000)
                ]);
            }
            return 0;
        };
    };

    // 7.7 EJECUCIÓN STT: WHISPER (Con Canal Anti-524)
    if ($action === 'stt') {
        if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
            finishTicketAndRecordMetric($TELEMETRY_FILE, $ticketId, 'stt', 0);
            sendSafeJson(['ok' => false, 'error' => 'No se recibió un archivo de audio válido.'], 400);
        }

        openAnti524Stream($ticketId, 'Iniciando transcripción en Whisper STT...');
        lockServerTurnForExecution($TELEMETRY_FILE, $ticketId, $operator_id, 'stt');

        $t0             = microtime(true);
        $lastOutputTime = $t0;

        $cfile = new CURLFile(
            $_FILES['file']['tmp_name'],
            $_FILES['file']['type'] ?: 'audio/webm',
            $_FILES['file']['name'] ?: 'voice.webm'
        );

        $ch = curl_init($API_STT);
        curl_setopt_array($ch, [
            CURLOPT_POST             => true,
            CURLOPT_POSTFIELDS       => ['file' => $cfile],
            CURLOPT_RETURNTRANSFER   => true,
            CURLOPT_CONNECTTIMEOUT   => 0,
            CURLOPT_TIMEOUT          => 0,
            CURLOPT_NOPROGRESS       => false,
            CURLOPT_PROGRESSFUNCTION => $makeAnti524ProgressCallback('Transcribiendo voz en Whisper STT...', $t0, $lastOutputTime)
        ]);

        $response = curl_exec($ch);
        $curlErr  = curl_error($ch);
        $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $durationMs = (microtime(true) - $t0) * 1000.0;
        finishTicketAndRecordMetric($TELEMETRY_FILE, $ticketId, 'stt', $durationMs);

        if ($response === false || $httpCode !== 200) {
            sendSafeJson([
                'type'  => 'error',
                'ok'    => false,
                'error' => "Error en Whisper STT (HTTP {$httpCode})" . ($curlErr ? ": {$curlErr}" : '')
            ]);
        }

        $decoded = json_decode((string)$response, true);
        if (!is_array($decoded)) {
            sendSafeJson([
                'type'  => 'error',
                'ok'    => false,
                'error' => 'Whisper devolvió una respuesta inválida: ' . mb_substr(strip_tags((string)$response), 0, 160)
            ]);
        }

        sendSafeJson([
            'type'        => 'result',
            'ok'          => true,
            'text'        => (string)($decoded['text'] ?? ''),
            'duration_ms' => round($durationMs)
        ]);
    }

    // 7.8 EJECUCIÓN LLM: OLLAMA (Streaming NDJSON Blindado Anti-524 + System Prompt + Opciones VRAM)
    if ($action === 'ollama') {
        $input        = json_decode((string)file_get_contents('php://input'), true) ?: [];
        $prompt       = trim((string)($input['prompt'] ?? ''));
        $systemPrompt = trim((string)($input['system'] ?? ''));
        $model        = trim((string)($input['model'] ?? $DEFAULT_OLLAMA_MODEL));
        $useStream    = (bool)($input['stream'] ?? true);
        $temperature  = max(0.0, min(1.5, (float)($input['temperature'] ?? 0.7)));
        $numCtx       = max(512, min(8192, (int)($input['num_ctx'] ?? 2048)));

        if ($model === '') {
            $model = $DEFAULT_OLLAMA_MODEL;
        }
        if ($prompt === '') {
            finishTicketAndRecordMetric($TELEMETRY_FILE, $ticketId, 'ollama', 0);
            sendSafeJson(['ok' => false, 'error' => 'El prompt para Ollama está vacío.'], 400);
        }

        openAnti524Stream($ticketId, "Cargando {$model} en VRAM/RAM...");
        lockServerTurnForExecution($TELEMETRY_FILE, $ticketId, $operator_id, 'ollama');

        $t0             = microtime(true);
        $lastOutputTime = $t0;
        $lineBuffer     = '';

        $reqBody = [
            'model'      => $model,
            'prompt'     => $prompt,
            'stream'     => $useStream,
            'keep_alive' => '15m',
            'options'    => [
                'temperature' => $temperature,
                'num_ctx'     => $numCtx
            ]
        ];
        if ($systemPrompt !== '') {
            $reqBody['system'] = $systemPrompt;
        }
        $payload = json_encode($reqBody, JSON_UNESCAPED_UNICODE);

        if ($useStream) {
            $ch = curl_init($API_OLLAMA_GEN);
            curl_setopt_array($ch, [
                CURLOPT_POST             => true,
                CURLOPT_POSTFIELDS       => $payload,
                CURLOPT_HTTPHEADER       => ['Content-Type: application/json'],
                CURLOPT_RETURNTRANSFER   => false,
                CURLOPT_CONNECTTIMEOUT   => 0,
                CURLOPT_TIMEOUT          => 0,
                CURLOPT_NOPROGRESS       => false,
                CURLOPT_PROGRESSFUNCTION => $makeAnti524ProgressCallback("Cargando {$model} en 6GB VRAM / 32GB RAM...", $t0, $lastOutputTime),
                CURLOPT_WRITEFUNCTION    => function ($ch, string $chunk) use (&$lineBuffer, &$lastOutputTime): int {
                    $lineBuffer .= $chunk;
                    while (($pos = strpos($lineBuffer, "\n")) !== false) {
                        $completeLine = trim(substr($lineBuffer, 0, $pos));
                        $lineBuffer   = substr($lineBuffer, $pos + 1);
                        if ($completeLine !== '') {
                            echo $completeLine . "\n";
                            if (ob_get_level() > 0) {
                                @ob_flush();
                            }
                            flush();
                            $lastOutputTime = microtime(true);
                        }
                    }
                    return strlen($chunk);
                }
            ]);

            $ok       = curl_exec($ch);
            $curlErr  = curl_error($ch);
            $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
            curl_close($ch);

            $rem = trim($lineBuffer);
            if ($rem !== '') {
                echo $rem . "\n";
            }

            $durationMs = (microtime(true) - $t0) * 1000.0;
            finishTicketAndRecordMetric($TELEMETRY_FILE, $ticketId, 'ollama', $durationMs);

            if ($ok === false || ($httpCode !== 200 && $httpCode !== 0)) {
                sendSafeJson([
                    'type'  => 'error',
                    'ok'    => false,
                    'error' => "Error en Ollama (HTTP {$httpCode})" . ($curlErr ? ": {$curlErr}" : '')
                ]);
            }

            sendSafeJson([
                'type'        => 'done',
                'ok'          => true,
                'done'        => true,
                'duration_ms' => round($durationMs)
            ]);
        }

        // Modo sin streaming (protegido con latidos Anti-524)
        $ch = curl_init($API_OLLAMA_GEN);
        curl_setopt_array($ch, [
            CURLOPT_POST             => true,
            CURLOPT_POSTFIELDS       => $payload,
            CURLOPT_HTTPHEADER       => ['Content-Type: application/json'],
            CURLOPT_RETURNTRANSFER   => true,
            CURLOPT_CONNECTTIMEOUT   => 0,
            CURLOPT_TIMEOUT          => 0,
            CURLOPT_NOPROGRESS       => false,
            CURLOPT_PROGRESSFUNCTION => $makeAnti524ProgressCallback("Generando respuesta completa con {$model}...", $t0, $lastOutputTime)
        ]);

        $response = curl_exec($ch);
        $curlErr  = curl_error($ch);
        $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $durationMs = (microtime(true) - $t0) * 1000.0;
        finishTicketAndRecordMetric($TELEMETRY_FILE, $ticketId, 'ollama', $durationMs);

        if ($response === false || $httpCode !== 200) {
            sendSafeJson([
                'type'  => 'error',
                'ok'    => false,
                'error' => "Error en Ollama (HTTP {$httpCode})" . ($curlErr ? ": {$curlErr}" : '')
            ]);
        }

        $decoded = json_decode((string)$response, true);
        if (!is_array($decoded)) {
            sendSafeJson([
                'type'  => 'error',
                'ok'    => false,
                'error' => 'Ollama devolvió una respuesta inválida.'
            ]);
        }

        $decoded['type']        = 'result';
        $decoded['ok']          = true;
        $decoded['duration_ms'] = round($durationMs);
        sendSafeJson($decoded);
    }

    // 7.9 EJECUCIÓN TTS: TEXTO A VOZ (Con Canal Anti-524)
    if ($action === 'tts') {
        $input = json_decode((string)file_get_contents('php://input'), true) ?: [];
        $text  = trim((string)($input['text'] ?? ''));

        if ($text === '') {
            finishTicketAndRecordMetric($TELEMETRY_FILE, $ticketId, 'tts', 0);
            sendSafeJson(['ok' => false, 'error' => 'No hay texto para sintetizar en voz.'], 400);
        }

        openAnti524Stream($ticketId, 'Sintetizando voz en motor TTS...');
        lockServerTurnForExecution($TELEMETRY_FILE, $ticketId, $operator_id, 'tts');

        $t0             = microtime(true);
        $lastOutputTime = $t0;

        $ch = curl_init($API_TTS);
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER   => true,
            CURLOPT_POST             => true,
            CURLOPT_HTTPHEADER       => ['Content-Type: application/json'],
            CURLOPT_POSTFIELDS       => json_encode(['texto' => $text], JSON_UNESCAPED_UNICODE),
            CURLOPT_CONNECTTIMEOUT   => 0,
            CURLOPT_TIMEOUT          => 0,
            CURLOPT_NOPROGRESS       => false,
            CURLOPT_PROGRESSFUNCTION => $makeAnti524ProgressCallback('Generando audio WAV en motor TTS...', $t0, $lastOutputTime)
        ]);

        $audioData = curl_exec($ch);
        $curlErr   = curl_error($ch);
        $httpCode  = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $durationMs = (microtime(true) - $t0) * 1000.0;
        finishTicketAndRecordMetric($TELEMETRY_FILE, $ticketId, 'tts', $durationMs);

        if ($httpCode === 200 && $audioData !== false && strlen((string)$audioData) > 64) {
            sendSafeJson([
                'type'         => 'result',
                'ok'           => true,
                'audio_base64' => base64_encode((string)$audioData),
                'duration_ms'  => round($durationMs)
            ]);
        }

        sendSafeJson([
            'type'  => 'error',
            'ok'    => false,
            'error' => "Error HTTP {$httpCode} en motor TTS" . ($curlErr ? ": {$curlErr}" : '')
        ]);
    }

    // 7.10 EJECUCIÓN SD: STABLE DIFFUSION (Con Traductor IA a Inglés + Liberación 6GB VRAM + Anti-524)
    if ($action === 'sd') {
        $input          = json_decode((string)file_get_contents('php://input'), true) ?: [];
        $rawPrompt      = trim((string)($input['prompt'] ?? ''));
        $negativePrompt = trim((string)($input['negative_prompt'] ?? 'blurry, low quality, bad anatomy, deformed, ugly, watermark, text, signature, cropped'));
        $steps          = max(10, min(50, (int)($input['steps'] ?? 20)));
        $cfgScale       = max(1.0, min(20.0, (float)($input['cfg_scale'] ?? 7.0)));
        $width          = max(256, min(1024, (int)($input['width'] ?? 512)));
        $height         = max(256, min(1024, (int)($input['height'] ?? 512)));
        $autoUnload     = (bool)($input['free_vram'] ?? true);
        $optimizePrompt = (bool)($input['optimize_prompt'] ?? true);
        $lastModel      = trim((string)($input['model'] ?? $DEFAULT_OLLAMA_MODEL));

        if ($rawPrompt === '') {
            finishTicketAndRecordMetric($TELEMETRY_FILE, $ticketId, 'sd', 0);
            sendSafeJson(['ok' => false, 'error' => 'El prompt para Stable Diffusion está vacío.'], 400);
        }

        openAnti524Stream($ticketId, 'Preparando pipeline de Stable Diffusion...');
        lockServerTurnForExecution($TELEMETRY_FILE, $ticketId, $operator_id, 'sd');

        $t0             = microtime(true);
        $lastOutputTime = $t0;
        $finalSdPrompt  = $rawPrompt;

        // PASO A: Si está activado el Ingeniero de Prompts IA, traducimos/optimizamos a inglés con Ollama
        // y al mismo tiempo le enviamos keep_alive: 0 si autoUnload está activo para liberar los 6GB de VRAM en un solo paso.
        if ($optimizePrompt) {
            emitStreamLine([
                'type'  => 'ping',
                'phase' => 'Traduciendo y optimizando prompt visual al inglés con Ollama...'
            ]);

            $engineerInstruction = "Convert the following text into a vivid, high-detail English image generation prompt for Stable Diffusion. Include visual descriptors, lighting, atmosphere, camera angle, and quality tags (masterpiece, best quality, highly detailed, 8k). Output ONLY the English prompt without quotes or explanations:\n\n" . mb_substr($rawPrompt, 0, 900);

            $optPayload = json_encode([
                'model'      => $lastModel ?: $DEFAULT_OLLAMA_MODEL,
                'prompt'     => $engineerInstruction,
                'stream'     => false,
                'keep_alive' => $autoUnload ? 0 : '5m',
                'options'    => ['temperature' => 0.5, 'num_ctx' => 1024]
            ], JSON_UNESCAPED_UNICODE);

            $chOpt = curl_init($API_OLLAMA_GEN);
            curl_setopt_array($chOpt, [
                CURLOPT_POST             => true,
                CURLOPT_POSTFIELDS       => $optPayload,
                CURLOPT_HTTPHEADER       => ['Content-Type: application/json'],
                CURLOPT_RETURNTRANSFER   => true,
                CURLOPT_CONNECTTIMEOUT   => 0,
                CURLOPT_TIMEOUT          => 0,
                CURLOPT_NOPROGRESS       => false,
                CURLOPT_PROGRESSFUNCTION => $makeAnti524ProgressCallback('Traduciendo prompt a inglés con Ollama...', $t0, $lastOutputTime)
            ]);
            $optRaw  = curl_exec($chOpt);
            $optCode = (int)curl_getinfo($chOpt, CURLINFO_HTTP_CODE);
            curl_close($chOpt);

            if ($optRaw !== false && $optCode === 200) {
                $optDec = json_decode((string)$optRaw, true);
                if (!empty($optDec['response'])) {
                    $cleanedPrompt = trim((string)$optDec['response'], " \t\n\r\0\x0B\"'");
                    if ($cleanedPrompt !== '') {
                        $finalSdPrompt = $cleanedPrompt;
                        emitStreamLine([
                            'type'      => 'sd_prompt',
                            'sd_prompt' => $finalSdPrompt
                        ]);
                    }
                }
            }
        }

        // PASO B: Asegurar que los 6GB de VRAM queden libres de cualquier otro modelo de Ollama
        if ($autoUnload) {
            emitStreamLine([
                'type'  => 'ping',
                'phase' => 'Liberando 6GB VRAM de Ollama (keep_alive: 0) para Stable Diffusion...'
            ]);
            unloadAllOllamaModelsFromVram($API_OLLAMA_PS, $API_OLLAMA_GEN, $lastModel);
        }

        // PASO C: Renderizar en Stable Diffusion
        emitStreamLine([
            'type'  => 'ping',
            'phase' => "Renderizando en GPU ({$width}x{$height} • {$steps} pasos)..."
        ]);

        $sdPayload = json_encode([
            'prompt'          => $finalSdPrompt,
            'negative_prompt' => $negativePrompt,
            'steps'           => $steps,
            'cfg_scale'       => $cfgScale,
            'width'           => $width,
            'height'          => $height
        ], JSON_UNESCAPED_UNICODE);

        $ch = curl_init($API_SD);
        curl_setopt_array($ch, [
            CURLOPT_POST             => true,
            CURLOPT_POSTFIELDS       => $sdPayload,
            CURLOPT_HTTPHEADER       => ['Content-Type: application/json', 'Accept: application/json'],
            CURLOPT_RETURNTRANSFER   => true,
            CURLOPT_CONNECTTIMEOUT   => 0,
            CURLOPT_TIMEOUT          => 0,
            CURLOPT_NOPROGRESS       => false,
            CURLOPT_PROGRESSFUNCTION => $makeAnti524ProgressCallback("Renderizando imagen en GPU ({$width}x{$height}, {$steps} pasos)...", $t0, $lastOutputTime)
        ]);

        $response = curl_exec($ch);
        $curlErr  = curl_error($ch);
        $httpCode = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        $durationMs = (microtime(true) - $t0) * 1000.0;
        finishTicketAndRecordMetric($TELEMETRY_FILE, $ticketId, 'sd', $durationMs);

        if ($response === false || $httpCode !== 200) {
            sendSafeJson([
                'type'  => 'error',
                'ok'    => false,
                'error' => "Error en Stable Diffusion (HTTP {$httpCode})" . ($curlErr ? ": {$curlErr}" : '')
            ]);
        }

        $decoded = json_decode((string)$response, true);
        if (!is_array($decoded) || empty($decoded['images'][0])) {
            sendSafeJson([
                'type'  => 'error',
                'ok'    => false,
                'error' => 'Stable Diffusion no devolvió una imagen válida.'
            ]);
        }

        sendSafeJson([
            'type'        => 'result',
            'ok'          => true,
            'images'      => [$decoded['images'][0]],
            'sd_prompt'   => $finalSdPrompt,
            'duration_ms' => round($durationMs)
        ]);
    }

    sendSafeJson(['ok' => false, 'error' => 'Acción desconocida.'], 400);
}

// ============================================================
// 8. INTERFAZ DE VOZ (archivo compartido aryi_ui.php)
// ============================================================
$UI_LOGOUT     = '?salir=true';
$UI_USER       = null;
$UI_ARCHIVADOR = null;
require __DIR__ . '/aryi_ui.php';
