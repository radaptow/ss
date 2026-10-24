<?php 
declare(strict_types=1); 

session_start(); 

if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id']) || empty($_SESSION['hash_verificado'])) {
    header('Location: public/InicioDeSesion/verificar.php');
    exit;
}

/* 
 * ============================================================ 
 * PHP WEB FILE MANAGER - V2 
 * ============================================================ 
 * 
 * MONOLITO PHP 
 * 
 * Caracteristicas: 
 * - Login protegido 
 * - Explorador de archivos y carpetas 
 * - Crear y subir archivos / carpetas 
 * - Descargar y editar archivos de texto 
 * - Eliminar elementos recursivamente 
 * - Proteccion CSRF y Path Traversal 
 * - Auto-proteccion del propio File Manager 
 * - Tema Light / Dark 
 * - Responsive desde 320px (Mobile First) 
 * ============================================================ 
 */

/* ============================================================ 
 * CONFIGURACION 
 * ============================================================ */ 
const ROOT_DIRECTORY = __DIR__; 
const ADMIN_USERNAME = 'ramiro'; 

/* Genera un nuevo hash con: echo password_hash('TU_PASSWORD', PASSWORD_DEFAULT); */ 
const PASSWORD_HASH = '$2y$10$15Qu88oBBIYkSU/u.j.ie.lpbvL2jOPEVjMRvgKubBHt8XW7Kk2UO'; 

/* Tamaños máximos en bytes */ 
const MAX_EDIT_SIZE = 5 * 1024 * 1024; 
const MAX_UPLOAD_SIZE = 20 * 1024 * 1024; 

/* Extensiones prohibidas para edición */ 
$FORBIDDEN_EDIT_EXTENSIONS = [ 
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'ico', 'pdf', 'zip', 'gz',
    'tar', 'rar', '7z', 'mp3', 'mp4', 'avi', 'mov', 'woff', 'woff2', 'ttf', 'otf' 
];

/* ============================================================ 
 * SESIÓN 
 * ============================================================ */
/*session_name('php_file_manager_session'); 
session_set_cookie_params([ 
    'httponly' => true, 
    'secure' => !empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off', 
    'samesite' => 'Strict' 
]);*/


/* ============================================================ 
 * FUNCIONES GENERALES 
 * ============================================================ */ 
function e(string $value): string { 
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); 
} 

function redirect(string $url): never { 
    header('Location: ' . $url); 
    exit; 
} 

function is_logged_in(): bool { 
    return !empty($_SESSION['file_manager_authenticated']); 
} 

function require_login(): void { 
    if (!is_logged_in()) { 
        redirect('?action=login'); 
    } 
} 

function root_directory(): string { 
    $real = realpath(ROOT_DIRECTORY); 
    if ($real === false || !is_dir($real)) { 
        die('El directorio raíz no existe.'); 
    } 
    return rtrim($real, DIRECTORY_SEPARATOR); 
}

function is_current_manager_file(string $absolutePath): bool { 
    $currentFile = realpath(__FILE__); 
    $targetFile = realpath($absolutePath); 
    if ($currentFile === false || $targetFile === false) { 
        return false; 
    } 
    return $currentFile === $targetFile; 
} 

function normalize_relative_path(string $path): string { 
    $path = str_replace('\\', '/', $path); 
    $parts = []; 
    foreach (explode('/', $path) as $part) { 
        if ($part === '' || $part === '.') { 
            continue; 
        } 
        if ($part === '..') { 
            if (!empty($parts)) { 
                array_pop($parts); 
            } 
            continue; 
        } 
        $parts[] = $part; 
    } 
    return implode('/', $parts); 
} 

function safe_path(string $relativePath = ''): string { 
    $root = root_directory(); 
    $relativePath = normalize_relative_path($relativePath); 
    if ($relativePath === '') { 
        return $root; 
    } 
    $candidate = $root . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $relativePath);
    
    if (file_exists($candidate) || is_link($candidate)) { 
        $real = realpath($candidate); 
        if ($real === false) { 
            throw new RuntimeException('Ruta inválida.'); 
        } 
        if ($real !== $root && !str_starts_with($real, $root . DIRECTORY_SEPARATOR)) { 
            throw new RuntimeException('Acceso fuera del directorio permitido.'); 
        } 
        return $real; 
    }
    
    $parentReal = realpath(dirname($candidate)); 
    if ($parentReal === false) { 
        throw new RuntimeException('El directorio padre no existe.'); 
    }
    if ($parentReal !== $root && !str_starts_with($parentReal, $root . DIRECTORY_SEPARATOR)) { 
        throw new RuntimeException('Acceso fuera del directorio permitido.'); 
    } 
    return $candidate; 
} 

