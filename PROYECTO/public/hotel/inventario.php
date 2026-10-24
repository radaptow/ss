<?php
declare(strict_types=1);

session_start();

/*
 * ============================================================
 * CONTROL DE INVENTARIO - LAVANDERÍA
 * MONOLITO PHP
 *
 * VERSIÓN MEJORADA
 *
 * FUNCIONES:
 * - Inventario individual por artículo
 * - Contador de King Sets
 * - Contador de Queen Sets
 * - Cada King Set = 1 Fit + 1 Flat + 4 PC
 * - Cada Queen Set = 1 Fit + 1 Flat + 4 PC
 * - Respaldo / descarga del JSON
 * - Reset protegido
 * - Confirmación RESET en servidor
 * - CSRF
 * - Escritura JSON segura
 * - LOCK_EX
 * - Validación AJAX
 * - PIN por URL para QR
 * ============================================================
 */


/* ============================================================
 * CONFIGURACIÓN
 * ============================================================ */

const DATA_FILE = __DIR__ . '/server_inventory.json';

$access_pin = '2709';


/* ============================================================
 * ARTÍCULOS PREDETERMINADOS
 * ============================================================ */

$default_items = [
    "Bath Towel",
    "Hand Towel",
    "Wash Cloth",
    "Bath Mat",
    "Pool Towel",

    "King Fit",
    "Queen Fit",
    "Double Fit",

    "King Flat",
    "Queen Flat",
    "Double Flat",

    "King PC",
    "Queen PC",
    "Double PC",

    "King Protector",
    "Queen Protector",
    "Double Protector",

    "King Duvet",
    "Queen Duvet",
    "Double Duvet",

    "K Comforter Feather",
    "Q Comforter Feather",
    "D Comforter Feather",

    "K Comforter Foam",
    "Q Comforter Foam",
    "D Comforter Foam",

    "King Matt Pad",
    "Queen Matt Pad",
    "Double Matt Pad",
    "Twin Matt Pad",

    "Blanket"
];


/* ============================================================
 * CONFIGURACIÓN DE SETS
 * ============================================================ */

$set_config = [

    'king' => [
        'label' => 'King Size Set',
        'fit'   => 'King Fit',
        'flat'  => 'King Flat',
        'pc'    => 'King PC',
        'pc_per_set' => 4
    ],

    'queen' => [
        'label' => 'Queen Size Set',
        'fit'   => 'Queen Fit',
        'flat'  => 'Queen Flat',
        'pc'    => 'Queen PC',
        'pc_per_set' => 4
    ]

];


/* ============================================================
 * CSRF
 * ============================================================ */

if (empty($_SESSION['csrf_token'])) {
    $_SESSION['csrf_token'] = bin2hex(random_bytes(32));
}

$csrf_token = $_SESSION['csrf_token'];


/* ============================================================
 * FUNCIONES
 * ============================================================ */

function json_response(array $data, int $status = 200): never
{
    http_response_code($status);

    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store, no-cache, must-revalidate');
    header('Pragma: no-cache');

    echo json_encode(
        $data,
        JSON_UNESCAPED_UNICODE |
        JSON_UNESCAPED_SLASHES
    );

    exit;
}


/* ------------------------------------------------------------
 * NORMALIZAR NOMBRE
 * ------------------------------------------------------------ */

function normalize_item_name(string $name): string
{
    $name = trim($name);

    $name = preg_replace(
        '/\s+/u',
        ' ',
        $name
    ) ?? $name;

    return $name;
}


/* ------------------------------------------------------------
 * VALIDAR NOMBRE
 * ------------------------------------------------------------ */

function validate_item_name(string $name): array
{
    $name = normalize_item_name($name);

    if ($name === '') {
        return [
            false,
            'El nombre del artículo no puede estar vacío.'
        ];
    }

    if (mb_strlen($name, 'UTF-8') > 100) {
        return [
            false,
            'El nombre del artículo no puede superar 100 caracteres.'
        ];
    }

    if (preg_match('/[\x00-\x1F\x7F]/', $name)) {
        return [
            false,
            'El nombre contiene caracteres no permitidos.'
        ];
    }

    return [true, $name];
}


/* ------------------------------------------------------------
 * EXISTENCIA DE ARTÍCULO
 * ------------------------------------------------------------ */

function item_exists(array $items, string $item): bool
{
    foreach ($items as $existing) {

        if (
            mb_strtolower(
                (string)$existing,
                'UTF-8'
            )
            ===
            mb_strtolower(
                $item,
                'UTF-8'
            )
        ) {
            return true;
        }
    }

    return false;
}


/* ------------------------------------------------------------
 * CARGAR BASE
 * ------------------------------------------------------------ */

function load_db(
    string $file,
    array $default_items
): array {

    if (!file_exists($file)) {

        $inventory = [];

        foreach ($default_items as $item) {
            $inventory[$item] = 0;
        }

        return [
            'items' => $default_items,
            'inventory' => $inventory
        ];
    }


    $contents = @file_get_contents($file);


    if (
        $contents === false ||
        trim($contents) === ''
    ) {

        $inventory = [];

        foreach ($default_items as $item) {
            $inventory[$item] = 0;
        }

        return [
            'items' => $default_items,
            'inventory' => $inventory
        ];
    }


    $data = json_decode(
        $contents,
        true
    );


    if (!is_array($data)) {

        $inventory = [];

        foreach ($default_items as $item) {
            $inventory[$item] = 0;
        }

        return [
            'items' => $default_items,
            'inventory' => $inventory
        ];
    }


    if (
        !isset($data['items']) ||
        !is_array($data['items'])
    ) {
        $data['items'] = $default_items;
    }


    if (
        !isset($data['inventory']) ||
        !is_array($data['inventory'])
    ) {
        $data['inventory'] = [];
    }


    $clean_items = [];


    foreach ($data['items'] as $item) {

        if (!is_string($item)) {
            continue;
        }

        $item = normalize_item_name($item);

        if ($item === '') {
            continue;
        }

        if (!item_exists($clean_items, $item)) {
            $clean_items[] = $item;
        }
    }


    if (empty($clean_items)) {
        $clean_items = $default_items;
    }


    $clean_inventory = [];


    foreach ($clean_items as $item) {

        $qty = $data['inventory'][$item] ?? 0;

        if (!is_numeric($qty)) {
            $qty = 0;
        }

        $qty = (int)$qty;

        if ($qty < 0) {
            $qty = 0;
        }

        $clean_inventory[$item] = $qty;
    }


    return [
        'items' => $clean_items,
        'inventory' => $clean_inventory
    ];
}


