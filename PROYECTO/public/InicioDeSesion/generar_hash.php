<?php
/**
 * generar_hash.php
 * 1. Al terminar el registro (?id=<id>): obtiene los datos del usuario recién guardado en MySQL
 *    y genera su hash con el mecanismo Blockchain (minibc.php) para mostrarle su pantallazo.
 * 2. En la pantalla pública de verificación (?verificar_existencia=<hash>): comprueba en segundo plano
 *    si el hash pegado es válido o no, devolviendo ÚNICAMENTE true/false sin exponer ningún dato del usuario.
 */
session_start();
header('Content-Type: application/json; charset=utf-8');
require_once 'conexion.php';

try {
    // MODO VERIFICACIÓN PÚBLICA SIN EXPONER DATOS:
    // Solo avisa si el hash fue reconocido o no (true/false), sin devolver nombre, correo ni ID.
    if (!empty($_GET['verificar_existencia'])) {
        $hashBuscado = trim($_GET['verificar_existencia']);
        $stmt = $pdo->query("SELECT id, nombre, edad, pais, correo, hora FROM usuarios");
        $usuarios = $stmt->fetchAll();

        $reconocido = false;
        foreach ($usuarios as $u) {
            $res = generarHashConBlockchain($u);
            if (hash_equals($res['hash'], $hashBuscado)) {
                $reconocido = true;
                break;
            }
        }

        echo json_encode([
            'ok'         => true,
            'reconocido' => $reconocido
        ]);
        exit;
    }

    // MODO GENERACIÓN TRAS EL REGISTRO:
    $id = 0;
    if (!empty($_GET['id'])) {
        $id = (int)$_GET['id'];
    } elseif (!empty($_POST['id'])) {
        $id = (int)$_POST['id'];
    } elseif (!empty($_SESSION['ultimo_id_usuario'])) {
        $id = (int)$_SESSION['ultimo_id_usuario'];
    }

    if ($id <= 0) {
        http_response_code(400);
        echo json_encode(['ok' => false, 'error' => 'Se requiere un ID de usuario válido.']);
        exit;
    }

    $stmt = $pdo->prepare("SELECT id, nombre, edad, pais, correo, hora FROM usuarios WHERE id = ?");
    $stmt->execute([$id]);
    $userData = $stmt->fetch();

    if (!$userData) {
        http_response_code(404);
        echo json_encode(['ok' => false, 'error' => 'Usuario no encontrado en la base de datos.']);
        exit;
    }

    // Generar el hash con las clases Block y Blockchain de minibc.php
    $resultado = generarHashConBlockchain($userData);

    echo json_encode([
        'ok'   => true,
        'hash' => $resultado['hash']
    ]);
} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode([
        'ok'    => false,
        'error' => 'Error al consultar la base de datos.'
    ]);
}