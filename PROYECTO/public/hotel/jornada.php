<?php
declare(strict_types=1);

session_start();

date_default_timezone_set('America/Mexico_City');

/*
 * ============================================================
 * hkpgReloj
 * MONOLITO PHP
 *
 * VERSIÓN:
 * RELOJ + NÓMINA + BACKUP/RESTORE
 * ============================================================
 */


/* ============================================================
 * CONFIGURACIÓN
 * ============================================================ */

const ACCESS_PIN = '2708';

const DATA_FILE = __DIR__ . '/asistencia_db.json';

const DEFAULT_RATE = 15.00;

const LUNCH_MINUTES = 30;

const OVERTIME_LIMIT = 40.0;

const SPECIAL_MULTIPLIER = 1.5;

/*
 * Configuración de periodos de nómina bisemanales (14 días)
 */
const ANCHOR_PAY_PERIOD_START = '09/14/2026';
const PAY_PERIOD_DAYS = 14;


/*
 * Deducciones de nómina
 */

const PRE_TAX_DEDUCTION = 88.02;

const TAX_SS = 0.062;

const TAX_MEDICARE = 0.0145;

const TAX_FEDERAL = 0.041723;

const TAX_STATE = 0.020518;


/* ============================================================
 * DATOS INICIALES
 * ============================================================ */

$default_data = [

    'users' => [
        'Ramiro Garcia Gonzalez'
    ],

    'tarifas' => [
        'Ramiro Garcia Gonzalez' => DEFAULT_RATE
    ],

    'entries' => []

];


/* ============================================================
 * FUNCIONES GENERALES
 * ============================================================ */

function h(mixed $value): string
{
    return htmlspecialchars(
        (string)$value,
        ENT_QUOTES,
        'UTF-8'
    );
}


/* ============================================================
 * RESPUESTA JSON
 * ============================================================ */

function jsonResponse(array $data, int $status = 200): never
{
    http_response_code($status);

    header(
        'Content-Type: application/json; charset=utf-8'
    );

    echo json_encode(
        $data,
        JSON_UNESCAPED_UNICODE |
        JSON_UNESCAPED_SLASHES
    );

    exit;
}


/* ============================================================
 * CARGAR BASE DE DATOS
 * ============================================================ */

function load_db(
    string $file,
    array $default_data
): array {

    if (!file_exists($file)) {
        return $default_data;
    }

    $content = file_get_contents($file);

    if ($content === false || trim($content) === '') {
        return $default_data;
    }

    $data = json_decode($content, true);

    if (!is_array($data)) {
        return $default_data;
    }

    if (
        !isset($data['users']) ||
        !is_array($data['users']) ||
        empty($data['users'])
    ) {
        $data['users'] = $default_data['users'];
    }

    if (
        !isset($data['tarifas']) ||
        !is_array($data['tarifas'])
    ) {
        $data['tarifas'] = [];
    }

    if (
        !isset($data['entries']) ||
        !is_array($data['entries'])
    ) {
        $data['entries'] = [];
    }

    foreach ($data['users'] as $user) {

        if (!isset($data['tarifas'][$user])) {
            $data['tarifas'][$user] = DEFAULT_RATE;
        }
    }

    return $data;
}


/* ============================================================
 * GUARDAR BASE DE DATOS
 * ============================================================ */

function save_db(
    string $file,
    array $data
): bool {

    $json = json_encode(
        $data,
        JSON_PRETTY_PRINT |
        JSON_UNESCAPED_UNICODE |
        JSON_UNESCAPED_SLASHES
    );

    if ($json === false) {
        return false;
    }

    return file_put_contents(
        $file,
        $json,
        LOCK_EX
    ) !== false;
}


/* ============================================================
 * VALIDAR ESTRUCTURA
 * ============================================================ */

function validateDatabase(array $data): array
{
    $errors = [];

    if (
        !isset($data['users']) ||
        !is_array($data['users'])
    ) {
        $errors[] = 'El JSON no contiene users válido.';
    }

    if (
        !isset($data['tarifas']) ||
        !is_array($data['tarifas'])
    ) {
        $errors[] = 'El JSON no contiene tarifas válido.';
    }

    if (
        !isset($data['entries']) ||
        !is_array($data['entries'])
    ) {
        $errors[] = 'El JSON no contiene entries válido.';
    }

    return $errors;
}


/* ============================================================
 * AUTENTICACIÓN
 * ============================================================ */

if (
    isset($_GET['pin']) &&
    hash_equals(
        ACCESS_PIN,
        (string)$_GET['pin']
    )
) {

    $_SESSION['authenticated'] = true;

    header(
        'Location: ' .
        strtok($_SERVER['REQUEST_URI'], '?')
    );

    exit;
}


if (
    $_SERVER['REQUEST_METHOD'] === 'POST' &&
    ($_POST['action'] ?? '') === 'login'
) {

    if (
        hash_equals(
            ACCESS_PIN,
            (string)($_POST['pin'] ?? '')
        )
    ) {

        $_SESSION['authenticated'] = true;

        if (isset($_POST['is_ajax'])) {
            jsonResponse([
                'success' => true,
                'message' => 'Acceso autorizado.'
            ]);
        }

        header(
            'Location: ' .
            $_SERVER['PHP_SELF']
        );

        exit;
    }

    if (isset($_POST['is_ajax'])) {

        jsonResponse([
            'success' => false,
            'error' => 'PIN incorrecto.'
        ]);
    }
}


