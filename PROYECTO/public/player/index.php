<?php
declare(strict_types=1);
session_start();

if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id']) || empty($_SESSION['hash_verificado'])) {
    header('Location: ../InicioDeSesion/verificar.php');
    exit;
}

/* ============================================================
 * SYNTAX SANCTUARY — MEDIA CENTER (MVP DEFINITIVO)
 * Monolito PHP: Catálogo + Autenticación + YouTube (Shorts inc.) / Local
 * ============================================================ */

// 1. Configuración Principal
const ADMIN_PASSWORD = 'ss-tfh-free'; 
const DATA_FILE = __DIR__ . '/videos_data.json';
const UPLOAD_DIR = __DIR__ . '/uploads_videos';
const MAX_VIDEO_BYTES = 1000 * 1024 * 1024; // 1000 MB (1 GB)
const CSRF_KEY = 'media_csrf';

/* ------------------------------------------------------------
 * Seguridad y Sesiones
 * ------------------------------------------------------------ */
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: SAMEORIGIN');

/*session_set_cookie_params([
    'lifetime' => 0,
    'path' => '/',
    'httponly' => true,
    'samesite' => 'Strict',
]);*/

if (session_status() !== PHP_SESSION_ACTIVE) {
    session_start();
}

/* ------------------------------------------------------------
 * Utilidades Core
 * ------------------------------------------------------------ */
