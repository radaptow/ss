<?php
/**
 * area_privada.php
 * Estación Central Unificada:
 * - Validación por Hash Blockchain.
 * - Archivador / Sandbox con almacenamiento aislado por usuario.
 * - Perfil de Usuario con opción de actualización de datos en tiempo real.
 * - Test Bench (Centro de Pruebas con guía interactiva de testing).
 * - Nexus Blog & Apuntes (Publicaciones privadas o públicas visibles para todos los usuarios).
 */
declare(strict_types=1);

// ============================================================
// 1. BLINDAJE DE EJECUCIÓN Y SESIÓN BLOCKCHAIN
// ============================================================
ini_set('display_errors', '0');
ini_set('log_errors', '1');
error_reporting(E_ALL);
set_time_limit(0);
ini_set('max_execution_time', '0');
ini_set('memory_limit', '512M');

ob_start();
session_start();
require_once 'conexion.php';

if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id']) || empty($_SESSION['hash_verificado'])) {
    header('Location: verificar.php');
    exit;
}

if (isset($_GET['logout'])) {
    $_SESSION = [];
    session_destroy();
    header('Location: verificar.php');
    exit;
}

$usuarioId = (int)$_SESSION['usuario_id'];
$accessKey = $_SESSION['hash_verificado'];

// ============================================================
// 2. GESTIÓN DE PERFIL Y ACTUALIZACIÓN DE DATOS
// ============================================================
$profileAlert = '';
$profileAlertType = 'success';

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action_profile'])) {
    $nuevoNombre = trim((string)($_POST['nombre'] ?? ''));
    $nuevaEdad   = (int)($_POST['edad'] ?? 0);
    $nuevoPais   = trim((string)($_POST['pais'] ?? ''));
    $nuevoCorreo = trim((string)($_POST['correo'] ?? ''));

    if ($nuevoNombre !== '' && $nuevoCorreo !== '') {
        try {
            $stmtUp = $pdo->prepare("UPDATE usuarios SET nombre = ?, edad = ?, pais = ?, correo = ? WHERE id = ?");
            $stmtUp->execute([$nuevoNombre, $nuevaEdad, $nuevoPais, $nuevoCorreo, $usuarioId]);

            // Re-consultar la fila actualizada para recalcular el Hash Blockchain automáticamente
            $stmtReload = $pdo->prepare("SELECT id, nombre, edad, pais, correo, hora FROM usuarios WHERE id = ? LIMIT 1");
            $stmtReload->execute([$usuarioId]);
            $usuarioActualizado = $stmtReload->fetch();

            if ($usuarioActualizado) {
                $nuevoHashBloque = generarHashConBlockchain($usuarioActualizado);
                $_SESSION['hash_verificado'] = $nuevoHashBloque['hash'];
                $accessKey = $nuevoHashBloque['hash'];
            }

            $profileAlert = '¡Perfil y Hash Blockchain actualizados con éxito!';
        } catch (Throwable $e) {
            $profileAlert = 'Error al actualizar el perfil: ' . $e->getMessage();
            $profileAlertType = 'error';
        }
    } else {
        $profileAlert = 'Nombre y Correo son obligatorios.';
        $profileAlertType = 'error';
    }
}

// Consultar datos del usuario actual
$stmt = $pdo->prepare("SELECT id, nombre, edad, pais, correo, hora FROM usuarios WHERE id = ? LIMIT 1");
$stmt->execute([$usuarioId]);
$usuarioActual = $stmt->fetch();

if (!$usuarioActual) {
    session_destroy();
    header('Location: verificar.php');
    exit;
}

$verificacionBloque = generarHashConBlockchain($usuarioActual);
if (!hash_equals($verificacionBloque['hash'], $accessKey)) {
    session_destroy();
    header('Location: verificar.php');
    exit;
}