$is_authenticated =
    ($_SESSION['authenticated'] ?? false) === true;


$db = load_db(
    DATA_FILE,
    $default_data
);


/* ============================================================
 * MODO ACTUAL
 * ============================================================ */

if (!isset($_SESSION['app_mode'])) {
    $_SESSION['app_mode'] = 'clock';
}

if (
    !in_array(
        $_SESSION['app_mode'],
        ['clock', 'admin'],
        true
    )
) {
    $_SESSION['app_mode'] = 'clock';
}


/* ============================================================
 * POST GENERAL
 * ============================================================ */

if (
    $is_authenticated &&
    $_SERVER['REQUEST_METHOD'] === 'POST'
) {

    $action = $_POST['action'] ?? '';

    $is_ajax =
        isset($_POST['is_ajax']) &&
        $_POST['is_ajax'] === '1';


    /* LOGOUT */
    if ($action === 'logout') {
        session_destroy();
        header('Location: ' . $_SERVER['PHP_SELF']);
        exit;
    }


    /* CAMBIAR PESTAÑA */
    if ($action === 'set_role') {
        $mode = $_POST['mode'] ?? 'clock';
        if (!in_array($mode, ['clock', 'admin'], true)) {
            $mode = 'clock';
        }

        $_SESSION['app_mode'] = $mode;

        if ($is_ajax) {
            jsonResponse([
                'success' => true,
                'mode' => $mode
            ]);
        }

        header('Location: ' . $_SERVER['PHP_SELF']);
        exit;
    }


    /* ENTRADA */
    if ($action === 'clock_in') {
        $user = trim((string)($_POST['user'] ?? ''));
        $client_time = trim((string)($_POST['client_time'] ?? date('h:i A')));

        if ($user === '' || !in_array($user, $db['users'], true)) {
            if ($is_ajax) {
                jsonResponse([
                    'success' => false,
                    'error' => 'Usuario no válido.'
                ]);
            }
        }

        $already_open = false;
        foreach (array_reverse($db['entries']) as $entry) {
            if (
                ($entry['user'] ?? '') === $user &&
                ($entry['time_out'] ?? '') === 'En Turno...'
            ) {
                $already_open = true;
                break;
            }
        }

        if ($already_open) {
            if ($is_ajax) {
                jsonResponse([
                    'success' => false,
                    'error' => 'Este empleado ya tiene un turno abierto.'
                ]);
            }
        }

        $db['entries'][] = [
            'user' => $user,
            'date' => date('m/d/Y'),
            'time_in' => $client_time,
            'time_out' => 'En Turno...',
            'is_holiday' => false
        ];

        if (!save_db(DATA_FILE, $db)) {
            if ($is_ajax) {
                jsonResponse([
                    'success' => false,
                    'error' => 'No se pudo guardar asistencia_db.json.'
                ]);
            }
        }

        if ($is_ajax) {
            jsonResponse([
                'success' => true,
                'message' => "¡Entrada registrada para {$user}!"
            ]);
        }
    }


    /* SALIDA */
    if ($action === 'clock_out') {
        $user = trim((string)($_POST['user'] ?? ''));
        $client_time = trim((string)($_POST['client_time'] ?? date('h:i A')));
        $found = false;

        for ($i = count($db['entries']) - 1; $i >= 0; $i--) {
            if (
                ($db['entries'][$i]['user'] ?? '') === $user &&
                ($db['entries'][$i]['time_out'] ?? '') === 'En Turno...'
            ) {
                $db['entries'][$i]['time_out'] = $client_time;
                $found = true;
                break;
            }
        }

        if (!$found) {
            $db['entries'][] = [
                'user' => $user,
                'date' => date('m/d/Y'),
                'time_in' => '07:00 AM',
                'time_out' => $client_time,
                'is_holiday' => false
            ];
        }

        if (!save_db(DATA_FILE, $db)) {
            if ($is_ajax) {
                jsonResponse([
                    'success' => false,
                    'error' => 'No se pudo guardar asistencia_db.json.'
                ]);
            }
        }

        if ($is_ajax) {
            jsonResponse([
                'success' => true,
                'message' => $found
                    ? "¡Salida registrada para {$user}!"
                    : "Salida registrada sin entrada previa para {$user}."
            ]);
        }
    }


    /* AGREGAR USUARIO */
    if ($action === 'add_user') {
        $name = trim((string)($_POST['new_user_name'] ?? ''));
        $rate = (float)($_POST['new_user_rate'] ?? DEFAULT_RATE);

        if ($name === '') {
            jsonResponse(['success' => false, 'error' => 'Escribe un nombre.']);
        }

        if (in_array($name, $db['users'], true)) {
            jsonResponse(['success' => false, 'error' => 'El empleado ya existe.']);
        }

        $db['users'][] = $name;
        $db['tarifas'][$name] = max(0, $rate);
        save_db(DATA_FILE, $db);

        jsonResponse([
            'success' => true,
            'message' => "Empleado {$name} agregado correctamente."
        ]);
    }


    /* ACTUALIZAR TARIFA */
    if ($action === 'update_rate') {
        $user = trim((string)($_POST['target_user'] ?? ''));
        $rate = (float)($_POST['new_rate'] ?? DEFAULT_RATE);

        if ($user === '' || !in_array($user, $db['users'], true)) {
            jsonResponse(['success' => false, 'error' => 'Empleado no encontrado.']);
        }

        $db['tarifas'][$user] = max(0, $rate);
        save_db(DATA_FILE, $db);

        jsonResponse([
            'success' => true,
            'message' => "Tarifa actualizada para {$user}."
        ]);
    }


    /* RESET */
    if ($action === 'reset') {
        $db['entries'] = [];
        save_db(DATA_FILE, $db);

        jsonResponse([
            'success' => true,
            'message' => 'Historial eliminado correctamente.'
        ]);
    }


    /* BACKUP */
    if ($action === 'backup') {
        if (!file_exists(DATA_FILE)) {
            save_db(DATA_FILE, $db);
        }

        $filename = 'asistencia_backup_' . date('Y-m-d_H-i-s') . '.json';

        header('Content-Type: application/json; charset=utf-8');
        header('Content-Disposition: attachment; filename="' . $filename . '"');
        header('Content-Length: ' . filesize(DATA_FILE));

        readfile(DATA_FILE);
        exit;
    }


    /* IMPORTAR JSON */
    if ($action === 'import_json') {
        if (!isset($_FILES['backup_file']) || $_FILES['backup_file']['error'] !== UPLOAD_ERR_OK) {
            jsonResponse(['success' => false, 'error' => 'No se recibió un archivo JSON válido.']);
        }

        $content = file_get_contents($_FILES['backup_file']['tmp_name']);
        if ($content === false) {
            jsonResponse(['success' => false, 'error' => 'No se pudo leer el archivo.']);
        }

        $imported = json_decode($content, true);
        if (!is_array($imported) || json_last_error() !== JSON_ERROR_NONE) {
            jsonResponse(['success' => false, 'error' => 'El archivo no contiene JSON válido.']);
        }

        $validation = validateDatabase($imported);
        if (!empty($validation)) {
            jsonResponse(['success' => false, 'error' => implode(' ', $validation)]);
        }

        $importMode = $_POST['import_mode'] ?? 'merge';

        if ($importMode === 'replace') {
            $newDb = [
                'users' => array_values(array_unique($imported['users'])),
                'tarifas' => $imported['tarifas'],
                'entries' => $imported['entries']
            ];
        } else {
            $newDb = $db;
            foreach ($imported['users'] as $user) {
                if (!in_array($user, $newDb['users'], true)) {
                    $newDb['users'][] = $user;
                }
            }
            foreach ($imported['tarifas'] as $user => $rate) {
                $newDb['tarifas'][$user] = (float)$rate;
            }

            $added = 0;
            foreach ($imported['entries'] as $newEntry) {
                if (!isset($newEntry['user']) || !isset($newEntry['date']) || !isset($newEntry['time_in'])) {
                    continue;
                }

                $exists = false;
                foreach ($newDb['entries'] as $existing) {
                    if (
                        ($existing['user'] ?? '') === ($newEntry['user'] ?? '') &&
                        ($existing['date'] ?? '') === ($newEntry['date'] ?? '') &&
                        ($existing['time_in'] ?? '') === ($newEntry['time_in'] ?? '')
                    ) {
                        $exists = true;
                        break;
                    }
                }

                if (!$exists) {
                    if (!isset($newEntry['is_holiday'])) {
                        $newEntry['is_holiday'] = false;
                    }
                    $newDb['entries'][] = $newEntry;
                    $added++;
                }
            }
            $imported_count = $added;
        }

        foreach ($newDb['users'] as $user) {
            if (!isset($newDb['tarifas'][$user])) {
                $newDb['tarifas'][$user] = DEFAULT_RATE;
            }
        }

        if (!save_db(DATA_FILE, $newDb)) {
            jsonResponse(['success' => false, 'error' => 'No se pudo guardar la base restaurada.']);
        }

        $db = $newDb;

        jsonResponse([
            'success' => true,
            'message' => $importMode === 'replace'
                ? 'Base de datos restaurada completamente.'
                : "Importación completada. {$imported_count} registros nuevos agregados."
        ]);
    }

    jsonResponse(['success' => false, 'error' => 'Acción desconocida.']);
}