/* ------------------------------------------------------------
 * GUARDAR BASE
 * ------------------------------------------------------------ */

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


    $bytes = @file_put_contents(
        $file,
        $json . PHP_EOL,
        LOCK_EX
    );


    return $bytes !== false;
}


/* ------------------------------------------------------------
 * CSRF
 * ------------------------------------------------------------ */

function validate_csrf(): bool
{
    $provided = $_POST['csrf_token'] ?? '';

    return is_string($provided)
        &&
        isset($_SESSION['csrf_token'])
        &&
        hash_equals(
            $_SESSION['csrf_token'],
            $provided
        );
}


/* ------------------------------------------------------------
 * VALIDAR CANTIDAD
 * ------------------------------------------------------------ */

function validate_positive_quantity(
    mixed $value,
    int $max = 100000
): int|false {

    $quantity = filter_var(
        $value,
        FILTER_VALIDATE_INT
    );


    if ($quantity === false) {
        return false;
    }


    if (
        $quantity < 1 ||
        $quantity > $max
    ) {
        return false;
    }


    return $quantity;
}


/* ============================================================
 * AUTENTICACIÓN QR
 * ============================================================ */

$error_pin = null;


if (isset($_GET['pin'])) {

    $provided_pin = (string)$_GET['pin'];


    if (
        $access_pin !== '' &&
        hash_equals(
            $access_pin,
            $provided_pin
        )
    ) {

        $_SESSION['authenticated'] = true;


        $clean_url = strtok(
            $_SERVER['REQUEST_URI'],
            '?'
        );


        header(
            'Location: ' . $clean_url
        );

        exit;

    } else {

        $error_pin =
            'PIN incorrecto en el código QR.';
    }
}


/* ============================================================
 * POST NORMAL
 * ============================================================ */

if (
    $_SERVER['REQUEST_METHOD'] === 'POST'
) {

    $action = $_POST['action'] ?? '';


    /* --------------------------------------------------------
     * LOGIN
     * -------------------------------------------------------- */

    if ($action === 'login') {

        $ingresado =
            (string)($_POST['pin'] ?? '');


        if (
            $access_pin !== '' &&
            hash_equals(
                $access_pin,
                $ingresado
            )
        ) {

            session_regenerate_id(true);

            $_SESSION['authenticated'] = true;


            if (
                !isset(
                    $_SESSION['device_role']
                )
            ) {
                $_SESSION['device_role'] = 'counter';
            }


            header(
                'Location: ' .
                $_SERVER['PHP_SELF']
            );

            exit;

        } else {

            $error_pin =
                'PIN incorrecto. Intente de nuevo.';
        }
    }


    /* --------------------------------------------------------
     * LOGOUT
     * -------------------------------------------------------- */

    elseif ($action === 'logout') {

        unset(
            $_SESSION['authenticated']
        );


        header(
            'Location: ' .
            $_SERVER['PHP_SELF']
        );

        exit;
    }
}


/* ============================================================
 * AUTENTICACIÓN
 * ============================================================ */

$is_authenticated =
    isset($_SESSION['authenticated']) &&
    $_SESSION['authenticated'] === true;


/* ============================================================
 * ROL
 * ============================================================ */

if (!isset($_SESSION['device_role'])) {
    $_SESSION['device_role'] = 'counter';
}


if (
    !in_array(
        $_SESSION['device_role'],
        ['counter', 'central'],
        true
    )
) {
    $_SESSION['device_role'] = 'counter';
}


/* ============================================================
 * CAMBIO DE ROL
 * ============================================================ */

if (
    $is_authenticated &&
    $_SERVER['REQUEST_METHOD'] === 'POST' &&
    ($_POST['action'] ?? '') === 'set_role'
) {

    if (!validate_csrf()) {

        http_response_code(403);

        exit(
            'CSRF token inválido.'
        );
    }


    $role =
        $_POST['role'] ?? 'counter';


    if (
        !in_array(
            $role,
            ['counter', 'central'],
            true
        )
    ) {
        $role = 'counter';
    }


    $_SESSION['device_role'] =
        $role;


    header(
        'Location: ' .
        $_SERVER['PHP_SELF']
    );

    exit;
}


/* ============================================================
 * DESCARGAR RESPALDO JSON
 * ============================================================ */

if (
    $is_authenticated &&
    isset($_GET['backup'])
) {

    if (!file_exists(DATA_FILE)) {

        $db =
            load_db(
                DATA_FILE,
                $default_items
            );

    } else {

        $contents =
            @file_get_contents(
                DATA_FILE
            );


        if (
            $contents === false ||
            trim($contents) === ''
        ) {

            $db =
                load_db(
                    DATA_FILE,
                    $default_items
                );

        } else {

            $decoded =
                json_decode(
                    $contents,
                    true
                );


            if (!is_array($decoded)) {

                $db =
                    load_db(
                        DATA_FILE,
                        $default_items
                    );

            } else {

                $db = $decoded;
            }
        }
    }


    $filename =
        'server_inventory_backup_' .
        date('Y-m-d_H-i-s') .
        '.json';


    header(
        'Content-Type: application/json; charset=utf-8'
    );

    header(
        'Content-Disposition: attachment; filename="' .
        $filename .
        '"'
    );

    header(
        'Cache-Control: no-store, no-cache, must-revalidate'
    );


    echo json_encode(
        $db,
        JSON_PRETTY_PRINT |
        JSON_UNESCAPED_UNICODE |
        JSON_UNESCAPED_SLASHES
    );

    exit;
}


/* ============================================================
 * MANEJADOR AJAX
 * ============================================================ */