function relative_path(string $absolutePath): string { 
    $root = root_directory();
    $absolutePath = str_replace('\\', '/', $absolutePath); 
    $root = str_replace('\\', '/', $root); 
    if ($absolutePath === $root) { 
        return ''; 
    }
    return ltrim(substr($absolutePath, strlen($root)), '/'); 
} 

function set_flash(string $message, string $type = 'success'): void { 
    $_SESSION['flash'] = ['message' => $message, 'type' => $type]; 
} 

function get_flash(): ?array { 
    if (empty($_SESSION['flash'])) { 
        return null; 
    } 
    $flash = $_SESSION['flash']; 
    unset($_SESSION['flash']); 
    return $flash; 
} 

function csrf_token(): string { 
    if (empty($_SESSION['csrf_token'])) { 
        $_SESSION['csrf_token'] = bin2hex(random_bytes(32)); 
    }
    return $_SESSION['csrf_token']; 
} 

function verify_csrf(): void { 
    $token = $_POST['csrf_token'] ?? ''; 
    if (empty($token) || empty($_SESSION['csrf_token']) || !hash_equals($_SESSION['csrf_token'], $token)) { 
        http_response_code(403);
        die('CSRF token inválido.'); 
    } 
} 

function can_edit_file(string $filename, int $size, array $forbiddenExtensions): bool {
    if ($size > MAX_EDIT_SIZE) { 
        return false; 
    } 
    $extension = strtolower(pathinfo($filename, PATHINFO_EXTENSION));
    return !($extension !== '' && in_array($extension, $forbiddenExtensions, true)); 
}

function format_bytes(int $bytes): string { 
    if ($bytes < 1024) { 
        return $bytes . ' B'; 
    } 
    if ($bytes < 1024 * 1024) {
        return number_format($bytes / 1024, 1) . ' KB'; 
    } 
    if ($bytes < 1024 * 1024 * 1024) {
        return number_format($bytes / (1024 * 1024), 1) . ' MB'; 
    }
    return number_format($bytes / (1024 * 1024 * 1024), 1) . ' GB'; 
}

function file_icon(string $name, bool $isDirectory): string { 
    if ($isDirectory) { 
        return '📁'; 
    }
    $ext = strtolower(pathinfo($name, PATHINFO_EXTENSION)); 
    return match ($ext) { 
        'php' => '🐘', 
        'html', 'htm' => '🌐', 
        'css' => '🎨', 
        'js' => '⚡', 
        'json' => '🧩', 
        'md', 'txt' => '📄', 
        'jpg', 'jpeg', 'png', 'gif', 'webp' => '🖼️', 
        'zip', 'rar' => '📦', 
        default => '📄' 
    }; 
} 

function delete_directory_recursive(string $directory): bool { 
    if (!is_dir($directory)) { 
        return false; 
    }
    $items = scandir($directory); 
    if ($items === false) { 
        return false; 
    } 
    foreach ($items as $item) { 
        if ($item === '.' || $item === '..') { 
            continue; 
        } 
        $path = $directory . DIRECTORY_SEPARATOR . $item; 
        if (is_dir($path) && !is_link($path)) { 
            delete_directory_recursive($path); 
        } else { 
            unlink($path); 
        } 
    }
    return rmdir($directory); 
} 

/* ============================================================ 
 * LOGIN / LOGOUT 
 * ============================================================ */ 
if (isset($_GET['action']) && $_GET['action'] === 'logout') { 
    $_SESSION = []; 
    if (ini_get('session.use_cookies')) {
        $params = session_get_cookie_params(); 
        setcookie(session_name(), '', time() - 42000, $params['path'], $params['domain'], $params['secure'], $params['httponly']); 
    } 
    session_destroy(); 
    redirect('?action=login'); 
}