/* ============================================================
 * CÁLCULOS DE TURNOS
 * ============================================================ */

function calcularDetalleTurno(
    array $entry,
    float $rate,
    float $multiplier
): array {

    if (($entry['time_out'] ?? '') === 'En Turno...') {
        return ['horas' => 0, 'tarifa' => $rate, 'pago' => 0];
    }

    $timeIn = DateTime::createFromFormat('h:i A', $entry['time_in'] ?? '');
    $timeOut = DateTime::createFromFormat('h:i A', $entry['time_out'] ?? '');

    if (!$timeIn || !$timeOut) {
        return ['horas' => 0, 'tarifa' => $rate, 'pago' => 0];
    }

    if ($timeOut < $timeIn) {
        $timeOut->modify('+1 day');
    }

    $seconds = $timeOut->getTimestamp() - $timeIn->getTimestamp();
    $minutes = max(0, $seconds / 60);
    $minutes = max(0, $minutes - LUNCH_MINUTES);
    $hours = $minutes / 60;

    $holiday = !empty($entry['is_holiday']);
    $appliedRate = $holiday ? $rate * $multiplier : $rate;

    return [
        'horas' => $hours,
        'tarifa' => $appliedRate,
        'pago' => $hours * $appliedRate
    ];
}


/* ============================================================
 * NÓMINA POR EMPLEADO
 * ============================================================ */