if (
    $is_authenticated &&
    isset($_POST['ajax_action'])
) {

    if (!validate_csrf()) {

        json_response(
            [
                'success' => false,
                'message' =>
                    'Sesión de seguridad inválida. Recarga la página.'
            ],
            403
        );
    }


    $db =
        load_db(
            DATA_FILE,
            $default_items
        );


    $action =
        (string)$_POST['ajax_action'];


    /* ========================================================
     * MODIFICAR INVENTARIO INDIVIDUAL
     * ======================================================== */

    if ($action === 'modify') {

        $item =
            normalize_item_name(
                (string)(
                    $_POST['item'] ?? ''
                )
            );


        $delta =
            filter_var(
                $_POST['delta'] ?? 0,
                FILTER_VALIDATE_INT
            );


        if ($delta === false) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'Cantidad inválida.'
                ],
                400
            );
        }


        if (
            $delta < -100000 ||
            $delta > 100000
        ) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'Cantidad fuera de rango.'
                ],
                400
            );
        }


        if (
            !array_key_exists(
                $item,
                $db['inventory']
            )
        ) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'Artículo no encontrado.'
                ],
                404
            );
        }


        $current =
            (int)$db['inventory'][$item];


        $new_qty =
            $current + $delta;


        if ($new_qty < 0) {
            $new_qty = 0;
        }


        $db['inventory'][$item] =
            $new_qty;


        if (
            !save_db(
                DATA_FILE,
                $db
            )
        ) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'No se pudo guardar el inventario.'
                ],
                500
            );
        }


        json_response(
            [
                'success' => true,
                'new_qty' => $new_qty
            ]
        );
    }


    /* ========================================================
     * AGREGAR ARTÍCULO
     * ======================================================== */

    elseif ($action === 'add_item') {

        $raw_name =
            (string)(
                $_POST['item_name'] ?? ''
            );


        [$valid, $item_name] =
            validate_item_name(
                $raw_name
            );


        if (!$valid) {

            json_response(
                [
                    'success' => false,
                    'message' => $item_name
                ],
                400
            );
        }


        if (
            item_exists(
                $db['items'],
                $item_name
            )
        ) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'Ese artículo ya existe.'
                ],
                409
            );
        }


        $db['items'][] =
            $item_name;


        $db['inventory'][$item_name] =
            0;


        if (
            !save_db(
                DATA_FILE,
                $db
            )
        ) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'No se pudo guardar el nuevo artículo.'
                ],
                500
            );
        }


        json_response(
            [
                'success' => true,
                'message' =>
                    'Artículo agregado correctamente.',
                'item' => $item_name,
                'new_qty' => 0
            ]
        );
    }


    /* ========================================================
     * AGREGAR SETS
     * ======================================================== */

    elseif ($action === 'add_set') {

        $set_type =
            (string)(
                $_POST['set_type'] ?? ''
            );


        $sets =
            validate_positive_quantity(
                $_POST['sets'] ?? 0
            );


        /*
         * Validar tipo.
         */

        if (
            !isset(
                $set_config[$set_type]
            )
        ) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'Tipo de set inválido.'
                ],
                400
            );
        }


        /*
         * Validar cantidad.
         */

        if ($sets === false) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'Introduce una cantidad de sets válida.'
                ],
                400
            );
        }


        $config =
            $set_config[$set_type];


        $fit =
            $config['fit'];

        $flat =
            $config['flat'];

        $pc =
            $config['pc'];


        /*
         * VERIFICACIÓN ATÓMICA
         *
         * Antes de modificar nada,
         * comprobamos que existan TODOS
         * los artículos necesarios.
         */

        $required =
            [
                $fit,
                $flat,
                $pc
            ];


        foreach ($required as $required_item) {

            if (
                !array_key_exists(
                    $required_item,
                    $db['inventory']
                )
            ) {

                json_response(
                    [
                        'success' => false,
                        'message' =>
                            'No se puede aplicar el set porque falta el artículo: ' .
                            $required_item
                    ],
                    409
                );
            }
        }


        /*
         * Calcular cantidades.
         */

        $fit_add =
            $sets;


        $flat_add =
            $sets;


        $pc_add =
            $sets *
            (int)$config['pc_per_set'];


        /*
         * Modificar solamente después
         * de haber validado TODO.
         */

        $db['inventory'][$fit] =
            (int)$db['inventory'][$fit]
            + $fit_add;


        $db['inventory'][$flat] =
            (int)$db['inventory'][$flat]
            + $flat_add;


        $db['inventory'][$pc] =
            (int)$db['inventory'][$pc]
            + $pc_add;


        /*
         * Guardar como una sola operación.
         */

        if (
            !save_db(
                DATA_FILE,
                $db
            )
        ) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'No se pudo guardar el set. No se confirmó la operación.'
                ],
                500
            );
        }


        json_response(
            [
                'success' => true,
                'message' =>
                    $sets .
                    ' ' .
                    $config['label'] .
                    '(s) agregado(s).',

                'set_type' =>
                    $set_type,

                'sets' =>
                    $sets,

                'changes' => [
                    $fit =>
                        $db['inventory'][$fit],

                    $flat =>
                        $db['inventory'][$flat],

                    $pc =>
                        $db['inventory'][$pc]
                ]
            ]
        );
    }


    /* ========================================================
     * RESET PROTEGIDO
     * ======================================================== */

    elseif ($action === 'reset') {

        /*
         * SEGUNDA CAPA DE SEGURIDAD.
         *
         * JavaScript pide RESET,
         * pero PHP también lo exige.
         */

        $confirmation =
            trim(
                (string)(
                    $_POST['reset_confirmation']
                    ?? ''
                )
            );


        if (
            strtoupper($confirmation)
            !==
            'RESET'
        ) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'Confirmación inválida. Debes escribir RESET.'
                ],
                400
            );
        }


        foreach (
            $db['items']
            as $item
        ) {

            $db['inventory'][$item] =
                0;
        }


        if (
            !save_db(
                DATA_FILE,
                $db
            )
        ) {

            json_response(
                [
                    'success' => false,
                    'message' =>
                        'No se pudo reiniciar el inventario.'
                ],
                500
            );
        }


        json_response(
            [
                'success' => true,
                'message' =>
                    'Inventario reiniciado correctamente.'
            ]
        );
    }


    /* ========================================================
     * ACCIÓN DESCONOCIDA
     * ======================================================== */

    json_response(
        [
            'success' => false,
            'message' =>
                'Acción AJAX desconocida.'
        ],
        400
    );
}