// ============================================================
// 3. SISTEMA DE BLOG / APUNTES CON SOPORTE PÚBLICO / PRIVADO
// ============================================================
$blogDbFile = __DIR__ . '/storage_blog_unificado.json';
if (!file_exists($blogDbFile)) {
    file_put_contents($blogDbFile, json_encode([
        [
            'id' => 'post_demo_1',
            'user_id' => 0,
            'autor' => 'Sistema',
            'titulo' => 'Bienvenido al Nexus & Blog Comunitario',
            'contenido' => 'Este es un espacio de apuntes e ideas. Puedes publicar notas privadas (solo visibles en tu área) o públicas (visibles para todos los usuarios autenticados).',
            'visibilidad' => 'publica',
            'fecha' => date('Y-m-d H:i:s')
        ]
    ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['action_blog'])) {
    $tituloBlog = trim((string)($_POST['blog_titulo'] ?? ''));
    $textoBlog  = trim((string)($_POST['blog_contenido'] ?? ''));
    $visibilidad= ($_POST['blog_visibilidad'] ?? 'privada') === 'publica' ? 'publica' : 'privada';

    if ($textoBlog !== '') {
        $fpBlog = fopen($blogDbFile, 'c+');
        if (flock($fpBlog, LOCK_EX)) {
            $sizeBlog = filesize($blogDbFile);
            $contentBlog = $sizeBlog > 0 ? fread($fpBlog, $sizeBlog) : '[]';
            $postsList = json_decode($contentBlog, true) ?: [];

            $nuevoPost = [
                'id' => 'post_' . uniqid(),
                'user_id' => $usuarioId,
                'autor' => $usuarioActual['nombre'],
                'titulo' => $tituloBlog !== '' ? $tituloBlog : 'Nota rápida de ' . $usuarioActual['nombre'],
                'contenido' => $textoBlog,
                'visibilidad' => $visibilidad,
                'fecha' => date('Y-m-d H:i:s')
            ];

            array_unshift($postsList, $nuevoPost);
            ftruncate($fpBlog, 0);
            rewind($fpBlog);
            fwrite($fpBlog, json_encode($postsList, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
            flock($fpBlog, LOCK_UN);
        }
        fclose($fpBlog);
        header('Location: area_privada.php?tab=blog');
        exit;
    }
}

// Eliminar post propio del blog
if (isset($_GET['delete_blog'])) {
    $delId = $_GET['delete_blog'];
    $postsList = json_decode((string)file_get_contents($blogDbFile), true) ?: [];
    $postsList = array_values(array_filter($postsList, function($p) use ($delId, $usuarioId) {
        return !($p['id'] === $delId && ((int)$p['user_id'] === $usuarioId || $usuarioId === 1));
    }));
    file_put_contents($blogDbFile, json_encode($postsList, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));
    header('Location: area_privada.php?tab=blog');
    exit;
}

// ============================================================
// 4. CONFIGURACIÓN DEL SANDBOX DE ARCHIVOS POR USUARIO
// ============================================================
const BASE_STORAGE = __DIR__ . DIRECTORY_SEPARATOR . 'storage_usuarios';
if (!is_dir(BASE_STORAGE)) mkdir(BASE_STORAGE, 0755, true);

$userRootDirectory = BASE_STORAGE . DIRECTORY_SEPARATOR . 'user_' . $usuarioId;
if (!is_dir($userRootDirectory)) mkdir($userRootDirectory, 0755, true);
define('USER_ROOT_DIRECTORY', $userRootDirectory);

const MAX_EDIT_SIZE = 5 * 1024 * 1024;
const MAX_UPLOAD_SIZE = 20 * 1024 * 1024;
$FORBIDDEN_EDIT_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'ico', 'pdf', 'zip', 'gz', 'tar', 'rar', '7z', 'mp3', 'mp4', 'avi', 'mov'];

function e(string $v): string { return htmlspecialchars($v, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); }
function redirect_manager(string $url): never { header('Location: area_privada.php?tab=archivador' . $url); exit; }
function root_directory(): string { return rtrim(realpath(USER_ROOT_DIRECTORY), DIRECTORY_SEPARATOR); }
function is_current_manager_file(string $path): bool { return realpath(__FILE__) === realpath($path); }
function normalize_relative_path(string $path): string {
    $path = str_replace('\\', '/', $path);
    $parts = [];
    foreach (explode('/', $path) as $p) {
        if ($p === '' || $p === '.') continue;
        if ($p === '..') { if (!empty($parts)) array_pop($parts); continue; }
        $parts[] = $p;
    }
    return implode('/', $parts);
}
function safe_path(string $rel = ''): string {
    $root = root_directory();
    $rel = normalize_relative_path($rel);
    $cand = $rel === '' ? $root : $root . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $rel);
    if (file_exists($cand) || is_link($cand)) {
        $real = realpath($cand);
        if ($real === false || ($real !== $root && !str_starts_with($real, $root . DIRECTORY_SEPARATOR))) throw new RuntimeException('Acceso fuera de ruta.');
        return $real;
    }
    return $cand;
}
function relative_path(string $abs): string {
    $root = root_directory();
    return str_replace('\\', '/', $abs) === str_replace('\\', '/', $root) ? '' : ltrim(substr($abs, strlen($root)), '/');
}
function set_flash(string $msg, string $type = 'success'): void { $_SESSION['flash'] = ['message' => $msg, 'type' => $type]; }
function get_flash(): ?array { if (empty($_SESSION['flash'])) return null; $f = $_SESSION['flash']; unset($_SESSION['flash']); return $f; }
function can_edit_file(string $name, int $size, array $forbidden): bool {
    if ($size > MAX_EDIT_SIZE) return false;
    $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION));
    return !in_array($ext, $forbidden, true);
}
function format_bytes(int $b): string {
    if ($b < 1024) return $b . ' B';
    if ($b < 1024*1024) return number_format($b/1024, 1) . ' KB';
    return number_format($b/(1024*1024), 1) . ' MB';
}
function file_icon(string $name, bool $isDir): string {
    if ($isDir) return '📁';
    return match(strtolower(pathinfo($name, PATHINFO_EXTENSION))) {
        'php' => '🐘', 'html' => '🌐', 'css' => '🎨', 'js' => '⚡', 'json' => '🧩', default => '📄'
    };
}
function delete_directory_recursive(string $dir): bool {
    if (!is_dir($dir)) return false;
    foreach (scandir($dir) as $item) {
        if ($item === '.' || $item === '..') continue;
        $p = $dir . DIRECTORY_SEPARATOR . $item;
        is_dir($p) && !is_link($p) ? delete_directory_recursive($p) : unlink($p);
    }
    return rmdir($dir);
}