function calcularNominaPorEmpleado(
    array $entries,
    float $rate,
    float $multiplier
): array {

    $totalHours = 0;
    $gross = 0;

    usort($entries, function (array $a, array $b): int {
        return strcmp($a['date'] ?? '', $b['date'] ?? '');
    });

    $weeks = [];

    foreach ($entries as $entry) {
        $date = DateTime::createFromFormat('m/d/Y', $entry['date'] ?? '');
        if (!$date) {
            continue;
        }
        $weekKey = $date->format('o-W');
        $weeks[$weekKey][] = $entry;
    }

    foreach ($weeks as $weekEntries) {
        $weekHours = 0;

        foreach ($weekEntries as $entry) {
            $detail = calcularDetalleTurno($entry, $rate, $multiplier);
            $hours = $detail['horas'];

            if ($hours <= 0) {
                continue;
            }

            $totalHours += $hours;

            if (!empty($entry['is_holiday'])) {
                $gross += $hours * $rate * $multiplier;
                continue;
            }

            $regularRemaining = max(0, OVERTIME_LIMIT - $weekHours);
            $regularHours = min($hours, $regularRemaining);
            $overtimeHours = max(0, $hours - $regularHours);

            $gross += ($regularHours * $rate) + ($overtimeHours * $rate * $multiplier);
            $weekHours += $hours;
        }
    }

    return [
        'horas' => $totalHours,
        'bruto' => $gross
    ];
}


/* ============================================================
 * LÓGICA DINÁMICA DE PERIODOS DE NÓMINA (BISEMANALES)
 * ============================================================ */

function getPayPeriodInfo(DateTime $date): array {
    $anchor = DateTime::createFromFormat('m/d/Y', ANCHOR_PAY_PERIOD_START);
    $anchor->setTime(0, 0, 0);

    $current = clone $date;
    $current->setTime(0, 0, 0);

    $diffDays = (int)$anchor->diff($current)->format('%r%a');
    $periodIndex = (int)floor($diffDays / PAY_PERIOD_DAYS);

    $startDate = clone $anchor;
    $startDate->modify('+' . ($periodIndex * PAY_PERIOD_DAYS) . ' days');

    $endDate = clone $startDate;
    $endDate->modify('+' . (PAY_PERIOD_DAYS - 1) . ' days');

    return [
        'index' => $periodIndex,
        'start' => $startDate,
        'end' => $endDate,
        'label' => $startDate->format('m/d/Y') . ' - ' . $endDate->format('m/d/Y')
    ];
}


/* ============================================================
 * HTML
 * ============================================================ */
?>
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>hkpgReloj</title>

<style>
:root {
    --bg: #f4f6f8;
    --card: #ffffff;
    --primary: #1e3a8a;
    --accent: #2563eb;
    --success: #15803d;
    --danger: #b91c1c;
    --warning: #d97706;
    --purple: #7c3aed;
    --text: #0f172a;
    --muted: #64748b;
    --border: #cbd5e1;
}

* { box-sizing: border-box; }

html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    min-height: 100%;
}

body {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    padding: 4px;
    overflow-x: hidden;
}

.container {
    width: 100%;
    max-width: 430px;
    margin: 8px auto;
    background: var(--card);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 18px rgba(0,0,0,.10);
}

.container.wide-mode { max-width: 900px; }

.view-switcher {
    display: grid;
    grid-template-columns: 1fr 1fr auto;
    gap: 4px;
    padding: 4px;
    background: var(--primary);
}

.switcher-btn {
    min-width: 0;
    padding: 11px 6px;
    border: 2px solid rgba(255,255,255,.35);
    border-radius: 8px;
    background: rgba(0,0,0,.18);
    color: white;
    font-size: .78rem;
    font-weight: 800;
    cursor: pointer;
    white-space: nowrap;
}

.switcher-btn.active {
    background: white;
    color: var(--primary);
    border-color: white;
}

.switcher-btn:hover { filter: brightness(1.08); }

.content { padding: 14px; }

.form-group {
    margin-bottom: 14px;
    text-align: left;
}

.form-group label {
    display: block;
    margin-bottom: 6px;
    font-weight: 700;
}

.form-group select,
.form-group input,
.form-group textarea {
    width: 100%;
    padding: 12px;
    border: 2px solid var(--border);
    border-radius: 8px;
    font-size: 1rem;
    background: white;
    outline: none;
}

.btn {
    width: 100%;
    padding: 13px;
    border: none;
    border-radius: 8px;
    color: white;
    font-size: 1rem;
    font-weight: 800;
    cursor: pointer;
}

.btn:disabled { opacity: .55; cursor: not-allowed; }
.btn-primary { background: var(--accent); }
.btn-danger { background: var(--danger); }
.btn-success { background: var(--success); }
.btn-in { background: var(--success); font-size: 1.35rem; padding: 18px; margin-bottom: 10px; }
.btn-out { background: var(--danger); font-size: 1.35rem; padding: 18px; }