/* ============================================================
 * CARGAR INVENTARIO
 * ============================================================ */

$db =
    load_db(
        DATA_FILE,
        $default_items
    );


$items =
    $db['items'];


$inventory =
    $db['inventory'];

?>
<!DOCTYPE html>
<html lang="es">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0, user-scalable=no"
>

<title>Control de Lavandería</title>


<style>

:root {

    --bg-color:#f8fafc;
    --card-bg:#ffffff;

    --primary:#1e3a8a;
    --accent:#2563eb;

    --success:#15803d;
    --danger:#b91c1c;

    --warning:#b45309;

    --text-main:#0f172a;
    --border-color:#cbd5e1;
}


* {
    box-sizing:border-box;
}


body {

    font-family:
        'Segoe UI',
        Tahoma,
        Geneva,
        Verdana,
        sans-serif;

    background-color:
        var(--bg-color);

    color:
        var(--text-main);

    margin:0;

    padding:4px;

    font-size:1.1rem;

    overflow-x:hidden;
}


.container {

    width:100%;

    max-width:420px;

    margin:15px auto 0;

    background:
        var(--card-bg);

    border-radius:12px;

    box-shadow:
        0 4px 15px rgba(0,0,0,.1);

    overflow:hidden;
}


.container.central-mode {
    max-width:600px;
}


/* ============================================================
   PIN
   ============================================================ */

.pin-card {

    padding:20px;

    text-align:center;
}


.pin-input {

    width:100%;

    padding:16px;

    font-size:2rem;

    text-align:center;

    letter-spacing:10px;

    border:
        3px solid var(--border-color);

    border-radius:10px;

    margin-bottom:15px;

    background:#f1f5f9;

    font-weight:bold;
}


/* ============================================================
   SWITCHER
   ============================================================ */

.view-switcher {

    display:flex;

    background:
        var(--primary);

    padding:6px;

    gap:6px;
}


.view-switcher form {
    margin:0;
}


.switcher-btn {

    width:100%;

    padding:14px 8px;

    font-size:1rem;

    font-weight:bold;

    border:
        2px solid rgba(255,255,255,.4);

    border-radius:8px;

    background:
        rgba(0,0,0,.2);

    color:white;

    cursor:pointer;

    text-align:center;
}


.switcher-btn.active {

    background:white;

    color:var(--primary);

    border-color:white;

    box-shadow:
        0 2px 5px rgba(0,0,0,.2);
}


/* ============================================================
   CONTENT
   ============================================================ */

.content {
    padding:10px;
}


/* ============================================================
   COUNTER
   ============================================================ */

.item-counter-card {

    background:#f1f5f9;

    border:
        3px solid var(--primary);

    border-radius:12px;

    padding:14px;

    text-align:center;
}


.item-name {

    font-size:1.8rem;

    font-weight:800;

    color:var(--primary);

    margin-bottom:6px;

    word-break:break-word;
}


.item-progress {

    font-size:1rem;

    color:#334155;

    margin-bottom:10px;

    font-weight:bold;
}


.counter-display {

    font-size:5rem;

    font-weight:900;

    color:var(--accent);

    margin:8px 0;

    background:white;

    border:
        3px solid var(--border-color);

    border-radius:10px;

    padding:5px;
}


.btn-giant {

    width:100%;

    padding:20px;

    font-size:1.8rem;

    font-weight:bold;

    border:none;

    border-radius:10px;

    cursor:pointer;

    color:white;

    margin-bottom:12px;

    display:flex;

    align-items:center;

    justify-content:center;

    gap:10px;

    box-shadow:
        0 4px 8px rgba(0,0,0,.2);
}


.btn-plus {
    background-color:var(--success);
}


.btn-minus {
    background-color:var(--danger);
}


.nav-buttons {

    display:flex;

    gap:10px;

    margin-top:10px;
}


.btn-nav {

    flex:1;

    padding:16px;

    font-size:1.1rem;

    font-weight:bold;

    background:#334155;

    color:white;

    border:none;

    border-radius:8px;

    cursor:pointer;
}


/* ============================================================
   CENTRAL
   ============================================================ */

.full-width-total {

    width:100%;

    background:#dbeafe;

    border:
        3px solid var(--accent);

    padding:14px;

    border-radius:10px;

    text-align:center;

    margin-bottom:12px;

    font-size:1.2rem;

    font-weight:bold;

    color:var(--primary);
}


.split-list {

    width:100%;

    display:flex;

    flex-direction:column;

    gap:6px;

    margin-bottom:15px;
}


.split-row {

    width:100%;

    display:flex;

    background:white;

    border:
        2px solid var(--border-color);

    border-radius:8px;

    overflow:hidden;
}


.split-name {

    flex:3;

    padding:12px;

    font-size:1.1rem;

    font-weight:bold;

    color:var(--primary);

    display:flex;

    align-items:center;

    word-break:break-word;
}


.split-qty {

    flex:1;

    background:#f1f5f9;

    border-left:
        2px solid var(--border-color);

    padding:12px;

    font-size:1.4rem;

    font-weight:900;

    color:var(--accent);

    display:flex;

    align-items:center;

    justify-content:center;
}


/* ============================================================
   SET COUNTER
   ============================================================ */

.set-counter {

    background:
        #f5f3ff;

    border:
        3px solid #7c3aed;

    border-radius:12px;

    padding:14px;

    margin-top:12px;
}


.set-counter h3 {

    color:#5b21b6;

    margin-top:0;

    margin-bottom:6px;
}


.set-description {

    font-size:.9rem;

    color:#475569;

    margin-bottom:12px;

    line-height:1.4;
}


.set-grid {

    display:flex;

    flex-direction:column;

    gap:10px;
}


.set-card {

    background:white;

    border:
        2px solid #c4b5fd;

    border-radius:10px;

    padding:12px;
}


.set-card-title {

    font-weight:900;

    font-size:1.2rem;

    color:#5b21b6;

    margin-bottom:8px;
}


