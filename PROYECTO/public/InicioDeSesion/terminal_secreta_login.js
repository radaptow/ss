/**
 * terminal_secreta_login.js
 * Mantiene completamente oculto el login por correo y contraseña.
 * - Al presionar la combinación de teclas `Ctrl + Shift + L` (o `Ctrl + Alt + T`),
 *   despliega una Terminal interactiva estilo consola Linux.
 * - El usuario debe teclear el comando `login` (o `sudo login` / `auth`) para desbloquear
 *   el formulario oculto de inicio de sesión por Correo/Usuario y Contraseña.
 *
 * Uso: Incluir <script src="terminal_secreta_login.js"></script> en verificar.html o index.html
 */

(function () {
    document.addEventListener('DOMContentLoaded', () => {
        // 1. Inyectar estilos aislados para la Terminal y el Formulario Oculto
        const style = document.createElement('style');
        style.textContent = `
            .sec-term-overlay {
                position: fixed;
                inset: 0;
                background: rgba(2, 6, 23, 0.88);
                backdrop-filter: blur(4px);
                display: none;
                justify-content: center;
                align-items: center;
                z-index: 9999;
                padding: 1.5rem;
            }
            .sec-term-overlay.visible {
                display: flex;
            }
            .sec-term-window {
                background: #090d16;
                border: 1px solid #10b981;
                border-radius: 10px;
                width: 100%;
                max-width: 620px;
                box-shadow: 0 25px 50px -12px rgba(16, 185, 129, 0.25);
                overflow: hidden;
                font-family: 'Courier New', Courier, monospace;
            }
            .sec-term-header {
                background: #111827;
                padding: 0.6rem 1rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid #1f2937;
            }
            .sec-term-dots {
                display: flex;
                gap: 6px;
            }
            .sec-term-dot {
                width: 11px;
                height: 11px;
                border-radius: 50%;
            }
            .sec-term-title {
                color: #9ca3af;
                font-size: 0.8rem;
            }
            .sec-term-close {
                background: transparent;
                border: none;
                color: #9ca3af;
                cursor: pointer;
                font-size: 1rem;
            }
            .sec-term-body {
                padding: 1.15rem;
                color: #10b981;
                font-size: 0.9rem;
                max-height: 240px;
                overflow-y: auto;
                line-height: 1.5;
            }
            .sec-term-line {
                margin-bottom: 0.35rem;
                word-break: break-word;
            }
            .sec-term-line.cmd { color: #38bdf8; }
            .sec-term-line.warn { color: #fbbf24; }
            .sec-term-line.err { color: #f87171; }
            .sec-term-input-row {
                display: flex;
                align-items: center;
                padding: 0.65rem 1.15rem;
                border-top: 1px solid #1f2937;
                background: #050811;
            }
            .sec-term-prompt {
                color: #10b981;
                font-weight: bold;
                margin-right: 0.5rem;
                white-space: nowrap;
                font-size: 0.9rem;
            }
            .sec-term-input {
                flex: 1;
                background: transparent;
                border: none;
                color: #f8fafc;
                font-family: inherit;
                font-size: 0.9rem;
                outline: none;
            }
            /* Formulario de Login Oculto dentro de la Terminal (se revela solo con el comando) */
            .sec-login-drawer {
                display: none;
                background: #111827;
                border-top: 1px dashed #38bdf8;
                padding: 1.25rem;
                font-family: system-ui, -apple-system, sans-serif;
            }
            .sec-login-drawer.desbloqueado {
                display: block;
            }
            .sec-login-drawer h4 {
                margin: 0 0 0.85rem 0;
                color: #38bdf8;
                font-size: 1rem;
            }
            .sec-login-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 0.85rem;
                margin-bottom: 0.85rem;
            }
            .sec-login-grid input {
                width: 100%;
                padding: 0.65rem 0.75rem;
                border-radius: 6px;
                border: 1px solid #374151;
                background: #090d16;
                color: #f8fafc;
                font-size: 0.9rem;
                box-sizing: border-box;
            }
            .sec-login-btn {
                width: 100%;
                padding: 0.7rem;
                background: #38bdf8;
                color: #090d16;
                border: none;
                border-radius: 6px;
                font-weight: 700;
                cursor: pointer;
                font-size: 0.9rem;
            }
            .sec-login-btn:hover {
                background: #0284c7;
                color: #ffffff;
            }
        `;
        document.head.appendChild(style);

        // 2. Crear el DOM de la Terminal Secreta
        const overlay = document.createElement('div');
        overlay.className = 'sec-term-overlay';
        overlay.id = 'secTermOverlay';
        overlay.innerHTML = `
            <div class="sec-term-window">
                <div class="sec-term-header">
                    <div class="sec-term-dots">
                        <span class="sec-term-dot" style="background:#ef4444"></span>
                        <span class="sec-term-dot" style="background:#f59e0b"></span>
                        <span class="sec-term-dot" style="background:#10b981"></span>
                    </div>
                    <span class="sec-term-title">root@syntax-sanctuary:~ (Ctrl+Shift+L)</span>
                    <button type="button" class="sec-term-close" id="secTermClose" title="Cerrar (Esc)">✕</button>
                </div>
                <div class="sec-term-body" id="secTermOutput">
                    <div class="sec-term-line">Syntax Sanctuary Secure Shell v2.4 [LAMP Stack]</div>
                    <div class="sec-term-line warn">Escribe <strong>help</strong> para ver los comandos o <strong>login</strong> para desbloquear el acceso por correo y contraseña.</div>
                </div>
                <div class="sec-term-input-row">
                    <span class="sec-term-prompt">guest@lamp:~$</span>
                    <input type="text" class="sec-term-input" id="secTermInput" autocomplete="off" placeholder="Escribe un comando (ej. login)...">
                </div>
                <div class="sec-login-drawer" id="secLoginDrawer">
                    <h4>🔓 Acceso Desbloqueado: Correo / Usuario + Contraseña</h4>
                    <form id="secLoginForm">
                        <div class="sec-login-grid">
                            <input type="text" id="secIdentificador" required placeholder="Correo o Nombre de Usuario">
                            <input type="password" id="secPassword" required placeholder="Contraseña">
                        </div>
                        <button type="submit" class="sec-login-btn">Autenticar con Contraseña Hasheada →</button>
                    </form>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        const termOutput = document.getElementById('secTermOutput');
        const termInput = document.getElementById('secTermInput');
        const loginDrawer = document.getElementById('secLoginDrawer');
        const loginForm = document.getElementById('secLoginForm');
        const btnClose = document.getElementById('secTermClose');

        // 3. Escuchar combinación de teclas: Ctrl + Shift + L (o Ctrl + Alt + T)
        document.addEventListener('keydown', (e) => {
            const esCtrlShiftL = e.ctrlKey && e.shiftKey && (e.key === 'L' || e.key === 'l');
            const esCtrlAltT = e.ctrlKey && e.altKey && (e.key === 'T' || e.key === 't');

            if (esCtrlShiftL || esCtrlAltT) {
                e.preventDefault();
                alternarTerminal();
            } else if (e.key === 'Escape' && overlay.classList.contains('visible')) {
                cerrarTerminal();
            }
        });

        btnClose.addEventListener('click', cerrarTerminal);

        // 4. Procesar los comandos escritos en la terminal
        termInput.addEventListener('keydown', (e) => {
            if (e.key !== 'Enter') return;
            e.preventDefault();

            const rawCmd = termInput.value.trim();
            termInput.value = '';
            if (!rawCmd) return;

            imprimirLinea(`guest@lamp:~$ ${rawCmd}`, 'cmd');
            const cmd = rawCmd.toLowerCase();

            if (cmd === 'help' || cmd === '?') {
                imprimirLinea('Comandos disponibles:');
                imprimirLinea('  login       -> Desbloquea el formulario oculto de Correo y Contraseña');
                imprimirLinea('  sudo login  -> Acceso directo al módulo de credenciales');
                imprimirLinea('  clear       -> Limpia la pantalla de la terminal');
                imprimirLinea('  exit        -> Oculta la terminal y el formulario');
                imprimirLinea('  redirect    -> Inicia cuenta regresiva y redirige a localhost');
            } else if (cmd === 'login' || cmd === 'sudo login' || cmd === 'auth' || cmd === 'auth --user') {
                imprimirLinea('[OK] Verificando privilegios... Módulo de credenciales desbloqueado.');
                loginDrawer.classList.add('desbloqueado');
                setTimeout(() => {
                    document.getElementById('secIdentificador').focus();
                }, 80);
            } else if (cmd === 'clear' || cmd === 'cls') {
                termOutput.innerHTML = '';
            } else if (cmd === 'exit' || cmd === 'quit') {
                cerrarTerminal();
            } else if (cmd === 'redirect' || cmd === 'redir') {
                let segundos = 10;
                imprimirLinea(`[INFO] Iniciando redirección a syntaxsanctuary.com en ${segundos} segundos...`);
                
                const timer = setInterval(() => {
                    segundos--;
                    if (segundos > 0) {
                        imprimirLinea(`Redirigiendo en ${segundos}...`);
                    } else {
                        clearInterval(timer);
                        imprimirLinea('¡Redirigiendo ahora...');
                        // Puedes cambiar 'http://localhost' por la ruta específica que necesites
                        window.location.href = 'https://syntaxsanctuary.com/'; 
                    }
                }, 1000);
        }else {
                imprimirLinea(`bash: ${rawCmd}: comando no encontrado. Escribe 'login' o 'help'.`, 'err');
            }
        });

        // 5. Enviar el formulario oculto a auth_credenciales.php
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const identificador = document.getElementById('secIdentificador').value.trim();
            const password = document.getElementById('secPassword').value;

            imprimirLinea(`[AUTH] Validando credenciales para '${identificador}' en MySQL...`, 'warn');

            try {
                const resp = await fetch('auth_credenciales.php', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        accion: 'login_credenciales',
                        identificador: identificador,
                        password: password
                    })
                });
                const data = await resp.json();

                if (!resp.ok || !data.ok) {
                    throw new Error(data.error || 'Credenciales inválidas.');
                }

                imprimirLinea(data.mensaje);
                setTimeout(() => {
                    window.location.href = data.redirect || 'area_privada.php';
                }, 650);
            } catch (err) {
                imprimirLinea(`[ERROR] ${err.message}`, 'err');
            }
        });

        function alternarTerminal() {
            const abierta = overlay.classList.toggle('visible');
            if (abierta) {
                setTimeout(() => termInput.focus(), 60);
            } else {
                loginDrawer.classList.remove('desbloqueado');
            }
        }

        function cerrarTerminal() {
            overlay.classList.remove('visible');
            loginDrawer.classList.remove('desbloqueado');
        }

        function imprimirLinea(texto, clase = '') {
            const div = document.createElement('div');
            div.className = 'sec-term-line ' + clase;
            div.textContent = texto;
            termOutput.appendChild(div);
            termOutput.scrollTop = termOutput.scrollHeight;
        }
    });
})();