if (isset($_GET['action']) && $_GET['action'] === 'login') { 
    if (is_logged_in()) { 
        redirect('?'); 
    } 
    $loginError = null; 
    if ($_SERVER['REQUEST_METHOD'] === 'POST') { 
        $username = (string)($_POST['username'] ?? ''); 
        $password = (string)($_POST['password'] ?? ''); 
        if (hash_equals(ADMIN_USERNAME, $username) && password_verify($password, PASSWORD_HASH)) { 
            session_regenerate_id(true); 
            $_SESSION['file_manager_authenticated'] = true; 
            redirect('?'); 
        } else { 
            $loginError = 'Usuario o contraseña incorrectos.'; 
        } 
    } 
?> 
<!doctype html> 
<html lang="es"> 
<head> 
    <meta charset="utf-8"> 
    <meta name="viewport" content="width=device-width, initial-scale=1"> 
    <meta name="theme-color" content="#f1f5f9"> 
    <title>Login - PHP File Manager</title> 
    <style> 
        :root { 
            --bg: #f1f5f9; 
            --card: #ffffff; 
            --border: #cbd5e1; 
            --input: #f8fafc; 
            --text: #0f172a; 
            --muted: #64748b; 
            --primary: #2563eb; 
            --primary-hover: #1d4ed8; 
            --error: #fee2e2; 
            --error-text: #991b1b; 
        }
        *, *::before, *::after { box-sizing: border-box; } 
        html { min-width: 320px; } 
        body { 
            margin: 0; 
            min-width: 320px; 
            min-height: 100vh;
            display: flex; 
            align-items: center; 
            justify-content: center; 
            padding: 12px; 
            background: var(--bg); 
            color: var(--text); 
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; 
        } 
        .login { 
            width: 100%; 
            max-width: 420px; 
            padding: 22px; 
            background: var(--card); 
            border: 1px solid var(--border); 
            border-radius: 16px; 
            box-shadow: 0 15px 45px rgba(15, 23, 42, .12); 
        } 
        .login h2 { 
            margin: 0 0 24px; 
            font-size: clamp(20px, 7vw, 28px); 
            line-height: 1.2; 
            overflow-wrap: anywhere; 
        } 
        .login label { 
            display: block; 
            margin-bottom: 7px; 
            color: var(--muted); 
            font-size: 14px; 
            font-weight: 700; 
        } 
        .login input { 
            width: 100%; 
            min-height: 46px; 
            padding: 11px 12px; 
            margin-bottom: 16px; 
            border: 1px solid var(--border); 
            border-radius: 8px; 
            background: var(--input); 
            color: var(--text); 
            font: inherit; 
        } 
        .login input:focus { 
            outline: 3px solid rgba(37, 99, 235, .18); 
            border-color: var(--primary); 
        } 
        .login button { 
            width: 100%; 
            min-height: 46px; 
            padding: 11px; 
            border: 0; 
            border-radius: 8px; 
            background: var(--primary); 
            color: white; 
            font: inherit; 
            font-weight: 700; 
            cursor: pointer; 
        } 
        .login button:hover { background: var(--primary-hover); } 
        .error { 
            width: 100%; 
            padding: 12px; 
            margin-bottom: 20px; 
            border-radius: 8px; 
            background: var(--error); 
            color: var(--error-text); 
            overflow-wrap: anywhere; 
        } 
        @media (min-width: 480px) { 
            body { padding: 20px; } 
            .login { padding: 32px; } 
        } 
        a {color:purple; text-decoration:none; transition: 1s;}
        a:hover {color:lightgreen;}
    </style> 
</head> 
<body> 
    <main class="login"> 
        <h2>🗂️ File Manager</h2> 
        <?php if ($loginError): ?> 
            <div class="error"><?= e($loginError) ?></div> 
        <?php endif; ?> 
        <form method="post"> 
            <label for="username">Usuario</label> 
            <input id="username" name="username" autocomplete="username" required> 
            
            <label for="password">Contraseña</label> 
            <input id="password" name="password" type="password" autocomplete="current-password" required> 
            
            <button type="submit">Entrar</button> 
        </form> 
    </main> 
</body> 
</html> 
<?php 
    exit; 
} 

/* ============================================================ 
 * ACCIONES RUTA Y CONTROL
 * ============================================================ */ 
require_login(); 
$action = $_GET['action'] ?? 'browse'; 
$currentPath = $_GET['path'] ?? '';

/* Descargar */ 
if ($action === 'download') { 
    try { 
        $file = safe_path($currentPath); 
        if (!is_file($file)) { 
            throw new RuntimeException('El archivo no existe.'); 
        } 
        if (is_current_manager_file($file)) {
            throw new RuntimeException('No puedes descargar el propio File Manager.'); 
        } 
        header('Content-Type: application/octet-stream'); 
        header('Content-Disposition: attachment; filename="' . basename($file) . '"'); 
        header('Content-Length: ' . filesize($file)); 
        readfile($file); 
        exit; 
    } catch (Throwable $e) { 
        die(e($e->getMessage())); 
    } 
} 