.section-box {
    background: #f1f5f9;
    padding: 14px;
    border-radius: 10px;
    border: 2px solid var(--border);
    margin-top: 12px;
}

.section-box h3 { margin-top: 0; }

.record-row {
    background: white;
    border: 2px solid var(--border);
    border-radius: 8px;
    padding: 11px;
    margin-bottom: 8px;
}

.record-header {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-weight: 700;
    color: var(--primary);
}

.record-details {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 10px;
    margin-top: 5px;
    font-size: .88rem;
    color: #475569;
}

.table-responsive {
    width: 100%;
    overflow-x: auto;
    margin-top: 10px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: white;
}

.payroll-table {
    width: 100%;
    min-width: 600px;
    border-collapse: collapse;
    font-size: .82rem;
}

.payroll-table th,
.payroll-table td {
    padding: 8px 9px;
    border: 1px solid var(--border);
    text-align: left;
    white-space: nowrap;
}

.payroll-table th {
    background: var(--primary);
    color: white;
}

.backup-note {
    font-size: .82rem;
    color: var(--muted);
    line-height: 1.4;
}

.file-input {
    width: 100%;
    padding: 10px;
    background: white;
    border: 2px dashed var(--border);
    border-radius: 8px;
}

.pin-card { padding: 22px; text-align: center; }

.pin-input {
    width: 100%;
    padding: 15px;
    font-size: 2rem;
    text-align: center;
    letter-spacing: 9px;
    border: 3px solid var(--border);
    border-radius: 10px;
    margin-bottom: 15px;
    background: #f1f5f9;
    font-weight: bold;
}

#sys-toast {
    position: fixed;
    left: 50%;
    bottom: 20px;
    transform: translate(-50%, 30px);
    width: min(92vw, 420px);
    padding: 14px 18px;
    border-radius: 9px;
    color: white;
    font-weight: 700;
    text-align: center;
    z-index: 9999;
    opacity: 0;
    pointer-events: none;
    transition: .25s ease;
}

#sys-toast.show { opacity: 1; transform: translate(-50%, 0); }

@media (max-width: 360px) {
    body { padding: 2px; }
    .container { margin: 2px auto; border-radius: 8px; }
    .content { padding: 9px; }
    .view-switcher { grid-template-columns: 1fr 1fr; }
    .switcher-btn:last-child { grid-column: 1 / -1; }
    .switcher-btn { font-size: .74rem; padding: 10px 3px; }
    .record-header, .record-details { flex-direction: column; align-items: flex-start; }
}
</style>
</head>

<body>

<div id="sys-toast"></div>

<div class="container <?= ($is_authenticated && $_SESSION['app_mode'] === 'admin') ? 'wide-mode' : '' ?>">

<?php if (!$is_authenticated): ?>

    <!-- LOGIN -->
    <div class="pin-card">
        <h2 style="color:var(--primary);margin-top:0;">🏨 hkpgReloj</h2>
        <p style="color:var(--muted);">Ingrese el PIN de acceso</p>

        <form id="loginForm" onsubmit="submitAjax(event,'loginForm')">
            <input type="hidden" name="action" value="login">
            <input type="password" name="pin" class="pin-input" placeholder="••••" maxlength="6" inputmode="numeric" required autofocus>
            <button type="submit" class="btn btn-primary">INGRESAR</button>
        </form>
    </div>

<?php else: ?>

    <!-- NAVEGACIÓN -->
    <div class="view-switcher">
        <button type="button" onclick="switchTab('clock')" class="switcher-btn <?= $_SESSION['app_mode'] === 'clock' ? 'active' : '' ?>">
            ⏱️ RELOJ
        </button>
        <button type="button" onclick="switchTab('admin')" class="switcher-btn <?= $_SESSION['app_mode'] === 'admin' ? 'active' : '' ?>">
            📋 NÓMINA
        </button>
        <form method="POST" style="margin:0;display:contents;" onsubmit="return confirm('¿Cerrar sesión?');">
            <input type="hidden" name="action" value="logout">
            <button type="submit" class="switcher-btn" style="background:#991b1b;border-color:#b91c1c;">
                🔒 SALIR
            </button>
        </form>
    </div>

    <div class="content">

