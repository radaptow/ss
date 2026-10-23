<?php session_start();

if (!empty($_SESSION['usuario_id'])) {
    header('Location: area_privada.php');
    exit;
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Registro de Usuario - Hash Blockchain (LAMP)</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --text: #f8fafc;
            --muted: #94a3b8;
            --border: #334155;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: system-ui, -apple-system, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 1.5rem;
        }
        .card {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 14px;
            max-width: 520px;
            width: 100%;
            padding: 2rem;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.45);
        }
        h1 {
            margin-top: 0;
            font-size: 1.5rem;
            margin-bottom: 0.4rem;
        }
        p.sub {
            color: var(--muted);
            font-size: 0.9rem;
            margin-top: 0;
            margin-bottom: 1.5rem;
        }
        .form-group {
            margin-bottom: 1rem;
        }
        .form-row {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1rem;
        }
        label {
            display: block;
            font-size: 0.85rem;
            margin-bottom: 0.35rem;
            color: #cbd5e1;
        }
        input {
            width: 100%;
            padding: 0.7rem 0.85rem;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: #0f172a;
            color: var(--text);
            font-size: 0.95rem;
        }
        input:focus {
            outline: 2px solid var(--primary);
            border-color: transparent;
        }
        button.btn-primary {
            width: 100%;
            padding: 0.85rem;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            margin-top: 0.5rem;
        }
        button.btn-primary:hover {
            background: var(--primary-hover);
        }
        .footer-link {
            margin-top: 1.25rem;
            text-align: center;
            font-size: 0.9rem;
            color: var(--muted);
        }
        .footer-link a {
            color: #38bdf8;
            text-decoration: none;
            font-weight: 600;
        }
        .alerta {
            display: none;
            padding: 0.85rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            font-size: 0.9rem;
        }
        .alerta.info { background: rgba(59, 130, 246, 0.15); color: #93c5fd; border: 1px solid #3b82f6; }
        .alerta.exito { background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid #10b981; }
        .alerta.error { background: rgba(239, 68, 68, 0.15); color: #fca5a5; border: 1px solid #ef4444; }

        /* Modal Pantallazo para copiar el Hash */
        .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.82);
            display: none;
            justify-content: center;
            align-items: center;
            padding: 1.5rem;
            z-index: 50;
        }
        .modal-overlay.activo {
            display: flex;
        }
        .modal-content {
            background: var(--card);
            border: 1px solid #10b981;
            border-radius: 14px;
            max-width: 540px;
            width: 100%;
            padding: 2rem;
            text-align: center;
        }
        .hash-display {
            background: #090d16;
            border: 1px dashed #38bdf8;
            color: #38bdf8;
            font-family: monospace;
            padding: 1rem;
            border-radius: 8px;
            word-break: break-all;
            margin: 1.25rem 0;
            font-size: 0.95rem;
            user-select: all;
        }
        .modal-actions {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }
        .btn-copy {
            padding: 0.75rem;
            border-radius: 8px;
            border: 1px solid #38bdf8;
            background: rgba(56, 189, 248, 0.1);
            color: #38bdf8;
            font-weight: 600;
            cursor: pointer;
        }
        .btn-continue {
            padding: 0.85rem;
            border-radius: 8px;
            border: none;
            background: #10b981;
            color: #052e16;
            font-weight: 700;
            cursor: pointer;
            font-size: 0.95rem;
        }
    </style>
</head>
<body>
    <div class="card">
        <h1>Paso 1: Registro de Usuario</h1>
        <p class="sub">Almacena tus datos en MySQL y genera tu llave criptográfica con mecanismo Blockchain.</p>

        <div id="estadoMensaje" class="alerta"></div>

        <form id="formRegistro">
            <div class="form-group">
                <label for="usuario">Nombre de Usuario (:usuario)</label>
                <input type="text" id="usuario" name="usuario" required placeholder="Ej. Carlos Mendoza">
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label for="edad">Edad (:edad)</label>
                    <input type="number" id="edad" name="edad" min="1" max="120" required placeholder="Ej. 28">
                </div>
                <div class="form-group">
                    <label for="pais">País (:pais)</label>
                    <input type="text" id="pais" name="pais" required placeholder="Ej. México">
                </div>
            </div>

            <div class="form-row">
                <div class="form-group">
                    <label for="correo">Correo (:correo)</label>
                    <input type="email" id="correo" name="correo" required placeholder="usuario@correo.com">
                </div>
                <div class="form-group">
                    <label for="hora">Hora (:hora)</label>
                    <input type="time" id="hora" name="hora" required>
                </div>
            </div>

            <div class="form-group">
                <label for="pass">Contraseña (:pass)</label>
                <input type="password" id="pass" name="pass" required placeholder="Ingresa tu contraseña">
            </div>

            <button type="submit" class="btn-primary">Guardar Datos y Generar Hash Blockchain</button>
        </form>

        <div class="footer-link">
            ¿Ya estás registrado y tienes tu Hash? <a href="verificar.php">Ir al Login Multiusuario →</a>
        </div>
    </div>

    <!-- Pantallazo / Modal para que el usuario copie su Hash generado -->
    <div id="modalHash" class="modal-overlay">
        <div class="modal-content">
            <h2 style="margin-top: 0; color: #10b981;">¡Hash Blockchain Generado!</h2>
            <p style="color: var(--muted); font-size: 0.9rem;">
                Tus datos fueron almacenados y minados en una cadena de bloques. <strong>Copia y guarda este hash</strong>; lo necesitarás en la siguiente pantalla para ingresar al Área Privada.
            </p>
            <div id="hashGeneradoTexto" class="hash-display"></div>
            <div class="modal-actions">
                <button type="button" id="btnSoloCopiar" class="btn-copy">Copiar Hash al Portapapeles</button>
                <button type="button" id="btnCopiarYRedirigir" class="btn-continue">Copiar Hash e Ir a Pantalla de Verificación →</button>
            </div>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>