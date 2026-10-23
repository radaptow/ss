/**
 * ui_credenciales_privada.js
 * Genera e incrusta dinámicamente una interfaz gráfica dentro de `area_privada.php`
 * para que el usuario que inició sesión pueda configurar/actualizar su usuario, correo
 * y contraseña (que se almacena en HASH en la misma tabla `usuarios` de MySQL).
 *
 * Uso: Incluir <script src="ui_credenciales_privada.js"></script> al final de area_privada.php
 */

(function () {
    document.addEventListener('DOMContentLoaded', () => {
        const contenedorPrincipal = document.querySelector('.container') || document.body;

        // 1. Inyectar estilos encapsulados para no ensuciar el CSS existente
        const estilos = document.createElement('style');
        estilos.textContent = `
            .cred-widget-wrapper {
                margin-top: 2rem;
                padding-top: 1.5rem;
                border-top: 1px dashed #334155;
            }
            .cred-toggle-btn {
                background: rgba(56, 189, 248, 0.12);
                color: #38bdf8;
                border: 1px solid #38bdf8;
                padding: 0.65rem 1.15rem;
                border-radius: 8px;
                font-size: 0.9rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .cred-toggle-btn:hover {
                background: #38bdf8;
                color: #0f172a;
            }
            .cred-panel {
                display: none;
                margin-top: 1.25rem;
                background: rgba(15, 23, 42, 0.75);
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 1.5rem;
            }
            .cred-panel.abierto {
                display: block;
            }
            .cred-panel h4 {
                margin: 0 0 0.35rem 0;
                font-size: 1.15rem;
                color: #f8fafc;
            }
            .cred-panel p.cred-desc {
                margin: 0 0 1.25rem 0;
                font-size: 0.85rem;
                color: #94a3b8;
            }
            .cred-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 1rem;
                margin-bottom: 1rem;
            }
            .cred-field label {
                display: block;
                font-size: 0.8rem;
                color: #cbd5e1;
                margin-bottom: 0.35rem;
            }
            .cred-field input {
                width: 100%;
                padding: 0.65rem 0.8rem;
                border-radius: 8px;
                border: 1px solid #334155;
                background: #090d16;
                color: #f8fafc;
                font-size: 0.9rem;
                box-sizing: border-box;
            }
            .cred-field input:focus {
                outline: 2px solid #38bdf8;
                border-color: transparent;
            }
            .cred-submit-btn {
                background: #10b981;
                color: #052e16;
                border: none;
                padding: 0.75rem 1.35rem;
                border-radius: 8px;
                font-weight: 700;
                cursor: pointer;
                font-size: 0.9rem;
            }
            .cred-submit-btn:hover {
                background: #059669;
                color: #ffffff;
            }
            .cred-msg {
                display: none;
                margin-top: 1rem;
                padding: 0.75rem;
                border-radius: 8px;
                font-size: 0.85rem;
                word-break: break-all;
            }
            .cred-msg.ok {
                display: block;
                background: rgba(16, 185, 129, 0.15);
                border: 1px solid #10b981;
                color: #6ee7b7;
            }
            .cred-msg.err {
                display: block;
                background: rgba(239, 68, 68, 0.15);
                border: 1px solid #ef4444;
                color: #fca5a5;
            }
        `;
        document.head.appendChild(estilos);

        // 2. Tomar los valores actuales de la fila de la tabla para pre-llenar usuario y correo
        const celdas = document.querySelectorAll('#tabla tbody tr td');
        const nombreActual = celdas.length > 1 ? celdas[1].textContent.trim() : '';
        const correoActual = celdas.length > 4 ? celdas[4].textContent.trim() : '';

        // 3. Construir la interfaz gráfica e incrustarla en el Área Privada
        const wrapper = document.createElement('div');
        wrapper.className = 'cred-widget-wrapper';
        wrapper.innerHTML = `
            <button type="button" class="cred-toggle-btn" id="btnToggleCredenciales">
                🔐 Configurar Acceso por Correo y Contraseña Hasheada
            </button>
            <div class="cred-panel" id="panelCredenciales">
                <h4>Configurar Credenciales de Acceso Directo</h4>
                <p class="cred-desc">
                    Actualiza o genera tu usuario, correo y contraseña en la misma base de datos. Tu contraseña se almacenará encriptada en hash (Bcrypt) y podrás usarla en la terminal oculta (<code>Ctrl + Shift + L</code>).
                </p>
                <form id="formCredencialesPrivadas">
                    <div class="cred-grid">
                        <div class="cred-field">
                            <label for="credUsuario">Nombre de Usuario</label>
                            <input type="text" id="credUsuario" required value="${escaparHTML(nombreActual)}">
                        </div>
                        <div class="cred-field">
                            <label for="credCorreo">Correo Electrónico</label>
                            <input type="email" id="credCorreo" required value="${escaparHTML(correoActual)}">
                        </div>
                        <div class="cred-field">
                            <label for="credPassword">Nueva Contraseña (se guardará en Hash)</label>
                            <input type="password" id="credPassword" required placeholder="Escribe tu contraseña secreta">
                        </div>
                    </div>
                    <button type="submit" class="cred-submit-btn">Hashear y Guardar en Base de Datos</button>
                </form>
                <div id="credResultadoMsg" class="cred-msg"></div>
            </div>
        `;
        contenedorPrincipal.appendChild(wrapper);

        // 4. Eventos de la interfaz incrustada
        const btnToggle = document.getElementById('btnToggleCredenciales');
        const panel = document.getElementById('panelCredenciales');
        const form = document.getElementById('formCredencialesPrivadas');
        const msgBox = document.getElementById('credResultadoMsg');

        btnToggle.addEventListener('click', () => {
            panel.classList.toggle('abierto');
        });

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            msgBox.className = 'cred-msg';
            msgBox.style.display = 'none';

            const payload = {
                accion: 'guardar_credenciales',
                usuario: document.getElementById('credUsuario').value.trim(),
                correo: document.getElementById('credCorreo').value.trim(),
                password: document.getElementById('credPassword').value
            };

            try {
                const resp = await fetch('auth_credenciales.php', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();

                if (!resp.ok || !data.ok) {
                    throw new Error(data.error || 'No se pudieron actualizar las credenciales.');
                }

                // Actualizar en vivo la tabla y el hash en pantalla si cambiaron el nombre o correo
                if (celdas.length > 4 && data.usuario) {
                    celdas[1].textContent = data.usuario.nombre;
                    celdas[4].textContent = data.usuario.correo;
                }
                const cajaHash = document.querySelector('code.hash-box');
                if (cajaHash && data.nuevo_hash_block) {
                    cajaHash.textContent = data.nuevo_hash_block;
                }

                msgBox.className = 'cred-msg ok';
                msgBox.innerHTML = `
                    <strong>${escaparHTML(data.mensaje)}</strong><br>
                    <span>Hash Bcrypt almacenado en MySQL: <code>${escaparHTML(data.hash_contrasena)}</code></span>
                `;
                document.getElementById('credPassword').value = '';
            } catch (err) {
                msgBox.className = 'cred-msg err';
                msgBox.textContent = err.message;
            }
        });

        function escaparHTML(str) {
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }
    });
})();