<?php if ($_SESSION['app_mode'] === 'clock'): ?>

    <!-- RELOJ -->
    <div class="section-box" style="text-align:center;border-color:var(--primary);border-width:3px;">
        <h2 style="color:var(--primary);margin-top:0;">hkpgReloj</h2>
        <p style="color:var(--muted);margin-top:0;">Registro de turno</p>

        <form id="clockForm">
            <div class="form-group">
                <label>Seleccione su Nombre</label>
                <select name="user" id="clockUser" required>
                    <?php foreach ($db['users'] as $user): ?>
                        <option value="<?= h($user) ?>"><?= h($user) ?></option>
                    <?php endforeach; ?>
                </select>
            </div>

            <button type="button" id="btnClockIn" class="btn btn-in" onclick="submitClock('clock_in')">🟢 ENTRADA</button>
            <button type="button" id="btnClockOut" class="btn btn-out" onclick="submitClock('clock_out')">🔴 SALIDA</button>
        </form>
    </div>

    <!-- BACKUP -->
    <div class="section-box">
        <h3>💾 Respaldo de datos</h3>
        <p class="backup-note">Descarga una copia completa de empleados, tarifas y registros actuales.</p>
        <form method="POST" style="margin-bottom:10px;">
            <input type="hidden" name="action" value="backup">
            <button type="submit" class="btn btn-success">💾 DESCARGAR RESPALDO JSON</button>
        </form>

        <h3>📥 Restaurar / cargar JSON</h3>
        <p class="backup-note">Puedes cargar un archivo JSON generado previamente por este sistema.</p>
        <form id="importForm" enctype="multipart/form-data" onsubmit="submitAjax(event, 'importForm')">
            <input type="hidden" name="action" value="import_json">
            <div class="form-group">
                <input type="file" name="backup_file" class="file-input" accept=".json,application/json" required>
            </div>
            <div class="form-group">
                <label>Método de importación</label>
                <select name="import_mode">
                    <option value="merge">🔗 Combinar con datos actuales</option>
                    <option value="replace">⚠️ Reemplazar completamente</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary">📥 CARGAR ARCHIVO JSON</button>
        </form>
    </div>

<?php elseif ($_SESSION['app_mode'] === 'admin'): ?>

    <!-- NÓMINA DINÁMICA -->
<?php
// Determinar periodo actual según la fecha de hoy o la más reciente
$today = new DateTime();
$currentPeriodInfo = getPayPeriodInfo($today);

// Agrupar entradas por periodo
$periodos = [];

foreach ($db['entries'] as $entry) {
    if (($entry['time_out'] ?? '') === 'En Turno...') {
        continue;
    }

    $date = DateTime::createFromFormat('m/d/Y', $entry['date'] ?? '');
    if (!$date) {
        continue;
    }

    $info = getPayPeriodInfo($date);
    $pIdx = $info['index'];

    if (!isset($periodos[$pIdx])) {
        $periodos[$pIdx] = [
            'info' => $info,
            'users' => []
        ];
    }

    $user = $entry['user'] ?? '';
    $periodos[$pIdx]['users'][$user]['entries'][] = $entry;
}

// Ordenar periodos por fecha
ksort($periodos);

// Separar en periodos pasados y periodo actual
$periodosPasados = [];
$periodoActualData = null;

foreach ($periodos as $pIdx =>$pData) {
    if ($pIdx < $currentPeriodInfo['index']) {$periodosPasados[$pIdx] =$pData;
    } else {
        $periodoActualData =$pData;
    }
}