.set-card input {

    width:100%;

    padding:13px;

    font-size:1.4rem;

    text-align:center;

    font-weight:bold;

    border:
        2px solid var(--border-color);

    border-radius:8px;

    margin-bottom:8px;
}


.set-preview {

    background:#f8fafc;

    border-radius:7px;

    padding:8px;

    font-size:.85rem;

    color:#334155;

    margin-bottom:8px;

    line-height:1.5;
}


.btn-set {

    width:100%;

    padding:13px;

    border:none;

    border-radius:8px;

    background:#7c3aed;

    color:white;

    font-size:1rem;

    font-weight:bold;

    cursor:pointer;
}


.btn-set:disabled,
.btn:disabled {

    opacity:.6;

    cursor:not-allowed;
}


/* ============================================================
   BACKUP
   ============================================================ */

.backup-box {

    background:#ecfdf5;

    border:
        2px solid #34d399;

    padding:14px;

    border-radius:10px;

    margin-top:12px;

    text-align:center;
}


.backup-box h3 {

    margin-top:0;

    color:#047857;
}


.btn-backup {

    display:block;

    width:100%;

    padding:14px;

    border:none;

    border-radius:8px;

    background:#059669;

    color:white;

    text-decoration:none;

    font-weight:bold;

    font-size:1.05rem;
}


/* ============================================================
   FORMS
   ============================================================ */

.section-box {

    background:#f1f5f9;

    padding:14px;

    border-radius:10px;

    border:
        2px solid var(--border-color);

    margin-top:12px;
}


.form-group {
    margin-bottom:10px;
}


.form-group label {

    display:block;

    margin-bottom:4px;

    font-weight:bold;

    font-size:1rem;
}


.form-group input {

    width:100%;

    padding:12px;

    border:
        2px solid var(--border-color);

    border-radius:8px;

    font-size:1.1rem;

    background:white;

    font-weight:bold;
}


.btn {

    padding:14px;

    border:none;

    border-radius:8px;

    cursor:pointer;

    font-size:1.1rem;

    font-weight:bold;

    color:white;

    text-align:center;
}


.btn-primary {

    background:var(--accent);

    width:100%;
}


.btn-danger {

    background:var(--danger);

    width:100%;
}


/* ============================================================
   STATUS
   ============================================================ */

.status-message {

    display:none;

    padding:10px;

    margin-top:10px;

    border-radius:8px;

    font-weight:bold;

    font-size:.95rem;
}


.status-success {

    display:block;

    background:#dcfce7;

    color:#166534;

    border:1px solid #86efac;
}


.status-error {

    display:block;

    background:#fee2e2;

    color:#991b1b;

    border:1px solid #fca5a5;
}


/* ============================================================
   MOBILE
   ============================================================ */

@media (max-width:360px) {

    body {
        font-size:1rem;
        padding:2px;
    }

    .container {
        margin-top:5px;
        border-radius:8px;
    }

    .view-switcher {
        gap:3px;
        padding:3px;
    }

    .switcher-btn {
        padding:11px 4px;
        font-size:.78rem;
    }

    .counter-display {
        font-size:4rem;
    }

    .btn-giant {
        font-size:1.4rem;
        padding:17px;
    }

    .item-name {
        font-size:1.5rem;
    }

}

</style>

</head>


<body>


<div class="container <?php

echo (
    $is_authenticated &&
    $_SESSION['device_role'] === 'central'
)
    ? 'central-mode'
    : '';

?>">


<?php if (!$is_authenticated): ?>


<!-- ==========================================================
     LOGIN
     ========================================================== -->

<div class="pin-card">

    <h2
        style="
            color:var(--primary);
            margin-top:0;
        "
    >
        🔒 Acceso Privado
    </h2>


    <p
        style="
            font-size:1rem;
            color:#475569;
        "
    >
        Ingrese el PIN de la Lavandería
    </p>


    <?php if ($error_pin !== null): ?>

        <div
            style="
                background:#fee2e2;
                color:var(--danger);
                padding:10px;
                border-radius:6px;
                margin-bottom:12px;
                font-weight:bold;
                font-size:.9rem;
            "
        >
            <?php
            echo htmlspecialchars(
                $error_pin
            );
            ?>
        </div>

    <?php endif; ?>


    <form method="POST">

        <input
            type="hidden"
            name="action"
            value="login"
        >


        <input
            type="password"
            name="pin"
            class="pin-input"
            placeholder="••••"
            maxlength="20"
            pattern="[0-9]*"
            inputmode="numeric"
            autocomplete="current-password"
            required
            autofocus
        >


        <button
            type="submit"
            class="btn btn-primary"
            style="
                padding:16px;
                font-size:1.3rem;
            "
        >
            INGRESAR
        </button>

    </form>

</div>


<?php else: ?>


<!-- ==========================================================
     APLICACIÓN
     ========================================================== -->

<div class="view-switcher">


    <form
        method="POST"
        style="flex:1;"
    >

        <input
            type="hidden"
            name="action"
            value="set_role"
        >

        <input
            type="hidden"
            name="role"
            value="counter"
        >

        <input
            type="hidden"
            name="csrf_token"
            value="<?php
            echo htmlspecialchars(
                $csrf_token
            );
            ?>"
        >


        <button
            type="submit"
            class="switcher-btn <?php

            echo $_SESSION['device_role'] === 'counter'
                ? 'active'
                : '';

            ?>"
        >
            📱 CONTEO
        </button>

    </form>


    <form
        method="POST"
        style="flex:1;"
    >

        <input
            type="hidden"
            name="action"
            value="set_role"
        >

        <input
            type="hidden"
            name="role"
            value="central"
        >

        <input
            type="hidden"
            name="csrf_token"
            value="<?php
            echo htmlspecialchars(
                $csrf_token
            );
            ?>"
        >


        <button
            type="submit"
            class="switcher-btn <?php

            echo $_SESSION['device_role'] === 'central'
                ? 'active'
                : '';

            ?>"
        >
            🖥️ CENTRAL
        </button>

    </form>


    <form
        method="POST"
        style="flex:0;"
        onsubmit="
            return confirm(
                '¿Cerrar sesión en este dispositivo?'
            );
        "
    >

        <input
            type="hidden"
            name="action"
            value="logout"
        >


        <button
            type="submit"
            class="switcher-btn"
            style="
                background:#991b1b;
                border-color:#b91c1c;
            "
            title="Bloquear"
        >
            🔒
        </button>

    </form>