/* Crear Carpeta / Archivo */ 
if ($action === 'create_folder' || $action === 'create_file') { 
    if ($_SERVER['REQUEST_METHOD'] === 'POST') { 
        verify_csrf(); 
        $name = trim((string)($_POST['name'] ?? '')); 
        try { 
            if ($name === '' || str_contains($name, '/') || str_contains($name, '\\')) { 
                throw new RuntimeException('Nombre inválido.'); 
            } 
            $parentPath = safe_path($currentPath); 
            $newPath = $parentPath . DIRECTORY_SEPARATOR . $name; 
            
            if (file_exists($newPath)) {
                throw new RuntimeException('Ya existe un elemento con ese nombre.'); 
            } 
            
            if ($action === 'create_folder') { 
                if (!mkdir($newPath, 0755)) { 
                    throw new RuntimeException('Error al crear carpeta.'); 
                } 
                set_flash('Carpeta creada.'); 
            } else {
                if (file_put_contents($newPath, '') === false) { 
                    throw new RuntimeException('Error al crear archivo.'); 
                } 
                set_flash('Archivo creado.'); 
            } 
        } catch (Throwable $e) { 
            set_flash($e->getMessage(), 'error'); 
        } 
        redirect('?' . http_build_query(['path' => $currentPath])); 
    } 
} 

/* Eliminar */ 
if ($action === 'delete') { 
    if ($_SERVER['REQUEST_METHOD'] === 'POST') { 
        verify_csrf(); 
        $target = (string)($_POST['target'] ?? ''); 
        try { 
            $fullPath = safe_path($target);
            if ($fullPath === root_directory()) { 
                throw new RuntimeException('No puedes eliminar la raíz.'); 
            } 
            if (is_current_manager_file($fullPath)) { 
                throw new RuntimeException('Por seguridad, no puedes eliminar el propio File Manager.'); 
            } 
            if (is_dir($fullPath)) { 
                if (!delete_directory_recursive($fullPath)) { 
                    throw new RuntimeException('Error al eliminar carpeta.'); 
                } 
            } else { 
                if (!unlink($fullPath)) { 
                    throw new RuntimeException('Error al eliminar archivo.'); 
                } 
            } 
            set_flash('Elemento eliminado.'); 
        } catch (Throwable $e) { 
            set_flash($e->getMessage(), 'error'); 
        } 
        redirect('?' . http_build_query(['path' => dirname(normalize_relative_path($target))])); 
    } 
} 

/* Subir Archivos */ 
if ($action === 'upload') { 
    if ($_SERVER['REQUEST_METHOD'] === 'POST') { 
        verify_csrf(); 
        try { 
            $destPath = safe_path($currentPath); 
            if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) { 
                throw new RuntimeException('Error al subir el archivo.'); 
            } 
            if ($_FILES['file']['size'] > MAX_UPLOAD_SIZE) { 
                throw new RuntimeException('Archivo demasiado grande.'); 
            } 
            $filename = basename($_FILES['file']['name']); 
            if ($filename === '' || $filename === '.' || $filename === '..') { 
                throw new RuntimeException('Nombre de archivo inválido.'); 
            } 
            $finalDest = $destPath . DIRECTORY_SEPARATOR . $filename; 
            if (file_exists($finalDest) && is_current_manager_file($finalDest)) { 
                throw new RuntimeException('No puedes sobrescribir el propio File Manager.'); 
            } 
            if (!move_uploaded_file($_FILES['file']['tmp_name'], $finalDest)) { 
                throw new RuntimeException('Error al mover el archivo subido.'); 
            } 
            set_flash('Archivo subido correctamente.'); 
        } catch (Throwable $e) { 
            set_flash($e->getMessage(), 'error'); 
        } 
        redirect('?' . http_build_query(['path' => $currentPath])); 
    } 
} 

/* Editar Archivo */ 
if ($action === 'edit') { 
    try { 
        $requestedEditFile = safe_path($currentPath); 
        if (is_current_manager_file($requestedEditFile)) { 
            set_flash('Por seguridad, no puedes editar el propio File Manager.', 'error'); 
            redirect('?' . http_build_query(['path' => dirname(normalize_relative_path($currentPath))])); 
        } 
    } catch (Throwable $e) { 
        set_flash($e->getMessage(), 'error'); 
        redirect('?'); 
    } 
    
    if ($_SERVER['REQUEST_METHOD'] === 'POST') { 
        verify_csrf(); 
        try { 
            $file = safe_path($currentPath); 
            if (is_current_manager_file($file)) { 
                throw new RuntimeException('Por seguridad, no puedes editar el propio File Manager.'); 
            } 
            if (!is_file($file)) { 
                throw new RuntimeException('Archivo no válido.'); 
            } 
            if (filesize($file) > MAX_EDIT_SIZE) { 
                throw new RuntimeException('El archivo es demasiado grande para editar.'); 
            } 
            $content = (string)($_POST['content'] ?? ''); 
            if (file_put_contents($file, $content) === false) { 
                throw new RuntimeException('Error al guardar el archivo.'); 
            } 
            set_flash('Archivo guardado correctamente.'); 
        } catch (Throwable $e) { 
            set_flash($e->getMessage(), 'error'); 
        } 
        redirect('?' . http_build_query(['action' => 'edit', 'path' => $currentPath])); 
    } 
} 