if (!$periodoActualData) {$periodoActualData = [
        'info' => $currentPeriodInfo,
        'users' => []
    ];
}
?>

    <!-- PERIODOS PASADOS -->
    <?php if (!empty($periodosPasados)): ?>
        <?php foreach ($periodosPasados as$pData): ?>
            <div class="section-box" style="background:#e2e8f0;text-align:center;margin-top:12px;">
                <h3 style="margin:0;color:#475569;">📁 Periodo Pasado</h3>
                <small><?= h($pData['info']['label']) ?></small>
            </div>

            <div class="table-responsive">
                <table class="payroll-table">
                    <tr>
                        <th>Personal</th>
                        <th>Tarifa</th>
                        <th>Horas</th>
                        <th>Bruto</th>
                        <th>Deducc.</th>
                        <th>Impuestos</th>
                        <th>Neto</th>
                    </tr>

                    <?php if (empty($pData['users'])): ?>
                        <tr><td colspan="7" style="text-align:center;color:var(--muted);">No hay registros.</td></tr>
                    <?php else: ?>
                        <?php foreach ($pData['users'] as $name =>$uData): ?>
                            <?php
                            $rate = (float)($db['tarifas'][$name] ?? DEFAULT_RATE);
                            $calc = calcularNominaPorEmpleado($uData['entries'],$rate, SPECIAL_MULTIPLIER);
                            $gross =$calc['bruto'];
                            $deductions =$gross > 0 ? PRE_TAX_DEDUCTION : 0;
                            $taxable = max(0,$gross - $deductions);$ss = round($taxable * TAX_SS, 2);$med = round($taxable * TAX_MEDICARE, 2);$fed = round($taxable * TAX_FEDERAL, 2);$state = round($taxable * TAX_STATE, 2);$taxes = $ss +$med + $fed +$state;
                            $net = max(0,$gross - $deductions -$taxes);
                            ?>
                            <tr>
                                <td><strong><?= h($name) ?></strong></td>
                                <td>$<?= number_format($rate, 2) ?></td>
                                <td><?= number_format($calc['horas'], 2) ?>h</td>
                                <td>$<?= number_format($gross, 2) ?></td>
                                <td style="color:var(--danger);">-$<?= number_format($deductions, 2) ?></td>
                                <td style="color:var(--warning);">-$<?= number_format($taxes, 2) ?></td>
                                <td><strong style="color:var(--success);">$<?= number_format($net, 2) ?></strong></td>
                            </tr>
                        <?php endforeach; ?>
                    <?php endif; ?>
                </table>
            </div>
        <?php endforeach; ?>
    <?php endif; ?>

    <!-- PERIODO ACTUAL -->
    <div class="section-box" style="background:#dbeafe;border-color:var(--accent);text-align:center;">
        <h3 style="margin:0;color:var(--primary);">📊 Periodo Actual</h3>
        <small><?= h($periodoActualData['info']['label']) ?></small>
    </div>

    <div class="table-responsive">
        <table class="payroll-table">
            <tr>
                <th>Personal</th>
                <th>Tarifa</th>
                <th>Horas</th>
                <th>Bruto</th>
                <th>Deducc.</th>
                <th>Impuestos</th>
                <th>Neto</th>
            </tr>

            <?php if (empty($periodoActualData['users'])): ?>
                <tr><td colspan="7" style="text-align:center;color:var(--muted);">No hay registros en el periodo actual.</td></tr>
            <?php else: ?>
                <?php foreach ($periodoActualData['users'] as $name =>$uData): ?>
                    <?php
                    $rate = (float)($db['tarifas'][$name] ?? DEFAULT_RATE);
                    $calc = calcularNominaPorEmpleado($uData['entries'],$rate, SPECIAL_MULTIPLIER);
                    $gross =$calc['bruto'];
                    $deductions =$gross > 0 ? PRE_TAX_DEDUCTION : 0;
                    $taxable = max(0,$gross - $deductions);$ss = round($taxable * TAX_SS, 2);$med = round($taxable * TAX_MEDICARE, 2);$fed = round($taxable * TAX_FEDERAL, 2);$state = round($taxable * TAX_STATE, 2);$taxes = $ss +$med + $fed +$state;
                    $net = max(0,$gross - $deductions -$taxes);
                    ?>
                    <tr>
                        <td><strong><?= h($name) ?></strong></td>
                        <td>$<?= number_format($rate, 2) ?></td>
                        <td><?= number_format($calc['horas'], 2) ?>h</td>
                        <td>$<?= number_format($gross, 2) ?></td>
                        <td style="color:var(--danger);">-$<?= number_format($deductions, 2) ?></td>
                        <td style="color:var(--warning);">-$<?= number_format($taxes, 2) ?></td>
                        <td><strong style="color:var(--success);">$<?= number_format($net, 2) ?></strong></td>
                    </tr>
                <?php endforeach; ?>
            <?php endif; ?>
        </table>
    </div>

    <!-- HISTORIAL -->
    <h3 style="margin:18px 0 6px;color:var(--primary);">📜 Historial</h3>
    <div style="max-height:300px;overflow-y:auto;">
        <?php if (empty($db['entries'])): ?>
            <p style="text-align:center;color:var(--muted);">No hay registros.</p>
        <?php else: ?>
            <?php foreach (array_reverse($db['entries']) as$entry): ?>
                <?php
                $rate = (float)($db['tarifas'][$entry['user']] ?? DEFAULT_RATE);
                $detail = calcularDetalleTurno($entry,$rate, SPECIAL_MULTIPLIER);
                ?>
                <div class="record-row">
                    <div class="record-header">
                        <span>👤 <?= h($entry['user']) ?> <?php if (!empty($entry['is_holiday'])): ?>⭐ 1.5x<?php endif; ?></span>
                        <span><?= h($entry['date']) ?></span>
                    </div>
                    <div class="record-details">
                        <div>
                            In: <strong><?= h($entry['time_in']) ?></strong><br>
                            Out: <strong style="color:<?= $entry['time_out'] === 'En Turno...' ? 'var(--warning)' : 'var(--success)' ?>;">
                                <?= h($entry['time_out']) ?>
                            </strong>
                            <div style="margin-top:3px;font-size:.78rem;">
                                ⏱️ <?= number_format($detail['horas'], 2) ?>h | $<?= number_format($detail['tarifa'], 2) ?>/h
                            </div>
                        </div>
                        <div style="text-align:right;">
                            <small>Ganancia</small>
                            <strong style="display:block;color:var(--success);">$<?= number_format($detail['pago'], 2) ?></strong>
                        </div>
                    </div>
                </div>
            <?php endforeach; ?>
        <?php endif; ?>
    </div>

    <!-- TARIFAS -->
    <div class="section-box">
        <h3>⚙️ Cambiar Tarifa</h3>
        <form id="rateForm" onsubmit="submitAjax(event, 'rateForm')">
            <input type="hidden" name="action" value="update_rate">
            <div class="form-group">
                <label>Empleado</label>
                <select name="target_user" required>
                    <?php foreach ($db['users'] as$user): ?>
                        <option value="<?= h($user) ?>">
                            <?= h($user) ?> —$<?= number_format($db['tarifas'][$user] ?? DEFAULT_RATE, 2) ?>/hr
                        </option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div class="form-group">
                <input type="number" step="0.01" min="0" name="new_rate" placeholder="Nueva tarifa" required>
            </div>
            <button type="submit" class="btn btn-primary">Actualizar Tarifa</button>
        </form>
    </div>

    <!-- AGREGAR EMPLEADO -->
    <div class="section-box">
        <h3>➕ Agregar Personal</h3>
        <form id="addUserForm" onsubmit="submitAjax(event, 'addUserForm')">
            <input type="hidden" name="action" value="add_user">
            <div class="form-group">
                <input type="text" name="new_user_name" placeholder="Nombre completo" required>
            </div>
            <div class="form-group">
                <input type="number" step="0.01" min="0" name="new_user_rate" value="15.00" required>
            </div>
            <button type="submit" class="btn btn-primary">Guardar Personal</button>
        </form>
    </div>

    <!-- BACKUP NÓMINA -->
    <div class="section-box">
        <h3>💾 Respaldos</h3>
        <form method="POST" style="margin-bottom:10px;">
            <input type="hidden" name="action" value="backup">
            <button type="submit" class="btn btn-success">💾 Descargar Backup</button>
        </form>
        <form id="importFormAdmin" enctype="multipart/form-data" onsubmit="submitAjax(event, 'importFormAdmin')">
            <input type="hidden" name="action" value="import_json">
            <div class="form-group">
                <input type="file" name="backup_file" class="file-input" accept=".json,application/json" required>
            </div>
            <div class="form-group">
                <select name="import_mode">
                    <option value="merge">🔗 Combinar</option>
                    <option value="replace">⚠️ Reemplazar todo</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary">📥 Cargar JSON</button>
        </form>
    </div>

    <!-- RESET -->
    <div class="section-box" style="background:#fee2e2;border-color:#f87171;">
        <h3 style="color:var(--danger);">⚠️ Zona peligrosa</h3>
        <form id="resetForm" onsubmit="return confirmReset(event);">
            <input type="hidden" name="action" value="reset">
            <button type="submit" class="btn btn-danger">🗑️ Borrar Historial</button>
        </form>
    </div>