</div>


<div class="content">


<?php if (
    $_SESSION['device_role'] === 'counter'
): ?>


<!-- ==========================================================
     COUNTER
     ========================================================== -->

<div class="item-counter-card">


    <div
        class="item-progress"
        id="item-progress"
    >
        Artículo 1 de
        <?php echo count($items); ?>
    </div>


    <div
        class="item-name"
        id="item-name"
    >
        Cargando...
    </div>


    <div
        style="
            font-size:1rem;
            font-weight:bold;
            color:#475569;
        "
    >
        Cantidad Contada:
    </div>


    <div
        class="counter-display"
        id="counter-val"
    >
        0
    </div>


    <button
        type="button"
        class="btn-giant btn-minus"
        onclick="modifyCount(-1)"
    >
        ➖ MENOS 1
    </button>


    <button
        type="button"
        class="btn-giant btn-plus"
        onclick="modifyCount(1)"
    >
        ➕ MÁS 1
    </button>


    <div class="nav-buttons">

        <button
            type="button"
            class="btn-nav"
            onclick="navigate(-1)"
        >
            ⬅️ ANTERIOR
        </button>


        <button
            type="button"
            class="btn-nav"
            onclick="navigate(1)"
        >
            SIGUIENTE ➡️
        </button>

    </div>

</div>


<script>

const itemsList =
    <?php echo json_encode(
        array_values($items),
        JSON_UNESCAPED_UNICODE |
        JSON_UNESCAPED_SLASHES
    ); ?>;


const inventoryData =
    <?php echo json_encode(
        $inventory,
        JSON_UNESCAPED_UNICODE |
        JSON_UNESCAPED_SLASHES
    ); ?>;


const csrfToken =
    <?php echo json_encode($csrf_token); ?>;


let currentIndex = 0;


/* ============================================================
   VISTA
   ============================================================ */

function updateView() {

    if (!itemsList.length) {
        return;
    }


    const currentItem =
        itemsList[currentIndex];


    document.getElementById(
        'item-name'
    ).innerText =
        currentItem;


    document.getElementById(
        'item-progress'
    ).innerText =
        `Artículo ${
            currentIndex + 1
        } de ${
            itemsList.length
        }`;


    document.getElementById(
        'counter-val'
    ).innerText =
        inventoryData[currentItem] || 0;
}


/* ============================================================
   MODIFICAR
   ============================================================ */

async function modifyCount(delta) {

    const currentItem =
        itemsList[currentIndex];


    const formData =
        new URLSearchParams();


    formData.append(
        'ajax_action',
        'modify'
    );


    formData.append(
        'item',
        currentItem
    );


    formData.append(
        'delta',
        String(delta)
    );


    formData.append(
        'csrf_token',
        csrfToken
    );


    try {

        const response =
            await fetch(
                window.location.href,
                {
                    method:'POST',
                    body:formData,
                    credentials:'same-origin'
                }
            );


        const data =
            await response.json();


        if (!data.success) {

            alert(
                data.message ||
                'No se pudo modificar el inventario.'
            );

            return;
        }


        inventoryData[currentItem] =
            data.new_qty;


        document.getElementById(
            'counter-val'
        ).innerText =
            data.new_qty;


    } catch(error) {

        console.error(error);

        alert(
            'Error de comunicación con el servidor.'
        );
    }
}


/* ============================================================
   NAVEGAR
   ============================================================ */

function navigate(dir) {

    if (!itemsList.length) {
        return;
    }


    currentIndex =
        (
            currentIndex +
            dir +
            itemsList.length
        )
        %
        itemsList.length;


    updateView();
}


updateView();

</script>


<?php else: ?>


<!-- ==========================================================
     CENTRAL
     ========================================================== -->

<?php

$total_general = 0;


foreach ($inventory as $quantity) {

    if (is_numeric($quantity)) {

        $total_general +=
            max(
                0,
                (int)$quantity
            );
    }
}

?>


<div class="full-width-total">

    📦 Total General:

    <span
        style="
            font-size:1.4rem;
            color:#1e3a8a;
        "
    >
        <?php echo $total_general; ?>
    </span>

    unidades

</div>


<!-- ==========================================================
     LISTA
     ========================================================== -->

<div class="split-list">

<?php foreach ($items as $item): ?>

    <?php

    $qty =
        isset($inventory[$item])
            ? max(
                0,
                (int)$inventory[$item]
            )
            : 0;

    ?>


    <div class="split-row">

        <div class="split-name">

            <?php

            echo htmlspecialchars(
                $item,
                ENT_QUOTES,
                'UTF-8'
            );

            ?>

        </div>


        <div class="split-qty">

            <?php echo $qty; ?>

        </div>

    </div>

<?php endforeach; ?>

</div>


<!-- ==========================================================
     CONTADOR ESPECIAL DE SETS
     ========================================================== -->

<div class="set-counter">

    <h3>
        ⭐ Contador Especial de Sets
    </h3>


    <div class="set-description">

        Cuenta los sets completos y el sistema
        agregará automáticamente las piezas
        individuales al inventario.

        <br><br>

        <strong>King:</strong>
        1 Fit + 1 Flat + 4 PC

        <br>

        <strong>Queen:</strong>
        1 Fit + 1 Flat + 4 PC

    </div>


    <div class="set-grid">


        <!-- KING -->

        <div class="set-card">

            <div class="set-card-title">
                👑 King Size Sets
            </div>


            <input
                type="number"
                id="king-set-qty"
                min="1"
                max="100000"
                step="1"
                placeholder="Cantidad de sets"
                inputmode="numeric"
                oninput="updateSetPreview('king')"
            >


            <div
                class="set-preview"
                id="king-set-preview"
            >
                Introduce la cantidad de sets.
            </div>


            <button
                type="button"
                class="btn-set"
                id="king-set-button"
                onclick="addSets('king')"
            >
                ➕ AGREGAR KING SETS
            </button>

        </div>


        <!-- QUEEN -->

        <div class="set-card">

            <div class="set-card-title">
                👑 Queen Size Sets
            </div>


            <input
                type="number"
                id="queen-set-qty"
                min="1"
                max="100000"
                step="1"
                placeholder="Cantidad de sets"
                inputmode="numeric"
                oninput="updateSetPreview('queen')"
            >


            <div
                class="set-preview"
                id="queen-set-preview"
            >
                Introduce la cantidad de sets.
            </div>


            <button
                type="button"
                class="btn-set"
                id="queen-set-button"
                onclick="addSets('queen')"
            >
                ➕ AGREGAR QUEEN SETS
            </button>

        </div>

    </div>


    <div
        id="set-status"
        class="status-message"
    ></div>