$flash = get_flash(); 
?> 
<!doctype html> 
<html lang="es"> 
<head> 
    <meta charset="utf-8"> 
    <meta name="viewport" content="width=device-width, initial-scale=1"> 
    <meta name="theme-color" content="#f1f5f9"> 
    <meta name="color-scheme" content="light dark"> 
    <title>PHP File Manager</title> 
    <style> 
        /* ============================================================ 
         * LIGHT THEME 
         * ============================================================ */ 
        :root { 
            --bg: #f1f5f9; 
            --surface: #ffffff; 
            --surface-2: #f8fafc; 
            --surface-3: #e2e8f0; 
            --border: #cbd5e1; 
            --border-soft: #e2e8f0; 
            --text: #0f172a; 
            --text-muted: #64748b; 
            --primary: #2563eb; 
            --primary-hover: #1d4ed8; 
            --danger: #dc2626; 
            --danger-hover: #b91c1c; 
            --success-bg: #dcfce7; 
            --success-text: #166534; 
            --error-bg: #fee2e2; 
            --error-text: #991b1b; 
            --input: #ffffff; 
            --editor-bg: #0f172a; 
            --editor-text: #d1fae5; 
            --shadow: 0 8px 30px rgba(15, 23, 42, .08); 
            --radius: 10px; 
            --radius-small: 7px; 
            --touch-size: 44px; 
        } 

        /* ============================================================ 
         * DARK THEME 
         * ============================================================ */ 
        html[data-theme="dark"] { 
            --bg: #0b1120; 
            --surface: #111827; 
            --surface-2: #1f2937; 
            --surface-3: #273449; 
            --border: #374151; 
            --border-soft: #263244; 
            --text: #f9fafb; 
            --text-muted: #9ca3af; 
            --primary: #2563eb; 
            --primary-hover: #1d4ed8; 
            --danger: #dc2626; 
            --danger-hover: #b91c1c; 
            --success-bg: #065f46; 
            --success-text: #d1fae5; 
            --error-bg: #991b1b; 
            --error-text: #fee2e2; 
            --input: #0f172a; 
            --editor-bg: #020617; 
            --editor-text: #a7f3d0; 
            --shadow: 0 15px 45px rgba(0, 0, 0, .25); 
        } 

        /* ============================================================ 
         * ESTILOS GENERALES Y LAYOUT 
         * ============================================================ */ 
        *, *::before, *::after { box-sizing: border-box; } 
        html { width: 100%; min-width: 320px; scroll-behavior: smooth; } 
        body { 
            margin: 0; 
            width: 100%; 
            min-width: 320px; 
            min-height: 100vh; 
            background: var(--bg); 
            color: var(--text); 
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; 
            font-size: 16px; 
            line-height: 1.5; 
            overflow-x: hidden; 
            transition: background .2s ease, color .2s ease; 
        } 

        a { color: #2563eb; text-decoration: none; overflow-wrap: anywhere; word-break: break-word; } 
        html[data-theme="dark"] a { color: #60a5fa; } 
        a:hover { text-decoration: underline; } 

        button, input, textarea { font: inherit; } 
        button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible { 
            outline: 3px solid rgba(37, 99, 235, .25); 
            outline-offset: 2px; 
        } 

        .container { width: 100%; max-width: 1200px; margin: 0 auto; padding: 10px 8px 40px; } 

        header { 
            width: 100%; 
            display: flex; 
            flex-direction: column; 
            align-items: stretch; 
            gap: 10px; 
            padding: 10px 0 16px; 
            margin-bottom: 16px; 
            border-bottom: 1px solid var(--border); 
        } 
        header > div:first-child { min-width: 0; } 
        header h2 { margin: 0; font-size: clamp(18px, 5vw, 26px); line-height: 1.25; overflow-wrap: anywhere; word-break: break-word; } 
        header > div:last-child { width: 100%; } 

        .btn { 
            min-height: var(--touch-size); 
            display: inline-flex; 
            align-items: center; 
            justify-content: center; 
            padding: 9px 12px; 
            border: 1px solid var(--border); 
            border-radius: var(--radius-small); 
            background: var(--surface-3); 
            color: var(--text); 
            cursor: pointer; 
            font-size: 14px; 
            font-weight: 650; 
            line-height: 1.2; 
            text-decoration: none; 
            transition: background .15s ease, transform .1s ease, border-color .15s ease; 
        } 
        .btn:hover { background: var(--surface-2); text-decoration: none; } 
        .btn:active { transform: translateY(1px); } 
        .btn-primary { border-color: var(--primary); background: var(--primary); color: white; } 
        .btn-primary:hover { background: var(--primary-hover); color: white; } 
        .btn-danger { border-color: var(--danger); background: var(--danger); color: white; } 
        .btn-danger:hover { background: var(--danger-hover); color: white; } 
        .theme-button { background: var(--surface); color: var(--text); border: 1px solid var(--border); } 

        .alert { width: 100%; padding: 12px; margin-bottom: 16px; border: 1px solid transparent; border-radius: var(--radius); overflow-wrap: anywhere; word-break: break-word; } 
        .alert-success { background: var(--success-bg); color: var(--success-text); } 
        .alert-error { background: var(--error-bg); color: var(--error-text); } 

        .toolbar { 
            width: 100%; 
            display: flex; 
            flex-direction: column; 
            align-items: stretch; 
            gap: 10px; 
            margin-bottom: 16px; 
            padding: 10px; 
            background: var(--surface); 
            border: 1px solid var(--border); 
            border-radius: var(--radius); 
            box-shadow: var(--shadow); 
        } 
        .toolbar form { width: 100% !important; display: flex !important; flex-direction: column !important; gap: 8px !important; margin: 0 !important; } 

        input[type="text"], input[type="file"] { 
            width: 100%; 
            min-width: 0; 
            min-height: var(--touch-size); 
            padding: 10px 12px; 
            border: 1px solid var(--border); 
            border-radius: var(--radius-small); 
            background: var(--input); 
            color: var(--text); 
            outline: none; 
        } 
        input[type="text"]:focus, input[type="file"]:focus { border-color: var(--primary); outline: 3px solid rgba(37, 99, 235, .12); } 
        input[type="file"] { padding: 8px; } 
        input::placeholder { color: var(--text-muted); } 

        table { width: 100%; border-collapse: separate; border-spacing: 0; background: transparent; } 
        thead { display: none; } 
        tbody { display: flex; flex-direction: column; gap: 10px; } 
        tr { display: flex; flex-direction: column; width: 100%; padding: 11px; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; box-shadow: var(--shadow); } 

        td { width: 100%; display: block; padding: 5px 0; border: 0; overflow-wrap: anywhere; word-break: break-word; } 
        td:first-child { display: flex; align-items: flex-start; gap: 8px; min-width: 0; font-weight: 500; } 
        td:first-child a, td:first-child span { min-width: 0; overflow-wrap: anywhere; word-break: break-word; } 
        td:nth-child(2)::before { content: "Tamaño: "; color: var(--text-muted); font-weight: 650; } 
        td:nth-child(3)::before { content: "Modificado: "; color: var(--text-muted); font-weight: 650; } 

        .actions { width: 100%; display: flex; flex-direction: column; gap: 8px; margin-top: 8px; padding-top: 10px; border-top: 1px solid var(--border-soft); } 
        .actions .btn, .actions form, .actions form .btn { width: 100%; } 
        .actions form { display: block !important; margin: 0 !important; } 

        textarea { 
            display: block; 
            width: 100%; 
            min-width: 0; 
            height: 60vh; 
            min-height: 320px; 
            padding: 12px; 
            background: var(--editor-bg); 
            color: var(--editor-text); 
            border: 1px solid var(--border); 
            border-radius: var(--radius); 
            resize: vertical; 
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace; 
            font-size: 14px; 
            line-height: 1.6; 
            tab-size: 4; 
            white-space: pre; 
            overflow: auto; 
        } 
        textarea:focus { outline: 3px solid rgba(37, 99, 235, .18); border-color: var(--primary); } 
        .toolbar > span { min-width: 0; overflow-wrap: anywhere; word-break: break-word; } 
        tbody tr td[colspan] { text-align: center; padding: 30px 15px; color: var(--text-muted); } 

        /* Media Queries */
        @media (min-width: 320px) and (max-width: 359px) { 
            .container { padding-left: 7px; padding-right: 7px; } 
            header { gap: 8px; } 
            header h2 { font-size: 18px; } 
            .toolbar { padding: 8px; } 
            .btn { font-size: 13px; padding-left: 9px; padding-right: 9px; } 
            tr { padding: 9px; } 
            textarea { font-size: 13px; } 
        } 
        @media (min-width: 360px) { .container { padding-left: 10px; padding-right: 10px; } } 
        @media (min-width: 480px) { 
            .container { padding-left: 16px; padding-right: 16px; } 
            .toolbar form { flex-direction: row !important; align-items: stretch; } 
            .toolbar form input[type="text"] { flex: 1; } 
            .toolbar form .btn { width: auto; } 
            .actions { flex-direction: row; flex-wrap: wrap; } 
            .actions .btn, .actions form, .actions form .btn { width: auto; } 
        } 
        @media (min-width: 768px) { 
            .container { padding: 20px 20px 50px; } 
            header { flex-direction: row; align-items: center; justify-content: space-between; } 
            header > div:last-child { width: auto; } 
            .toolbar { flex-direction: row; align-items: center; flex-wrap: wrap; } 
            .toolbar form { width: auto !important; } 
            thead { display: table-header-group; } 
            tbody { display: table-row-group; } 
            tr { display: table-row; padding: 0; background: var(--surface); border: 0; border-radius: 0; box-shadow: none; } 
            td, th { display: table-cell; padding: 12px; border-bottom: 1px solid var(--border); text-align: left; vertical-align: middle; } 
            td:nth-child(2)::before, td:nth-child(3)::before { content: ""; } 
            .actions { display: flex; flex-direction: row; margin: 0; padding: 0; border: 0; } 
            .actions form { display: inline !important; } 
            .actions .btn, .actions form, .actions form .btn { width: auto; } 
            tr:hover { background: var(--surface-3); } 
        } 
        @media (min-width: 1024px) { 
            .container { padding-left: 20px; padding-right: 20px; } 
            .toolbar { padding: 15px; } 
            .btn { min-height: 40px; } 
            td, th { padding: 12px; } 
            textarea { height: 65vh; } 
        } 
        @media (prefers-reduced-motion: reduce) { 
            *, *::before, *::after { scroll-behavior: auto !important; transition: none !important; animation: none !important; } 
        } 
        @media print { 
            body { background: white; color: black; } 
            .toolbar, header > div:last-child, .actions { display: none !important; } 
            .container { max-width: none; } 
            tr { background: white; color: black; } 
        } 
    </style> 
</head> 
<body> 
    <div class="container"> 
        <!-- HEADER --> 
        <header> 
            <div> 
                <h2>🗂️ / <?= e($currentPath) ?></h2> 
            </div> 
            <div style="display:flex; flex-wrap:wrap; gap:8px;"> 
                <button type="button" class="btn theme-button" id="themeToggle" aria-label="Cambiar tema">☀️ Light</button> 
                <a href="?action=logout" class="btn btn-danger">Cerrar Sesión</a> 
            </div> 
        </header> 

        <!-- FLASH MESSAGES --> 
        <?php if ($flash): ?> 
            <div class="alert alert-<?= e($flash['type']) ?>"><?= e($flash['message']) ?></div> 
        <?php endif; ?> 

        <!-- MODO EDITOR --> 
        <?php if ($action === 'edit'): ?> 
            <?php 
                $fullPath = safe_path($currentPath); 
                if (!is_file($fullPath)) { die('Archivo no válido.'); } 
                if (is_current_manager_file($fullPath)) { die('No puedes editar el propio File Manager.'); } 
                $content = file_get_contents($fullPath); 
            ?> 
            <div class="toolbar"> 
                <a href="?path=<?= e(dirname($currentPath)) ?>" class="btn">⬅️ Volver</a> 
                <span>Editando: <strong><?= e(basename($fullPath)) ?></strong></span> 
            </div> 
            <form method="post"> 
                <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>"> 
                <textarea name="content" spellcheck="false"><?= e($content) ?></textarea> 
                <div style="height:16px;"></div> 
                <button type="submit" class="btn btn-primary">💾 Guardar Archivo</button> 
            </form> 
        <?php else: ?> 
            <!-- MODO EXPLORADOR --> 
            <div class="toolbar"> 
                <?php if ($currentPath !== ''): ?> 
                    <a href="?path=<?= e(dirname($currentPath)) ?>" class="btn">⬅️ Subir Nivel</a> 
                <?php endif; ?> 

                <!-- Crear carpeta --> 
                <form method="post" action="?action=create_folder&path=<?= e($currentPath) ?>"> 
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>"> 
                    <input type="text" name="name" placeholder="Nueva Carpeta" autocomplete="off" required> 
                    <button type="submit" class="btn btn-primary">📁 Crear Carpeta</button> 
                </form> 

                <!-- Crear archivo --> 
                <form method="post" action="?action=create_file&path=<?= e($currentPath) ?>"> 
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>"> 
                    <input type="text" name="name" placeholder="Nuevo Archivo" autocomplete="off" required> 
                    <button type="submit" class="btn btn-primary">📄 Crear Archivo</button> 
                </form> 

                <!-- Subir archivo --> 
                <form method="post" action="?action=upload&path=<?= e($currentPath) ?>" enctype="multipart/form-data"> 
                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>"> 
                    <input type="file" name="file" required> 
                    <button type="submit" class="btn btn-primary">📤 Subir</button> 
                </form> 
            </div> 

            <!-- TABLA DE ARCHIVOS --> 
            <table> 
                <thead> 
                    <tr> 
                        <th>Nombre</th> 
                        <th>Tamaño</th> 
                        <th>Última Modificación</th> <th>Acciones</th> 
                    </tr> 
                </thead> 
                <tbody> 
                    <?php 
                        $dirPath = safe_path($currentPath); 
                        $items = scandir($dirPath); 
                        $folders = []; 
                        $files = []; 

                        foreach ($items as $item) { 
                            if ($item === '.' || $item === '..') { continue; } 
                            $itemAbsolutePath = $dirPath . DIRECTORY_SEPARATOR . $item; 
                            if (is_current_manager_file($itemAbsolutePath)) { continue; } 
                            
                            if (is_dir($itemAbsolutePath)) { 
                                $folders[] = $item; 
                            } else { 
                                $files[] = $item; 
                            } 
                        } 
                        sort($folders); 
                        sort($files); 

                        foreach (array_merge($folders, $files) as $item): 
                            $itemPath = $dirPath . DIRECTORY_SEPARATOR . $item; 
                            $relItemPath = relative_path($itemPath); 
                            $isDir = is_dir($itemPath); 
                            $size = $isDir ? '-' : format_bytes(filesize($itemPath)); 
                            $mtime = date('Y-m-d H:i', filemtime($itemPath)); 
                    ?> 
                    <tr> 
                        <td> 
                            <span aria-hidden="true"><?= file_icon($item, $isDir) ?></span> 
                            <?php if ($isDir): ?> 
                                <a href="?path=<?= urlencode($relItemPath) ?>"><strong><?= e($item) ?></strong></a> 
                            <?php else: ?> 
                                <span><?= e($item) ?></span> 
                            <?php endif; ?> 
                        </td> 
                        <td><?= e($size) ?></td> 
                        <td><?= e($mtime) ?></td> 
                        <td> 
                            <div class="actions"> 
                                <?php if (!$isDir): ?> 
                                    <a href="?action=download&path=<?= urlencode($relItemPath) ?>" class="btn">⬇️ Descargar</a> 
                                    <?php if (can_edit_file($item, filesize($itemPath), $FORBIDDEN_EDIT_EXTENSIONS)): ?> 
                                        <a href="?action=edit&path=<?= urlencode($relItemPath) ?>" class="btn btn-primary">✏️ Editar</a> 
                                    <?php endif; ?> 
                                <?php endif; ?> 
                                <form method="post" action="?action=delete" onsubmit="return confirm('¿Seguro que deseas eliminar esto?');"> 
                                    <input type="hidden" name="csrf_token" value="<?= e(csrf_token()) ?>"> 
                                    <input type="hidden" name="target" value="<?= e($relItemPath) ?>"> 
                                    <button type="submit" class="btn btn-danger">🗑️ Borrar</button> 
                                </form> 
                            </div> 
                        </td> 
                    </tr> 
                    <?php endforeach; ?> 

                    <?php if (empty($folders) && empty($files)): ?> 
                    <tr> 
                        <td colspan="4">📂 El directorio está vacío.</td> 
                    </tr> 
                    <?php endif; ?> 
                </tbody> 
            </table> 
        <?php endif; ?> 
    </div> 

    <!-- SCRIPT DE TEMA (LIGHT / DARK) --> 
    <script> 
        (function () { 
            'use strict'; 
            const html = document.documentElement; 
            const button = document.getElementById('themeToggle'); 
            
            let savedTheme = localStorage.getItem('php_file_manager_theme'); 
            if (savedTheme !== 'dark' && savedTheme !== 'light') { 
                savedTheme = 'light'; 
            } 
            html.dataset.theme = savedTheme; 

            function updateThemeButton() { 
                if (!button) { return; } 
                if (html.dataset.theme === 'dark') { 
                    button.textContent = '🌙 Dark'; 
                    button.setAttribute('aria-label', 'Cambiar a tema claro'); 
                } else { 
                    button.textContent = '☀️ Light'; 
                    button.setAttribute('aria-label', 'Cambiar a tema oscuro'); 
                } 
            } 
            updateThemeButton(); 

            if (button) { 
                button.addEventListener('click', function () { 
                    const newTheme = html.dataset.theme === 'dark' ? 'light' : 'dark'; 
                    html.dataset.theme = newTheme; 
                    localStorage.setItem('php_file_manager_theme', newTheme); 
                    updateThemeButton(); 
                }); 
            } 
        })(); 
    </script> 
    <script src="https://syntaxsanctuary.com/public/machine_status/Template/bit.js" data-user="SyntaxSanctuary_RGG"></script>
    <script src="http://localhost:8000/public/InicioDeSesion/terminal_secreta_login.js"></script>
</body> 
</html>
