<?php
/**
 * auth_credenciales.php
 * Endpoint modular para:
 * 1. (accion = 'guardar_credenciales'): En el Área Privada, permite al usuario autenticado actualizar/generar
 *    su nombre de usuario, correo y contraseña guardándola en HASH (password_hash / SHA-256) en la misma tabla `usuarios`.
 * 2. (accion = 'login_credenciales'): Autentica desde el formulario oculto de la Terminal Secreta usando
 *    correo (o usuario) + contraseña, verifica el hash de la contraseña, genera su sesión Blockchain y da acceso a `area_privada.php`.
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

$accion = $data['accion'] ?? '';

try {
    // =========================================================================
    // ACCIÓN 1: Guardar / Actualizar Usuario, Correo y Contraseña Hasheada (Desde Área Privada)
    // =========================================================================
    if ($accion === 'guardar_credenciales') {
        if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id'])) {
            http_response_code(401);
            echo json_encode(['ok' => false, 'error' => 'Sesión no autorizada.']);
            exit;
        }

        $usuarioId   = (int)$_SESSION['usuario_id'];
        $nuevoNombre = trim($data['usuario'] ?? '');
        $nuevoCorreo = trim($data['correo'] ?? '');
        $nuevaPass   = $data['password'] ?? '';

        if ($nuevoNombre === '' || $nuevoCorreo === '' || $nuevaPass === '') {
            http_response_code(400);
            echo json_encode(['ok' => false, 'error' => 'Completa el usuario, correo y la nueva contraseña.']);
            exit;
        }

        // Hasheamos la contraseña con BCRYPT seguro de PHP (password_hash)
        $passwordHasheada = password_hash($nuevaPass, PASSWORD_DEFAULT);

        $stmtUpdate = $pdo->prepare(
            "UPDATE usuarios SET nombre = :nombre, correo = :correo, password = :pass WHERE id = :id"
        );
        $stmtUpdate->execute([
            ':nombre' => $nuevoNombre,
            ':correo' => $nuevoCorreo,
            ':pass'   => $passwordHasheada,
            ':id'     => $usuarioId
        ]);

        // Obtenemos los datos actualizados para recalcular el hash del bloque en sesión
        $stmtUser = $pdo->prepare("SELECT id, nombre, edad, pais, correo, hora FROM usuarios WHERE id = ? LIMIT 1");
        $stmtUser->execute([$usuarioId]);
        $usuarioActualizado = $stmtUser->fetch();

        $nuevoBloque = generarHashConBlockchain($usuarioActualizado);
        $_SESSION['usuario']         = $usuarioActualizado['nombre'];
        $_SESSION['hash_verificado'] = $nuevoBloque['hash'];

        echo json_encode([
            'ok'               => true,
            'mensaje'          => '✓ Credenciales actualizadas y contraseña guardada en formato Hash.',
            'hash_contrasena'  => $passwordHasheada,
            'nuevo_hash_block' => $nuevoBloque['hash'],
            'usuario'          => [
                'nombre' => $usuarioActualizado['nombre'],
                'correo' => $usuarioActualizado['correo']
            ]
        ]);
        exit;
    }

    // =========================================================================
    // ACCIÓN 2: Iniciar Sesión desde la Terminal Secreta con Correo/Usuario + Password
    // =========================================================================
    if ($accion === 'login_credenciales') {
        $identificador = trim($data['identificador'] ?? ''); // Puede ser el correo o el nombre de usuario
        $passwordInput = $data['password'] ?? '';

        if ($identificador === '' || $passwordInput === '') {
            http_response_code(400);
            echo json_encode(['ok' => false, 'error' => 'Ingresa tu correo/usuario y contraseña.']);
            exit;
        }

        // Buscamos al usuario por correo o por nombre en la misma tabla `usuarios`
        $stmt = $pdo->prepare(
            "SELECT id, nombre, edad, pais, correo, hora, password FROM usuarios WHERE correo = :id1 OR nombre = :id2 LIMIT 1"
        );
        $stmt->execute([
            ':id1' => $identificador,
            ':id2' => $identificador
        ]);
        $usuario = $stmt->fetch();

        if (!$usuario) {
            http_response_code(401);
            echo json_encode(['ok' => false, 'error' => 'Acceso denegado: Usuario o correo no encontrado.']);
            exit;
        }

        $passGuardada = $usuario['password'];
        $passwordValida = false;

        // 1. Verificar si está hasheada con password_hash() (Bcrypt/Argon2)
        if (password_verify($passwordInput, $passGuardada)) {
            $passwordValida = true;
        }
        // 2. Verificar si fue guardada como SHA-256 directo
        elseif (hash_equals($passGuardada, hash('sha256', $passwordInput))) {
            $passwordValida = true;
        }
        // 3. Compatibilidad si el registro inicial guardó el password en texto plano (y lo migramos a hash automáticamente)
        elseif (hash_equals($passGuardada, $passwordInput)) {
            $passwordValida = true;
            $nuevoHashPass = password_hash($passwordInput, PASSWORD_DEFAULT);
            $stmtMigrar = $pdo->prepare("UPDATE usuarios SET password = ? WHERE id = ?");
            $stmtMigrar->execute([$nuevoHashPass, $usuario['id']]);
        }

        if (!$passwordValida) {
            http_response_code(401);
            echo json_encode(['ok' => false, 'error' => 'Acceso denegado: Contraseña incorrecta.']);
            exit;
        }

        // Calculamos el hash Blockchain correspondiente a este usuario para su sesión en el Área Privada
        $bloqueUsuario = generarHashConBlockchain($usuario);

        session_regenerate_id(true);
        $_SESSION['acceso_autorizado'] = true;
        $_SESSION['usuario_id']        = (int)$usuario['id'];
        $_SESSION['usuario']           = $usuario['nombre'];
        $_SESSION['hash_verificado']   = $bloqueUsuario['hash'];

        echo json_encode([
            'ok'       => true,
            'mensaje'  => '✓ Autenticación exitosa. Redirigiendo a tu Área Privada...',
            'redirect' => 'area_privada.php'
        ]);
        exit;
    }

    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Acción no reconocida.']);

} catch (PDOException $e) {
    http_response_code(500);
    echo json_encode(['ok' => false, 'error' => 'Error interno en la base de datos.']);
}