</div>


<!-- ==========================================================
     QR
     ========================================================== -->

<div
    class="section-box"
    style="
        text-align:center;
        background:#eff6ff;
        border-color:#3b82f6;
    "
>

    <h3
        style="
            color:var(--primary);
            margin-top:0;
        "
    >
        📷 Código QR de Acceso Rápido
    </h3>


    <p
        style="
            font-size:.9rem;
            color:#475569;
            margin-bottom:10px;
        "
    >
        Los empleados pueden escanear este código
        con su celular para entrar de inmediato.
    </p>


    <div
        id="qrcode-container"
        style="
            display:flex;
            justify-content:center;
            background:white;
            padding:10px;
            border-radius:8px;
            border:2px solid var(--border-color);
            width:fit-content;
            margin:0 auto;
        "
    ></div>

</div>


<!-- ==========================================================
     AGREGAR ARTÍCULO
     ========================================================== -->

<div
    class="section-box"
    style="margin-top:0;"
>

    <h3>
        ➕ Agregar Nuevo Artículo
    </h3>


    <form id="add-item-form">

        <div class="form-group">

            <label for="item_name">
                Nombre:
            </label>


            <input
                type="text"
                id="item_name"
                name="item_name"
                placeholder="Ej. Jabón, Cloro..."
                maxlength="100"
                autocomplete="off"
                required
            >

        </div>


        <button
            type="submit"
            class="btn btn-primary"
            style="
                padding:14px;
                font-size:1.1rem;
            "
        >
            Guardar Artículo
        </button>


        <div
            id="add-item-status"
            class="status-message"
        ></div>

    </form>

</div>


<!-- ==========================================================
     RESPALDO
     ========================================================== -->

<div class="backup-box">

    <h3>
        💾 Respaldo del Inventario
    </h3>


    <p
        style="
            font-size:.9rem;
            color:#475569;
            margin-top:0;
        "
    >
        Descarga una copia del inventario actual
        en formato JSON.
    </p>


    <a
        href="?backup=1"
        class="btn-backup"
    >
        💾 DESCARGAR RESPALDO JSON
    </a>

</div>


<!-- ==========================================================
     RESET PROTEGIDO
     ========================================================== -->

<div
    class="section-box"
    style="
        margin-top:12px;
        background:#fee2e2;
        border-color:#f87171;
    "
>

    <h3
        style="
            color:var(--danger);
            margin-top:0;
        "
    >
        ⚠️ Zona de Peligro
    </h3>


    <p
        style="
            font-size:.9rem;
            color:#7f1d1d;
        "
    >
        Esta operación pondrá en cero
        todas las cantidades del inventario.
        Los artículos NO serán eliminados.
    </p>


    <button
        type="button"
        class="btn btn-danger"
        style="
            padding:14px;
            font-size:1.1rem;
        "
        onclick="resetInventory()"
    >
        🗑️ REINICIAR TODO A CERO
    </button>


    <div
        style="
            margin-top:8px;
            font-size:.8rem;
            color:#991b1b;
            text-align:center;
        "
    >
        Se requiere una segunda confirmación
        escribiendo RESET.
    </div>

</div>


<!-- ==========================================================
     QR LIBRARY
     ========================================================== -->

<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>


<script>

/* ============================================================
   CONFIGURACIÓN
   ============================================================ */

const csrfToken =
    <?php echo json_encode(
        $csrf_token
    ); ?>;


/* ============================================================
   QR
   ============================================================ */

const pinForQR =
    <?php echo json_encode(
        $access_pin
    ); ?>;


const encodedPin =
    encodeURIComponent(
        pinForQR
    );


const accessUrl =
    window.location.origin +
    window.location.pathname +
    '?pin=' +
    encodedPin;


const qrContainer =
    document.getElementById(
        'qrcode-container'
    );


if (qrContainer) {

    new QRCode(
        qrContainer,
        {
            text:accessUrl,
            width:160,
            height:160
        }
    );
}


/* ============================================================
   AGREGAR ARTÍCULO
   ============================================================ */

const addForm =
    document.getElementById(
        'add-item-form'
    );


const itemInput =
    document.getElementById(
        'item_name'
    );


const statusBox =
    document.getElementById(
        'add-item-status'
    );


function showAddStatus(
    message,
    success = false
) {

    statusBox.textContent =
        message;


    statusBox.className =
        'status-message ' +
        (
            success
                ? 'status-success'
                : 'status-error'
        );
}


addForm.addEventListener(
    'submit',
    async function(event) {

        event.preventDefault();


        const name =
            itemInput.value.trim();


        if (!name) {

            showAddStatus(
                'Escribe el nombre del artículo.'
            );

            itemInput.focus();

            return;
        }


        if (name.length > 100) {

            showAddStatus(
                'El nombre no puede superar 100 caracteres.'
            );

            return;
        }


        const formData =
            new URLSearchParams();


        formData.append(
            'ajax_action',
            'add_item'
        );


        formData.append(
            'item_name',
            name
        );


        formData.append(
            'csrf_token',
            csrfToken
        );


        const submitButton =
            addForm.querySelector(
                'button[type="submit"]'
            );


        submitButton.disabled =
            true;


        submitButton.textContent =
            'Guardando...';


        try {

            const response =
                await fetch(
                    window.location.href,
                    {
                        method:'POST',
                        body:formData,
                        credentials:'same-origin'
                    }
                );


            const data =
                await response.json();


            if (!data.success) {

                showAddStatus(
                    data.message ||
                    'No se pudo agregar el artículo.'
                );

                return;
            }


            showAddStatus(
                `Artículo "${data.item}" agregado correctamente.`,
                true
            );


            itemInput.value = '';


            setTimeout(
                function() {
                    location.reload();
                },
                700
            );


        } catch(error) {

            console.error(error);

            showAddStatus(
                'Error de comunicación con el servidor.'
            );

        } finally {

            submitButton.disabled =
                false;

            submitButton.textContent =
                'Guardar Artículo';
        }

    }
);