$action = $_GET['action'] ?? 'browse';
$currentPath = $_GET['path'] ?? '';

if ($action === 'download') {
    try {
        $file = safe_path($currentPath);
        if (!is_file($file)) throw new RuntimeException('No existe.');
        header('Content-Type: application/octet-stream');
        header('Content-Disposition: attachment; filename="' . basename($file) . '"');
        readfile($file);
        exit;
    } catch (Throwable $e) { die(e($e->getMessage())); }
}

if ($action === 'create_folder' || $action === 'create_file') {
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $name = trim((string)($_POST['name'] ?? ''));
        try {
            $newP = safe_path($currentPath) . DIRECTORY_SEPARATOR . $name;
            $action === 'create_folder' ? mkdir($newP, 0755) : file_put_contents($newP, '');
            set_flash('Elemento creado con éxito.');
        } catch (Throwable $e) { set_flash($e->getMessage(), 'error'); }
        redirect_manager('&path=' . urlencode($currentPath));
    }
}

if ($action === 'delete') {
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        try {
            $fp = safe_path($_POST['target'] ?? '');
            is_dir($fp) ? delete_directory_recursive($fp) : unlink($fp);
            set_flash('Elemento eliminado.');
        } catch (Throwable $e) { set_flash($e->getMessage(), 'error'); }
        redirect_manager('&path=' . urlencode(dirname(normalize_relative_path($_POST['target'] ?? ''))));
    }
}