function e(string $value): string {
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function jsonResponse(array $data, int $status = 200): never {
    http_response_code($status);
    header('Content-Type: application/json; charset=UTF-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function ensureStorage(): void {
    if (!is_dir(UPLOAD_DIR) && !mkdir(UPLOAD_DIR, 0755, true)) {
        throw new RuntimeException('No se pudo crear el directorio de vídeos.');
    }
    if (!file_exists(DATA_FILE)) {
        atomicWriteJson([]);
    }
}

function loadVideos(): array {
    if (!is_file(DATA_FILE)) return [];
    $raw = file_get_contents(DATA_FILE);
    if ($raw === false || trim($raw) === '') return [];
    $data = json_decode($raw, true);
    return is_array($data) ? array_values($data) : [];
}

function atomicWriteJson(array $videos): void {
    $encoded = json_encode(array_values($videos), JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE);
    if ($encoded === false) throw new RuntimeException('Error serializando catálogo.');
    
    $tmp = DATA_FILE . '.tmp.' . bin2hex(random_bytes(8));
    if (file_put_contents($tmp, $encoded, LOCK_EX) === false) {
        throw new RuntimeException('Error escribiendo catálogo temporal.');
    }
    if (!rename($tmp, DATA_FILE)) {
        @unlink($tmp);
        throw new RuntimeException('Error reemplazando el catálogo.');
    }
}

function isAdmin(): bool {
    return !empty($_SESSION['admin_authenticated']);
}

function requireAdmin(): void {
    if (!isAdmin()) jsonResponse(['ok' => false, 'message' => 'Sesión requerida.'], 401);
}

function csrfToken(): string {
    if (empty($_SESSION[CSRF_KEY])) $_SESSION[CSRF_KEY] = bin2hex(random_bytes(32));
    return (string)$_SESSION[CSRF_KEY];
}

function requireCsrf(): void {
    $token = $_POST['csrf'] ?? '';
    if (!hash_equals((string)($_SESSION[CSRF_KEY] ?? ''), $token)) {
        jsonResponse(['ok' => false, 'message' => 'Token CSRF inválido.'], 419);
    }
}

// Regex actualizada para soportar Shorts, Live, Watch y YouTu.be
function getYoutubeId(string $url): ?string {
    preg_match('%(?:youtube(?:-nocookie)?\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)/|.*[?&]v=|shorts/|live/)|youtu\.be/)([^"&?/\s]{11})%i', $url, $match);
    return $match[1] ?? null;
}

/* ------------------------------------------------------------
 * Controlador API (AJAX POST)
 * ------------------------------------------------------------ */
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    try {
        ensureStorage();
        $videos = loadVideos();
        $action = $_POST['action'] ?? '';

        switch ($action) {
            case 'login':
                $password = (string)($_POST['password'] ?? '');
                if ($password === ADMIN_PASSWORD) {
                    session_regenerate_id(true);
                    $_SESSION['admin_authenticated'] = true;
                    $_SESSION[CSRF_KEY] = bin2hex(random_bytes(32));
                    jsonResponse(['ok' => true, 'csrf' => csrfToken()]);
                } else {
                    jsonResponse(['ok' => false, 'message' => 'Contraseña incorrecta.'], 401);
                }
                break;

            case 'logout':
                requireAdmin();
                requireCsrf();
                $_SESSION = [];
                session_destroy();
                jsonResponse(['ok' => true]);
                break;

            case 'upload_video':
                requireAdmin();
                requireCsrf();

                $titulo = trim($_POST['titulo'] ?? '');
                $descripcion = trim($_POST['descripcion'] ?? '');
                $tipo_medio = $_POST['tipo_medio'] ?? 'local';

                if ($titulo === '') jsonResponse(['ok' => false, 'message' => 'El título es obligatorio.'], 422);
                
                if ($tipo_medio === 'youtube') {
                    // Lógica para enlaces de YouTube
                    $yt_url = trim($_POST['youtube_url'] ?? '');
                    if ($yt_url === '') jsonResponse(['ok' => false, 'message' => 'El enlace de YouTube es obligatorio.'], 422);
                    
                    $yt_id = getYoutubeId($yt_url);
                    if (!$yt_id) jsonResponse(['ok' => false, 'message' => 'Enlace de YouTube no válido. Verifica la URL.'], 422);

                    $nuevo_video = [
                        'id' => 'vid-' . time() . rand(100,999),
                        'tipo' => 'youtube',
                        'titulo' => $titulo,
                        'descripcion' => $descripcion,
                        'url' => $yt_id,
                        'fecha' => date('Y-m-d')
                    ];

                } else {
                    // Lógica para archivos locales
                    if (!isset($_FILES['archivo_video'])) {
                        jsonResponse(['ok' => false, 'message' => 'PHP no recibió el archivo. Límite post_max_size superado.'], 422);
                    }

                    $error_code = $_FILES['archivo_video']['error'];
                    if ($error_code !== UPLOAD_ERR_OK) {
                        $errores = [
                            1 => 'El archivo supera "upload_max_filesize" en tu php.ini',
                            2 => 'El archivo supera el límite HTML',
                            3 => 'La subida se cortó a la mitad',
                            4 => 'No se seleccionó ningún archivo',
                            6 => 'Falta la carpeta temporal en Linux',
                            7 => 'Fallo de permisos al escribir en disco',
                            8 => 'Una extensión de PHP bloqueó la subida'
                        ];
                        $msg = $errores[$error_code] ?? 'Error desconocido: ' . $error_code;
                        jsonResponse(['ok' => false, 'message' => 'Bloqueo de servidor: ' . $msg], 422);
                    }

                    $file = $_FILES['archivo_video'];
                    if ($file['size'] > MAX_VIDEO_BYTES) {
                        jsonResponse(['ok' => false, 'message' => 'El vídeo supera el límite de 1 GB interno.'], 422);
                    }

                    $finfo = new finfo(FILEINFO_MIME_TYPE);
                    $mime = $finfo->file($file['tmp_name']);
                    
                    $allowed = [
                        'video/mp4' => 'mp4', 
                        'video/webm' => 'webm', 
                        'video/ogg' => 'ogv', 
                        'video/quicktime' => 'mov',
                        'application/octet-stream' => 'mp4' 
                    ];
                    
                    if (!isset($allowed[$mime])) {
                        jsonResponse(['ok' => false, 'message' => 'Formato MIME rechazado por seguridad: ' . $mime], 422);
                    }

                    $filename = bin2hex(random_bytes(16)) . '.' . $allowed[$mime];
                    $target = UPLOAD_DIR . '/' . $filename;

                    if (!move_uploaded_file($file['tmp_name'], $target)) {
                        jsonResponse(['ok' => false, 'message' => 'Error de permisos: PHP no pudo mover el archivo a /uploads_videos'], 500);
                    }

                    $nuevo_video = [
                        'id' => 'vid-' . time() . rand(100,999),
                        'tipo' => 'local',
                        'titulo' => $titulo,
                        'descripcion' => $descripcion,
                        'url' => 'uploads_videos/' . $filename,
                        'fecha' => date('Y-m-d'),
                        'mime' => $mime === 'application/octet-stream' ? 'video/mp4' : $mime
                    ];
                }

                array_unshift($videos, $nuevo_video);
                atomicWriteJson($videos);

                jsonResponse([
                    'ok' => true, 
                    'message' => 'Vídeo añadido correctamente.',
                    'video' => $nuevo_video
                ]);
                break;

            case 'delete_video':
                requireAdmin();
                requireCsrf();

                $id = trim($_POST['id_video'] ?? '');
                $restantes = [];
                $encontrado = false;

                foreach ($videos as $vid) {
                    if ($vid['id'] === $id) {
                        $encontrado = true;
                        // Borramos archivo físico solo si es local
                        $es_local = ($vid['tipo'] ?? 'local') === 'local';
                        if ($es_local && str_starts_with($vid['url'], 'uploads_videos/')) {
                            @unlink(__DIR__ . '/' . $vid['url']);
                        }
                    } else {
                        $restantes[] = $vid;
                    }
                }

                if (!$encontrado) jsonResponse(['ok' => false, 'message' => 'Vídeo no encontrado.'], 404);
                
                atomicWriteJson($restantes);
                jsonResponse(['ok' => true, 'message' => 'Vídeo eliminado correctamente.']);
                break;

            default:
                jsonResponse(['ok' => false, 'message' => 'Acción no válida.'], 400);
        }
    } catch (Throwable $e) {
        jsonResponse(['ok' => false, 'message' => 'Error interno del servidor.'], 500);
    }
}

/* ------------------------------------------------------------
 * Inicialización Vista
 * ------------------------------------------------------------ */
ensureStorage();
$videos = loadVideos();
$videoActual = $videos[0] ?? null;
$loggedIn = isAdmin();
$csrf = csrfToken();

$tipoActual = $videoActual['tipo'] ?? 'local';
$esYoutube = ($tipoActual === 'youtube');
$esLocal = ($tipoActual === 'local');
?>
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="csrf-token" content="<?= e($csrf) ?>">
<title>Media Center | Syntax Sanctuary</title>
<style>
    :root {
        --bg: #09090b;
        --surface: #18181b;
        --surface-hover: #27272a;
        --primary: #00f0ff;
        --text: #f4f4f5;
        --text-muted: #a1a1aa;
        --border: #27272a;
        --danger: #ef4444;
        --success: #22c55e;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
        font-family: system-ui, -apple-system, sans-serif;
        background-color: var(--bg);
        color: var(--text);
        line-height: 1.5;
        padding: 20px;
    }
    .container { max-width: 1280px; margin: 0 auto; }
    
    header {
        margin-bottom: 24px; border-bottom: 1px solid var(--border);
        padding-bottom: 16px; display: flex; justify-content: space-between;
        align-items: center; flex-wrap: wrap; gap: 12px;
    }
    header h1 {
        font-size: 1.8rem; background: linear-gradient(90deg, #fff, var(--primary));
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    
    .btn {
        padding: 10px 16px; border: none; border-radius: 8px;
        font-weight: 700; cursor: pointer; transition: all 0.2s;
    }
    .btn:disabled { opacity: 0.6; cursor: not-allowed; }
    .btn-ghost { background: var(--surface); color: var(--primary); border: 1px solid var(--primary); }
    .btn-ghost:hover { background: var(--primary); color: #000; }
    .btn-primary { background: var(--primary); color: #000; }
    .btn-danger { background: var(--danger); color: #fff; padding: 6px 10px; font-size: 0.8rem; }
    
    .main-layout { display: grid; grid-template-columns: 1fr; gap: 24px; }
    @media (min-width: 900px) { .main-layout { grid-template-columns: 1fr 360px; } }

    /* Player */
    .player-wrapper { background: var(--surface); border-radius: 12px; overflow: hidden; border: 1px solid var(--border); }
    .video-container { width: 100%; background: #000; aspect-ratio: 16 / 9; position: relative; }
    video, iframe { width: 100%; height: 100%; object-fit: contain; border: none; }
    .video-details { padding: 20px; }
    .video-title { font-size: 1.4rem; margin-bottom: 8px; }
    .video-meta { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 12px; display: flex; gap: 10px; align-items: center; }
    .badge { padding: 3px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: bold; background: var(--surface-hover); border: 1px solid var(--border); color: var(--text); text-transform: uppercase; }
    .badge.yt { color: #ff0000; border-color: rgba(255,0,0,0.3); }
    .video-desc { color: var(--text-muted); font-size: 0.95rem; white-space: pre-wrap; }
    .empty { padding: 40px; text-align: center; color: var(--text-muted); width: 100%; position: absolute; top: 50%; transform: translateY(-50%); }

    /* Playlist */
    .playlist-wrapper { background: var(--surface); border-radius: 12px; border: 1px solid var(--border); padding: 16px; display: flex; flex-direction: column; max-height: 650px; }
    .playlist-header { font-size: 1.1rem; font-weight: 700; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); color: var(--primary); }
    .playlist-items { overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
    .playlist-item { padding: 12px; border-radius: 8px; background: var(--bg); border: 1px solid var(--border); cursor: pointer; transition: all 0.2s; }
    .playlist-item:hover, .playlist-item.active { border-color: var(--primary); background: var(--surface-hover); }
    .item-title { display: block; font-weight: 600; font-size: 0.95rem; margin-bottom: 4px; }
    .item-date { display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 8px; }

    /* Paneles Admin */
    .panel { display: none; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; margin-bottom: 24px; }
    .panel.active { display: block; }
    .panel h2 { color: var(--primary); margin-bottom: 16px; font-size: 1.2rem; }
    .form-group { margin-bottom: 14px; display: flex; flex-direction: column; gap: 6px; }
    label { font-size: 0.85rem; color: var(--text-muted); font-weight: 600; }
    input[type="text"], input[type="password"], input[type="file"], input[type="url"], select, textarea { width: 100%; padding: 10px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-family: inherit; }
    input:focus, select:focus, textarea:focus { outline: 1px solid var(--primary); border-color: var(--primary); }
    textarea { resize: vertical; min-height: 80px; }
    
    .admin-only { display: none; }
    body.is-admin .admin-only { display: inline-block; }

    /* Alertas y Progreso */
    .alert { display: none; padding: 12px; border-radius: 8px; margin-bottom: 16px; font-size: 0.9rem; }
    .alert.active { display: block; }
    .alert-error { background: rgba(239, 68, 68, 0.15); border: 1px solid var(--danger); color: #fca5a5; }
    .alert-success { background: rgba(34, 197, 94, 0.15); border: 1px solid var(--success); color: #86efac; }
    
    .progress-wrap { display: none; margin-top: 10px; }
    .progress-wrap.active { display: block; }
    .progress-track { height: 12px; background: var(--bg); border-radius: 6px; border: 1px solid var(--border); overflow: hidden; }
    .progress-bar { width: 0%; height: 100%; background: var(--primary); transition: width 0.1s linear; }
    .progress-text { display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted); margin-top: 4px; }
</style>
</head>
<body class="<?= $loggedIn ? 'is-admin' : '' ?>">

<div class="container">
    <header>
        <h1>🎬 Media Center</h1>
        <button type="button" class="btn btn-ghost" id="btnToggleAdmin">
            <?= $loggedIn ? '⚙️ Panel de Gestión' : '🔒 Administrador' ?>
        </button>
        <a href="https://syntaxsanctuary.com" style="color:var(--text-muted); text-decoration:none;">SyntSanc</a>
    </header>

    <div id="alertBox" class="alert"></div>

    <!-- Login -->
    <section id="loginPanel" class="panel <?= $loggedIn ? '' : 'active' ?>">
        <h2>🔐 Acceso Protegido</h2>
        <form id="loginForm">
            <input type="hidden" name="action" value="login">
            <div class="form-group">
                <label>Contraseña Maestra</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="btn btn-primary">Entrar</button>
        </form>
    </section>

    <!-- Upload -->
    <section id="uploadPanel" class="panel <?= $loggedIn ? 'active' : '' ?>">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h2>📤 Añadir Nuevo Vídeo</h2>
            <button type="button" id="btnLogout" class="btn btn-danger">Cerrar Sesión</button>
        </div>
        <form id="uploadForm">
            <input type="hidden" name="action" value="upload_video">
            <input type="hidden" name="csrf" id="csrfToken" value="<?= e($csrf) ?>">
            
            <div class="form-group">
                <label>Tipo de Medio</label>
                <select name="tipo_medio" id="tipoMedioSelect" onchange="toggleUploadFields()">
                    <option value="youtube">Enlace de YouTube (Recomendado)</option>
                    <option value="local">Archivo Local (MP4, WebM)</option>
                </select>
            </div>

            <div class="form-group">
                <label>Título</label>
                <input type="text" name="titulo" required placeholder="Ej: Mi nuevo proyecto">
            </div>
            
            <div class="form-group" id="fieldYoutube">
                <label>Enlace de YouTube (Botón Compartir o URL web)</label>
                <input type="url" name="youtube_url" id="youtubeInput" placeholder="https://youtu.be/..." required>
            </div>

            <div class="form-group" id="fieldFile" style="display: none;">
                <label>Archivo de Vídeo</label>
                <input type="file" name="archivo_video" id="fileInput" accept="video/mp4,video/webm,video/quicktime">
            </div>

            <div class="form-group">
                <label>Descripción</label>
                <textarea name="descripcion" placeholder="Detalles..."></textarea>
            </div>
            
            <div id="progressWrap" class="progress-wrap">
                <div class="progress-track"><div id="progressBar" class="progress-bar"></div></div>
                <div class="progress-text">
                    <span id="progressStatus">Procesando...</span>
                    <span id="progressPercent">0%</span>
                </div>
            </div>

            <button type="submit" id="btnUpload" class="btn btn-primary" style="margin-top: 10px;">Añadir a la Playlist</button>
        </form>
    </section>

    <!-- Reproductor -->
    <main class="main-layout">
        <section class="player-wrapper">
            <div class="video-container">
                <!-- Reproductor Archivo Local -->
                <video id="mainPlayer" controls playsinline <?= ($videoActual && $esLocal) ? '' : 'style="display:none;"' ?>>
                    <?php if ($videoActual && $esLocal): ?>
                        <source id="videoSource" src="<?= e($videoActual['url']) ?>" type="<?= e($videoActual['mime'] ?? 'video/mp4') ?>">
                    <?php else: ?>
                        <source id="videoSource" src="" type="video/mp4">
                    <?php endif; ?>
                </video>
                
                <!-- Reproductor YouTube -->
                <iframe id="youtubePlayer" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen <?= ($videoActual && $esYoutube) ? 'src="https://www.youtube.com/embed/'.e($videoActual['url']).'"' : 'style="display:none;"' ?>></iframe>
                
                <div id="emptyPlayer" class="empty" <?= $videoActual ? 'style="display:none;"' : '' ?>>No hay vídeos en el catálogo.</div>
            </div>
            <div class="video-details">
                <h2 id="videoTitle" class="video-title"><?= e($videoActual['titulo'] ?? 'Sin contenido') ?></h2>
                <div id="videoMeta" class="video-meta">
                    <span id="videoDate"><?= $videoActual ? 'Publicado: ' . e($videoActual['fecha']) : '' ?></span>
                    <span id="videoBadge" class="badge <?= $esYoutube ? 'yt' : '' ?>" <?= $videoActual ? '' : 'style="display:none;"' ?>>
                        <?= $esYoutube ? 'YouTube' : 'Local' ?>
                    </span>
                </div>
                <p id="videoDesc" class="video-desc"><?= e($videoActual['descripcion'] ?? '') ?></p>
            </div>
        </section>

        <aside class="playlist-wrapper">
            <div class="playlist-header">Catálogo (<span id="count"><?= count($videos) ?></span>)</div>
            <div class="playlist-items" id="playlist">
                <?php foreach ($videos as $index => $vid): 
                    $es_yt = ($vid['tipo'] ?? 'local') === 'youtube';
                ?>
                    <div class="playlist-item <?= $index === 0 ? 'active' : '' ?>" data-vid="<?= e(json_encode($vid)) ?>">
                        <span class="item-title"><?= e($vid['titulo']) ?></span>
                        <div class="item-date">
                            <span><?= e($vid['fecha']) ?></span>
                            <span style="font-weight:bold; font-size:10px; color:<?= $es_yt ? '#ff4444' : 'var(--text-muted)' ?>"><?= $es_yt ? 'YT' : 'MP4' ?></span>
                        </div>
                        <button type="button" class="btn btn-danger admin-only btn-delete" data-id="<?= e($vid['id']) ?>">Borrar</button>
                    </div>
                <?php endforeach; ?>
            </div>
        </aside>
    </main>
</div>

<script>
    const state = { loggedIn: <?= $loggedIn ? 'true' : 'false' ?>, csrf: '<?= e($csrf) ?>' };

    function showMsg(msg, isSuccess = false) {
        const box = document.getElementById('alertBox');
        box.textContent = msg;
        box.className = 'alert active ' + (isSuccess ? 'alert-success' : 'alert-error');
        setTimeout(() => box.className = 'alert', 5000);
    }

    function toggleUploadFields() {
        const type = document.getElementById('tipoMedioSelect').value;
        const fileField = document.getElementById('fieldFile');
        const ytField = document.getElementById('fieldYoutube');
        const fileInput = document.getElementById('fileInput');
        const ytInput = document.getElementById('youtubeInput');

        if (type === 'youtube') {
            fileField.style.display = 'none';
            ytField.style.display = 'flex';
            fileInput.removeAttribute('required');
            ytInput.setAttribute('required', 'required');
        } else {
            fileField.style.display = 'flex';
            ytField.style.display = 'none';
            ytInput.removeAttribute('required');
            fileInput.setAttribute('required', 'required');
        }
    }

    function ajax(formData, onProgress = null) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('POST', window.location.href);
            xhr.responseType = 'json';
            
            if (onProgress) {
                xhr.upload.addEventListener('progress', e => {
                    if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
                });
            }
            
            xhr.onload = () => xhr.status >= 200 && xhr.status < 300 ? resolve(xhr.response) : reject(xhr.response?.message || 'Error HTTP');
            xhr.onerror = () => reject('Fallo de conexión. Verifica límites o Cloudflare Timeout.');
            xhr.send(formData);
        });
    }

    document.getElementById('btnToggleAdmin').addEventListener('click', () => {
        if (!state.loggedIn) {
            document.getElementById('loginPanel').classList.toggle('active');
        } else {
            document.getElementById('uploadPanel').classList.toggle('active');
        }
    });

    document.getElementById('loginForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        try {
            const res = await ajax(new FormData(e.target));
            state.csrf = res.csrf;
            document.getElementById('csrfToken').value = res.csrf;
            state.loggedIn = true;
            document.body.classList.add('is-admin');
            document.getElementById('loginPanel').classList.remove('active');
            document.getElementById('uploadPanel').classList.add('active');
            document.getElementById('btnToggleAdmin').textContent = '⚙️ Panel de Gestión';
            e.target.reset();
            showMsg('Sesión iniciada.', true);
        } catch (err) { showMsg(err); }
    });

    document.getElementById('btnLogout').addEventListener('click', async () => {
        const fd = new FormData(); fd.append('action', 'logout'); fd.append('csrf', state.csrf);
        try {
            await ajax(fd);
            window.location.reload();
        } catch (err) { showMsg(err); }
    });

    document.getElementById('uploadForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const btn = document.getElementById('btnUpload');
        const wrap = document.getElementById('progressWrap');
        const bar = document.getElementById('progressBar');
        const perc = document.getElementById('progressPercent');
        const stat = document.getElementById('progressStatus');
        const isYoutube = document.getElementById('tipoMedioSelect').value === 'youtube';

        btn.disabled = true;
        wrap.classList.add('active');
        
        try {
            const res = await ajax(new FormData(e.target), (p) => {
                if (!isYoutube) {
                    bar.style.width = p + '%';
                    perc.textContent = p + '%';
                    stat.textContent = p === 100 ? 'Guardando en disco...' : 'Subiendo...';
                } else {
                    bar.style.width = '100%';
                    perc.textContent = '100%';
                    stat.textContent = 'Procesando enlace...';
                }
            });
            showMsg(res.message, true);
            setTimeout(() => window.location.reload(), 1000);
        } catch (err) {
            showMsg(err);
            wrap.classList.remove('active');
            btn.disabled = false;
        }
    });

    document.getElementById('playlist').addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-delete')) {
            if (!confirm('¿Seguro que deseas eliminar este vídeo?')) return;
            const fd = new FormData();
            fd.append('action', 'delete_video');
            fd.append('id_video', e.target.dataset.id);
            fd.append('csrf', state.csrf);
            try {
                const res = await ajax(fd);
                showMsg(res.message, true);
                e.target.closest('.playlist-item').remove();
                document.getElementById('count').textContent = document.querySelectorAll('.playlist-item').length;
            } catch (err) { showMsg(err); }
            return;
        }

        const item = e.target.closest('.playlist-item');
        if (!item) return;

        const data = JSON.parse(item.dataset.vid);
        document.querySelectorAll('.playlist-item').forEach(el => el.classList.remove('active'));
        item.classList.add('active');

        const player = document.getElementById('mainPlayer');
        const ytPlayer = document.getElementById('youtubePlayer');
        const source = document.getElementById('videoSource');
        const badge = document.getElementById('videoBadge');
        
        const isYoutube = (data.tipo || 'local') === 'youtube';

        if (isYoutube) {
            player.style.display = 'none';
            player.pause();
            ytPlayer.style.display = 'block';
            ytPlayer.src = 'https://www.youtube.com/embed/' + data.url + '?autoplay=1';
            
            badge.textContent = 'YouTube';
            badge.className = 'badge yt';
            badge.style.display = 'inline-block';
        } else {
            ytPlayer.style.display = 'none';
            ytPlayer.src = '';
            player.style.display = 'block';
            source.src = data.url;
            source.type = data.mime || 'video/mp4';
            player.load();
            player.play().catch(()=>{});
            
            badge.textContent = 'Local';
            badge.className = 'badge';
            badge.style.display = 'inline-block';
        }

        document.getElementById('videoTitle').textContent = data.titulo;
        document.getElementById('videoDate').textContent = 'Publicado: ' + data.fecha;
        document.getElementById('videoDesc').textContent = data.descripcion;
    });
</script>
</body>
</html>