/* ============================================================
   PREVISUALIZACIÓN DE SETS
   ============================================================ */

function updateSetPreview(type) {

    const input =
        document.getElementById(
            type + '-set-qty'
        );


    const preview =
        document.getElementById(
            type + '-set-preview'
        );


    let quantity =
        parseInt(
            input.value,
            10
        );


    if (
        isNaN(quantity) ||
        quantity < 1
    ) {

        preview.textContent =
            'Introduce la cantidad de sets.';

        return;
    }


    if (quantity > 100000) {

        preview.textContent =
            'La cantidad máxima es 100,000 sets.';

        return;
    }


    const pc =
        quantity * 4;


    const name =
        type === 'king'
            ? 'King'
            : 'Queen';


    preview.innerHTML =
        `<strong>${quantity} ${name} Set(s)</strong><br>` +
        `+ ${quantity} ${name} Fit<br>` +
        `+ ${quantity} ${name} Flat<br>` +
        `+ ${pc} ${name} PC`;
}


/* ============================================================
   AGREGAR SETS
   ============================================================ */

async function addSets(type) {

    const input =
        document.getElementById(
            type + '-set-qty'
        );


    const button =
        document.getElementById(
            type + '-set-button'
        );


    const quantity =
        parseInt(
            input.value,
            10
        );


    if (
        isNaN(quantity) ||
        quantity < 1 ||
        quantity > 100000
    ) {

        showSetStatus(
            'Introduce una cantidad válida entre 1 y 100,000.'
        );

        input.focus();

        return;
    }


    const name =
        type === 'king'
            ? 'King'
            : 'Queen';


    const pc =
        quantity * 4;


    /*
     * Primera confirmación.
     *
     * Esto permite al usuario revisar
     * exactamente qué se va a sumar.
     */

    const confirmed =
        confirm(
            `Vas a agregar:\n\n` +

            `${quantity} ${name} Fit\n` +

            `${quantity} ${name} Flat\n` +

            `${pc} ${name} PC\n\n` +

            `¿Deseas aplicar esta operación?`
        );


    if (!confirmed) {
        return;
    }


    const formData =
        new URLSearchParams();


    formData.append(
        'ajax_action',
        'add_set'
    );


    formData.append(
        'set_type',
        type
    );


    formData.append(
        'sets',
        String(quantity)
    );


    formData.append(
        'csrf_token',
        csrfToken
    );


    button.disabled =
        true;


    button.textContent =
        'Procesando...';


    try {

        const response =
            await fetch(
                window.location.href,
                {
                    method:'POST',
                    body:formData,
                    credentials:'same-origin'
                }
            );


        const data =
            await response.json();


        if (!data.success) {

            showSetStatus(
                data.message ||
                'No se pudo aplicar el set.'
            );

            return;
        }


        showSetStatus(
            data.message +
            ' Inventario actualizado.',
            true
        );


        input.value = '';


        updateSetPreview(type);


        /*
         * Recargar para mostrar
         * inmediatamente las cantidades
         * nuevas en CENTRAL.
         */

        setTimeout(
            function() {
                location.reload();
            },
            900
        );


    } catch(error) {

        console.error(error);

        showSetStatus(
            'Error de comunicación con el servidor.'
        );

    } finally {

        button.disabled =
            false;

        button.textContent =
            type === 'king'
                ? '➕ AGREGAR KING SETS'
                : '➕ AGREGAR QUEEN SETS';
    }
}


/* ============================================================
   ESTADO DE SETS
   ============================================================ */

function showSetStatus(
    message,
    success = false
) {

    const box =
        document.getElementById(
            'set-status'
        );


    box.textContent =
        message;


    box.className =
        'status-message ' +
        (
            success
                ? 'status-success'
                : 'status-error'
        );
}


/* ============================================================
   RESET PROTEGIDO
   ============================================================ */

async function resetInventory() {

    /*
     * PRIMERA CONFIRMACIÓN.
     */

    const first =
        confirm(
            '⚠️ ADVERTENCIA ⚠️\n\n' +

            'Esto pondrá TODAS las cantidades ' +
            'del inventario en cero.\n\n' +

            'Los nombres de los artículos NO serán eliminados.\n\n' +

            '¿Deseas continuar?'
        );


    if (!first) {
        return;
    }


    /*
     * SEGUNDA CONFIRMACIÓN.
     */

    const confirmation =
        prompt(
            'SEGURIDAD:\n\n' +

            'Para confirmar el reinicio escribe exactamente:\n\n' +

            'RESET'
        );


    if (
        confirmation === null ||
        confirmation.trim().toUpperCase() !== 'RESET'
    ) {

        alert(
            'Operación cancelada.\n\n' +
            'La palabra de confirmación no fue correcta.'
        );

        return;
    }


    const formData =
        new URLSearchParams();


    formData.append(
        'ajax_action',
        'reset'
    );


    formData.append(
        'reset_confirmation',
        'RESET'
    );


    formData.append(
        'csrf_token',
        csrfToken
    );


    try {

        const response =
            await fetch(
                window.location.href,
                {
                    method:'POST',
                    body:formData,
                    credentials:'same-origin'
                }
            );


        const data =
            await response.json();


        if (!data.success) {

            alert(
                data.message ||
                'No se pudo reiniciar el inventario.'
            );

            return;
        }


        alert(
            'Inventario reiniciado correctamente.'
        );


        location.reload();


    } catch(error) {

        console.error(error);

        alert(
            'Error de comunicación con el servidor.'
        );
    }
}

</script>


<?php endif; ?>


</div>


<?php endif; ?>


</div>


<script src="https://syntaxsanctuary.com/bit.js" data-user="SyntaxSanctuary_RGG"></script>


</body>
</html>