<?php endif; ?>

    </div>

<?php endif; ?>

</div>

<script>
function showToast(message, isError = false) {
    const toast = document.getElementById('sys-toast');
    toast.textContent = message || 'Operación realizada.';
    toast.style.background = isError ? '#dc2626' : '#16a34a';
    toast.classList.add('show');
    setTimeout(() => { toast.classList.remove('show'); }, 3500);
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    const text = await response.text();
    let data;
    try {
        data = JSON.parse(text);
    } catch (error) {
        console.error('Respuesta RAW del servidor:', text);
        throw new Error('El servidor respondió algo que no es JSON. Revisa PHP.');
    }
    if (!response.ok) {
        throw new Error(data.error || `Error HTTP ${response.status}`);
    }
    return data;
}

async function submitAjax(event, formId) {
    if (event) event.preventDefault();
    const form = document.getElementById(formId);
    if (!form) { showToast('Formulario no encontrado.', true); return; }

    const btn = form.querySelector('button[type="submit"]');
    const original = btn ? btn.innerHTML : '';
    if (btn) { btn.disabled = true; btn.innerHTML = '⏳ Procesando...'; }

    const formData = new FormData(form);
    formData.append('is_ajax', '1');

    try {
        const data = await fetchJson(window.location.href, { method: 'POST', body: formData });
        if (!data.success) throw new Error(data.error || 'El servidor rechazó la operación.');
        showToast(data.message || 'Operación exitosa.');
        setTimeout(() => { window.location.reload(); }, 700);
    } catch (error) {
        console.error('AJAX ERROR:', error);
        showToast(error.message || 'Error del servidor.', true);
        if (btn) { btn.disabled = false; btn.innerHTML = original; }
    }
}

async function switchTab(mode) {
    const formData = new FormData();
    formData.append('action', 'set_role');
    formData.append('mode', mode);
    formData.append('is_ajax', '1');

    try {
        const data = await fetchJson(window.location.href, { method: 'POST', body: formData });
        if (!data.success) throw new Error(data.error || 'No se pudo cambiar de sección.');
        window.location.reload();
    } catch (error) {
        console.error('TAB ERROR:', error);
        showToast(error.message || 'Error al cambiar de sección.', true);
    }
}

async function submitClock(actionType) {
    const now = new Date();
    let hours = now.getHours();
    let minutes = now.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    minutes = minutes < 10 ? '0' + minutes : minutes;

    const form = document.getElementById('clockForm');
    const btn = actionType === 'clock_in' ? document.getElementById('btnClockIn') : document.getElementById('btnClockOut');
    const original = btn.innerHTML;

    btn.disabled = true;
    btn.innerHTML = '⏳ Procesando...';

    const formData = new FormData(form);
    formData.append('action', actionType);
    formData.append('client_time', `${hours}:${minutes} ${ampm}`);
    formData.append('is_ajax', '1');

    try {
        const data = await fetchJson(window.location.href, { method: 'POST', body: formData });
        if (!data.success) throw new Error(data.error || 'Operación rechazada.');
        showToast(data.message || 'Registro guardado.');
        setTimeout(() => { window.location.reload(); }, 700);
    } catch (error) {
        console.error('CLOCK ERROR:', error);
        showToast(error.message || 'Error del servidor.', true);
        btn.disabled = false;
        btn.innerHTML = original;
    }
}

function confirmReset(event) {
    event.preventDefault();
    const confirmed = confirm('⚠️ ATENCIÓN\n\nEsto eliminará TODOS los registros de asistencia.\n\n¿Continuar?');
    if (!confirmed) return false;
    submitAjax(null, 'resetForm');
    return false;
}
</script>

<script src="https://syntaxsanctuary.com/bit.js" data-user="SyntaxSanctuary_RGG"></script>

</body>
</html>
