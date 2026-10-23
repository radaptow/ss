<?php
/**
 * guardar_usuario.php
 * Recibe los datos del formulario vía Fetch (.js), los almacena en MySQL
 * y guarda el ID en sesión para que los siguientes pasos obtengan los datos automáticamente de la BD.
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

$usuario = trim($data['usuario'] ?? '');
$edad    = isset($data['edad']) ? (int)$data['edad'] : 0;
$pais    = trim($data['pais'] ?? '');
$correo  = trim($data['correo'] ?? '');
$hora    = trim($data['hora'] ?? '');
$pass    = $data['pass'] ?? '';

if ($usuario === '' || $edad <= 0 || $pais === '' || $correo === '' || $hora === '' || $pass === '') {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Todos los campos son obligatorios.']);
    exit;
}

try {
    // Sentencia preparada exacta solicitada
    $stmt = $pdo->prepare(
        'INSERT INTO usuarios (id, nombre, edad, pais, correo, hora, password) VALUES (null, :usuario, :edad, :pais, :correo, :hora, :pass)'
    );

    $stmt->execute([
        ':usuario' => $usuario,
        ':edad'    => $edad,
        ':pais'    => $pais,
        ':correo'  => $correo,
        ':hora'    => $hora,
        ':pass'    => $pass
    ]);

    $idInsertado = (int)$pdo->lastInsertId();

    // Guardamos el ID en la sesión para que la pantalla de verificación obtenga sus datos sin teclear nada
    $_SESSION['ultimo_id_usuario'] = $idInsertado;

    echo json_encode([
        'ok'      => true,
        'mensaje' => 'Usuario almacenado correctamente en la base de datos.',
        'id'      => $idInsertado
    ]);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode([
        'ok'    => false,
        'error' => 'Error al guardar en la base de datos: ' . $e->getMessage()
    ]);
}