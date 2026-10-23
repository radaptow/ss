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
    <title>Verificación de Hash Blockchain - Acceso Privado</title>
    <style>
        :root {
            --bg: #0f172a;
            --card: #1e293b;
            --primary: #10b981;
            --primary-hover: #059669;
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
            line-height: 1.45;
        }
        .form-group {
            margin-bottom: 1.25rem;
        }
        label {
            display: block;
            font-size: 0.85rem;
            margin-bottom: 0.5rem;
            color: #cbd5e1;
        }
        input.hash-input {
            width: 100%;
            padding: 0.85rem 0.95rem;
            border-radius: 8px;
            border: 1px solid #38bdf8;
            background: #0f172a;
            color: #38bdf8;
            font-family: monospace;
            font-size: 0.95rem;
        }
        input.hash-input:focus {
            outline: 2px solid var(--primary);
            border-color: transparent;
        }
        button.btn-primary {
            width: 100%;
            padding: 0.85rem;
            background: var(--primary);
            color: #052e16;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
        }
        button.btn-primary:hover {
            background: var(--primary-hover);
            color: white;
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
            margin-bottom: 1.25rem;
            font-size: 0.9rem;
            font-weight: 500;
        }
        .alerta.info { background: rgba(59, 130, 246, 0.15); color: #93c5fd; border: 1px solid #3b82f6; }
        .alerta.exito { background: rgba(16, 185, 129, 0.15); color: #6ee7b7; border: 1px solid #10b981; }
        .alerta.error { background: rgba(239, 68, 68, 0.15); color: #fca5a5; border: 1px solid #ef4444; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Paso 2: Verificación de Hash</h1>
        <p class="sub">
            Ingresa únicamente tu Hash Blockchain. El servidor recreará los bloques internamente desde la base de datos y te avisará si el hash es reconocido, sin exponer información personal en esta pantalla pública.
        </p>

        <div id="estadoMensaje" class="alerta"></div>

        <form id="formVerificar">
            <div class="form-group">
                <label for="hashGuardado">Clave o Código Secreto de Acceso (Hash):</label>
                <input type="text" id="hashGuardado" name="hash" class="hash-input" required autocomplete="off" placeholder="Pega aquí tu hash SHA-256 de 64 caracteres...">
            </div>

            <button type="submit" class="btn-primary">Verificar Hash y Entrar al Área Privada</button>
        </form>

        <div class="footer-link">
            <a href="index.php">← Volver al formulario de registro</a>
            <hr>
            <code>Ctrl + Shift + L</code>
        </div>
    </div>

    <script src="terminal_secreta_login.js"></script>
    <script src="app.js"></script>
</body>
</html>