$flash = get_flash();
$activeTab = $_GET['tab'] ?? 'perfil';
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Estación Privada // Syntax Sanctuary</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --surface: #334155;
            --accent: #10b981;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --danger: #ef4444;
            --danger-hover: #dc2626;
            --text: #f8fafc;
            --muted: #94a3b8;
            --border: #334155;
            --shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.45);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: system-ui, -apple-system, sans-serif; }
        body { background-color: var(--bg); color: var(--text); padding: 1.5rem; min-height: 100vh; }
        .container { background: var(--card); border: 1px solid var(--border); border-radius: 14px; max-width: 1000px; margin: 0 auto; padding: 2rem; box-shadow: var(--shadow); }
        
        .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 10px; border-bottom: 1px solid var(--border); padding-bottom: 1rem; }
        .badge { background: rgba(16, 185, 129, 0.15); color: var(--accent); padding: 0.35rem 0.85rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; }
        .btn { display: inline-flex; align-items: center; justify-content: center; padding: 8px 14px; border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--text); cursor: pointer; font-size: 0.9rem; font-weight: 600; text-decoration: none; transition: background 0.2s; }
        .btn:hover { background: #475569; }
        .btn-primary { background: var(--primary); border-color: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-danger { background: var(--danger); border-color: var(--danger); color: white; }
        .btn-danger:hover { background: var(--danger-hover); }

        /* Pestañas de Navegación */
        .nav-tabs { display: flex; gap: 8px; margin-bottom: 1.5rem; border-bottom: 2px solid var(--border); padding-bottom: 10px; flex-wrap: wrap; }
        .tab-link { padding: 8px 16px; border-radius: 8px; background: rgba(255,255,255,0.03); color: var(--muted); text-decoration: none; font-weight: 600; font-size: 0.9rem; transition: all 0.2s; }
        .tab-link.active { background: var(--primary); color: white; }

        .tab-content { display: none; }
        .tab-content.active { display: block; }

        code.hash-box { background: #090d16; color: #38bdf8; padding: 12px; display: block; word-break: break-all; border-left: 4px solid var(--accent); border-radius: 6px; margin: 0.75rem 0 1.5rem 0; font-family: monospace; font-size: 0.9rem; }

        /* Formularios y Perfil */
        .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
        .form-group { display: flex; flex-direction: column; gap: 6px; }
        label { font-size: 0.85rem; color: var(--muted); font-weight: bold; }
        input[type="text"], input[type="number"], input[type="email"], select, textarea { width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--border); background: #0f172a; color: var(--text); font-size: 0.95rem; }
        textarea { min-height: 100px; resize: vertical; }

        /* Tablas */
        table.tabla { width: 100%; border-collapse: collapse; margin-top: 1rem; font-size: 0.95rem; }
        table.tabla th, table.tabla td { padding: 10px; text-align: left; border-bottom: 1px solid var(--border); }
        table.tabla th { background: rgba(255, 255, 255, 0.04); color: #cbd5e1; }

        /* Test Bench & Blog Cards */
        .test-card, .blog-card { background: rgba(0,0,0,0.2); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem; margin-bottom: 1rem; }
        .test-card h4 { color: #38bdf8; margin-bottom: 6px; }
        .blog-card h3 { color: var(--accent); margin-bottom: 6px; display: flex; justify-content: space-between; align-items: center; }
        .blog-meta { font-size: 0.75rem; color: var(--muted); margin-bottom: 8px; }
        
        .alert { padding: 10px 14px; border-radius: 8px; margin-bottom: 1rem; font-size: 0.9rem; font-weight: 500; }
        .alert-success { background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid var(--accent); }
        .alert-error { background: rgba(239, 68, 68, 0.15); color: #fca5a5; border: 1px solid var(--danger); }
    </style>
</head>
<body>
    <div class="container">
        <!-- BARRA SUPERIOR -->
        <div class="top-bar">
            <div>
                <span class="badge">✓ Sesión Blockchain Activa</span>
                <h2 style="margin-top: 5px; font-size: 1.3rem;"><?php echo e($usuarioActual['nombre']); ?></h2>
            </div>
            <a href="?logout=1" class="btn btn-danger">Cerrar Sesión</a>
            <a href="../player/" class="btn btn-danger">Videos</a>
        </div>

        <!-- NAVEGACIÓN DE PESTAÑAS -->
        <div class="nav-tabs">
            <a href="?tab=perfil" class="tab-link <?php echo $activeTab === 'perfil' ? 'active' : ''; ?>">👤 Mi Perfil y Hash</a>
            <a href="?tab=archivador" class="tab-link <?php echo $activeTab === 'archivador' ? 'active' : ''; ?>">📂 Archivador Personal</a>
            <a href="?tab=blog" class="tab-link <?php echo $activeTab === 'blog' ? 'active' : ''; ?>">📝 Blog & Apuntes</a>
            <a href="?tab=testbench" class="tab-link <?php echo $activeTab === 'testbench' ? 'active' : ''; ?>">🧪 Test Bench (Pruebas)</a>
        </div>

        <!-- ================= PESTAÑA 1: PERFIL Y HASH ================= -->
        <div id="tab-perfil" class="tab-content <?php echo $activeTab === 'perfil' ? 'active' : ''; ?>">
            <h3>Gestión de Identidad y Hash Blockchain</h3>
            <p style="color: var(--muted); font-size: 0.9rem; margin-top: 4px; margin-bottom: 1rem;">
                Tu hash se regenera automáticamente al modificar tus datos personales, manteniendo la integridad criptográfica de tu cuenta.
            </p>

            <?php if ($profileAlert !== ''): ?>
                <div class="alert alert-<?php echo $profileAlertType === 'success' ? 'success' : 'error'; ?>">
                    <?php echo e($profileAlert); ?>
                </div>
            <?php endif; ?>

            <label>Tu Hash de Acceso Actual (SHA-256 Blockchain):</label>
            <code class="hash-box"><?php echo e($accessKey); ?></code>

            <form method="POST">
                <input type="hidden" name="action_profile" value="1">
                <div class="form-grid">
                    <div class="form-group">
                        <label for="nombre">Nombre Completo:</label>
                        <input type="text" id="nombre" name="nombre" value="<?php echo e($usuarioActual['nombre']); ?>" required>
                    </div>
                    <div class="form-group">
                        <label for="edad">Edad:</label>
                        <input type="number" id="edad" name="edad" value="<?php echo (int)$usuarioActual['edad']; ?>">
                    </div>
                    <div class="form-group">
                        <label for="pais">País:</label>
                        <input type="text" id="pais" name="pais" value="<?php echo e($usuarioActual['pais']); ?>">
                    </div>
                    <div class="form-group">
                        <label for="correo">Correo Electrónico:</label>
                        <input type="email" id="correo" name="correo" value="<?php echo e($usuarioActual['correo']); ?>" required>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary">Actualizar Perfil y Re-hashear</button>
            </form>
        </div>

        <!-- ================= PESTAÑA 2: ARCHIVADOR ================= -->
        <div id="tab-archivador" class="tab-content <?php echo $activeTab === 'archivador' ? 'active' : ''; ?>">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 1rem;">
                <h3>📂 Gestor de Archivos Aislado (Sandbox)</h3>
                <span style="font-size: 0.85rem; color: var(--muted);">Ruta: /<?php echo e($currentPath); ?></span>
            </div>

            <?php if ($flash): ?> 
                <div class="alert alert-<?php echo $flash['type'] === 'success' ? 'success' : 'error'; ?>"><?php echo e($flash['message']); ?></div> 
            <?php endif; ?> 

            <div style="display:flex; gap: 8px; margin-bottom: 1rem; flex-wrap: wrap;">
                <?php if ($currentPath !== ''): ?> 
                    <a href="?tab=archivador&path=<?php echo urlencode(dirname(normalize_relative_path($currentPath))); ?>" class="btn">⬅️ Subir Nivel</a> 
                <?php endif; ?> 
                <form method="post" action="?tab=archivador&action=create_folder&path=<?php echo e($currentPath); ?>" style="display:flex; gap:6px; flex:1; min-width: 200px;"> 
                    <input type="text" name="name" placeholder="Nueva Carpeta" required> 
                    <button type="submit" class="btn btn-primary">📁 Carpeta</button> 
                </form> 
                <form method="post" action="?tab=archivador&action=create_file&path=<?php echo e($currentPath); ?>" style="display:flex; gap:6px; flex:1; min-width: 200px;"> 
                    <input type="text" name="name" placeholder="Archivo.php" required> 
                    <button type="submit" class="btn btn-primary">📄 Archivo</button> 
                </form> 
            </div>

            <table class="tabla">
                <thead> 
                    <tr><th>Nombre</th><th>Tamaño</th><th>Modificado</th><th>Acciones</th></tr> 
                </thead> 
                <tbody> 
                    <?php 
                        $dirPath = safe_path($currentPath); 
                        $items = scandir($dirPath) ?: []; 
                        $folders = []; $files = []; 
                        foreach ($items as $item) { 
                            if ($item === '.' || $item === '..') continue; 
                            $itemAbsolutePath = $dirPath . DIRECTORY_SEPARATOR . $item; 
                            if (is_current_manager_file($itemAbsolutePath)) continue; 
                            is_dir($itemAbsolutePath) ? $folders[] = $item : $files[] = $item; 
                        } 
                        sort($folders); sort($files); 
                        foreach (array_merge($folders, $files) as $item): 
                            $itemPath = $dirPath . DIRECTORY_SEPARATOR . $item; 
                            $relItemPath = relative_path($itemPath); 
                            $isDir = is_dir($itemPath); 
                            $size = $isDir ? '-' : format_bytes(filesize($itemPath)); 
                            $mtime = date('Y-m-d H:i', filemtime($itemPath)); 
                    ?> 
                    <tr> 
                        <td> 
                            <?php echo file_icon($item, $isDir); ?> 
                            <?php if ($isDir): ?> 
                                <a href="?tab=archivador&path=<?php echo urlencode($relItemPath); ?>" style="color: #38bdf8; font-weight: bold; text-decoration: none;"><?php echo e($item); ?></a> 
                            <?php else: ?> 
                                <span><?php echo e($item); ?></span> 
                            <?php endif; ?> 
                        </td> 
                        <td><?php echo e($size); ?></td> 
                        <td><?php echo e($mtime); ?></td> 
                        <td> 
                            <div style="display:flex; gap:6px;"> 
                                <?php if (!$isDir): ?> 
                                    <a href="?tab=archivador&action=download&path=<?php echo urlencode($relItemPath); ?>" class="btn" style="padding:4px 8px; font-size:12px;">⬇️ Descargar</a> 
                                <?php endif; ?> 
                                <form method="post" action="?tab=archivador&action=delete" onsubmit="return confirm('¿Eliminar elemento?');" style="margin:0;"> 
                                    <input type="hidden" name="target" value="<?php echo e($relItemPath); ?>"> 
                                    <button type="submit" class="btn btn-danger" style="padding:4px 8px; font-size:12px;">🗑️ Borrar</button> 
                                </form> 
                            </div> 
                        </td> 
                    </tr> 
                    <?php endforeach; ?> 
                </tbody> 
            </table>
        </div>

        <!-- ================= PESTAÑA 3: BLOG Y APUNTES ================= -->
        <div id="tab-blog" class="tab-content <?php echo $activeTab === 'blog' ? 'active' : ''; ?>">
            <h3>Nexus Blog & Apuntes Compartidos</h3>
            <p style="color: var(--muted); font-size: 0.9rem; margin-top: 4px; margin-bottom: 1.5rem;">
                Publica notas privadas o compártelas con la comunidad (las públicas aparecen en el feed de todos los usuarios).
            </p>

            <div class="test-card" style="margin-bottom: 2rem;">
                <h4 style="color: var(--accent); margin-bottom: 10px;">➕ Crear Nueva Publicación o Nota</h4>
                <form method="POST">
                    <input type="hidden" name="action_blog" value="1">
                    <div class="form-group" style="margin-bottom: 10px;">
                        <label>Título:</label>
                        <input type="text" name="blog_titulo" placeholder="Título del apunte o idea...">
                    </div>
                    <div class="form-group" style="margin-bottom: 10px;">
                        <label>Contenido / Código:</label>
                        <textarea name="blog_contenido" placeholder="Escribe tu nota, fragmento de código o idea..." required></textarea>
                    </div>
                    <div class="form-group" style="margin-bottom: 10px;">
                        <label>Visibilidad:</label>
                        <select name="blog_visibilidad">
                            <option value="privada">🔒 Privada (Solo para mí)</option>
                            <option value="publica">🌐 Pública (Visible para todos los usuarios)</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-primary">Publicar Nota</button>
                </form>
            </div>

            <h4 style="margin-bottom: 1rem;">Feed de Apuntes (Tus notas + Públicas de otros)</h4>
            <?php
            $allPosts = json_decode((string)file_get_contents($blogDbFile), true) ?: [];
            $filteredPosts = array_filter($allPosts, function($p) use ($usuarioId) {
                return ($p['visibilidad'] === 'publica' || (int)$p['user_id'] === $usuarioId);
            });
            
            if (empty($filteredPosts)) {
                echo '<p style="color: var(--muted);">No hay publicaciones disponibles en este momento.</p>';
            } else {
                foreach ($filteredPosts as $post) {
                    $isMine = ((int)$post['user_id'] === $usuarioId || $usuarioId === 1);
                    echo '<div class="blog-card">';
                    echo '<h3>' . e($post['titulo']) . ' <span class="badge" style="font-size:0.7rem;">' . ($post['visibilidad'] === 'publica' ? '🌐 Público' : '🔒 Privado') . '</span></h3>';
                    echo '<div class="blog-meta">Por: <strong>' . e($post['autor']) . '</strong> • ' . e($post['fecha']) . '</div>';
                    echo '<p style="white-space: pre-wrap; font-size: 0.95rem; margin-bottom: 10px;">' . e($post['contenido']) . '</p>';
                    if ($isMine) {
                        echo '<a href="?tab=blog&delete_blog=' . e($post['id']) . '" class="btn btn-danger" style="padding: 2px 8px; font-size: 11px;" onclick="return confirm(\'¿Borrar esta nota?\')">Eliminar Nota</a>';
                    }
                    echo '</div>';
                }
            }
            ?>
        </div>

        <!-- ================= PESTAÑA 4: TEST BENCH ================= -->
        <div id="tab-testbench" class="tab-content <?php echo $activeTab === 'testbench' ? 'active' : ''; ?>">
            <h3>🧪 Test Bench & Guía de Pruebas (Staging)</h3>
            <p style="color: var(--muted); font-size: 0.9rem; margin-top: 4px; margin-bottom: 1.5rem;">
                Apartado especial interactivo diseñado para verificar que todos los módulos y características del sistema respondan correctamente durante tus pruebas.
            </p>

            <div class="test-card">
                <h4>1. Verificación de Integridad Blockchain</h4>
                <p style="font-size: 0.85rem; color: var(--muted); margin-bottom: 8px;">Prueba cambiar tus datos en la pestaña "Mi Perfil" y comprueba que el hash se actualice dinámicamente y coincida con el bloque.</p>
                <span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #93c5fd;">Estado: Listo para testear</span>
            </div>

            <div class="test-card">
                <h4>2. Test de Aislamiento de Archivos (Sandbox)</h4>
                <p style="font-size: 0.85rem; color: var(--muted); margin-bottom: 8px;">Crea una carpeta o sube un archivo de prueba en el Archivador. Verifica que se guarde exclusivamente en tu directorio personal <code>storage_usuarios/user_<?php echo $usuarioId; ?></code>.</p>
                <span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #93c5fd;">Estado: Listo para testear</span>
            </div>

            <div class="test-card">
                <h4>3. Test de Sincronización del Blog Comunitario</h4>
                <p style="font-size: 0.85rem; color: var(--muted); margin-bottom: 8px;">Crea un post público en la pestaña "Blog & Apuntes" e inicia sesión con otro hash/usuario diferente para verificar que la nota aparezca en su feed compartido.</p>
                <span class="badge" style="background: rgba(59, 130, 246, 0.15); color: #93c5fd;">Estado: Listo para testear</span>
            </div>
        </div>
    </div>

    <script>
        const activeTab = "<?php echo $activeTab; ?>";
        document.querySelectorAll('.tab-content').forEach(function(el) { el.classList.remove('active'); });
        var targetTab = document.getElementById('tab-' + activeTab);
        if (targetTab) targetTab.classList.add('active');
    </script>
    <script src="./ui_credenciales_privada.js"></script>
</body>
</html>