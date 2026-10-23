<?php
/**
 * validar_acceso.php
 * Recibe únicamente el hash pegado por el usuario en la pantalla pública.
 * Obtiene internamente los registros de la BD, recrea el hash Blockchain de cada uno y los compara.
 * No expone ningún dato personal en la respuesta pública: solo informa si el hash fue reconocido
 * y guarda en sesión el ID exclusivo de ese hash para el Área Privada.
 */
session_start();
header('Content-Type: application/json; charset=utf-8');
require_once 'conexion.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['ok' => false, 'error' => 'Método no permitido. Usa POST.']);
    exit;
}

$inputJSON = file_get_contents('php://input');
$data = json_decode($inputJSON, true);
if (!is_array($data)) {
    $data = $_POST;
}

$hashIngresado = trim($data['hash'] ?? '');

if ($hashIngresado === '') {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Por favor pega tu hash de acceso.']);
    exit;
}

try {
    $stmtTodos = $pdo->query("SELECT id, nombre, edad, pais, correo, hora FROM usuarios");
    $todosLosUsuarios = $stmtTodos->fetchAll();

    $usuarioAutenticado = null;
    $hashRecreadoExitoso = '';

    foreach ($todosLosUsuarios as $filaUsuario) {
        $resultado = generarHashConBlockchain($filaUsuario);
        if (hash_equals($resultado['hash'], $hashIngresado)) {
            $usuarioAutenticado = $filaUsuario;
            $hashRecreadoExitoso = $resultado['hash'];
            break;
        }
    }

    if ($usuarioAutenticado) {
        // Regeneramos el ID de sesión por seguridad y vinculamos la sesión ÚNICAMENTE al dueño de este hash
        session_regenerate_id(true);
        $_SESSION['acceso_autorizado'] = true;
        $_SESSION['usuario_id']        = (int)$usuarioAutenticado['id'];
        $_SESSION['usuario']           = $usuarioAutenticado['nombre'];
        $_SESSION['hash_verificado']   = $hashRecreadoExitoso;

        // En el área pública solo respondemos que fue reconocido sin filtrar datos personales
        echo json_encode([
            'ok'       => true,
            'acceso'   => true,
            'mensaje'  => '✓ Hash reconocido correctamente. Ingresando a tu Área Privada...',
            'redirect' => 'area_privada.php'
        ]);
    } else {
        http_response_code(401);
        echo json_encode([
            'ok'     => false,
            'acceso' => false,
            'error'  => '✕ Hash no reconocido. Verifica que hayas pegado tu clave completa.'
        ]);
    }
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode([
        'ok'    => false,
        'error' => 'Error interno al verificar el hash.'
    ]);
}