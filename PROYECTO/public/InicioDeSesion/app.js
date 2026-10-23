/**
 * app.js
 * - En index.html: envía los datos del formulario a guardar_usuario.php, solicita el hash a generar_hash.php
 *   y muestra el pantallazo para copiar el hash antes de redirigir a verificar.html.
 * - En verificar.html: no expone ningún dato de usuarios en el área pública; únicamente recibe el hash,
 *   informa si fue reconocido o no, y redirige a area_privada.php tras la validación.
 */

document.addEventListener('DOMContentLoaded', () => {
    const formRegistro = document.getElementById('formRegistro');
    const modalHash = document.getElementById('modalHash');
    const hashGeneradoTexto = document.getElementById('hashGeneradoTexto');
    const btnCopiarYRedirigir = document.getElementById('btnCopiarYRedirigir');
    const btnSoloCopiar = document.getElementById('btnSoloCopiar');
    const estadoMensaje = document.getElementById('estadoMensaje');

    // =========================================================================
    // PASO 1 y 2: Capturar datos del formulario, guardar en MySQL y pedir Hash
    // =========================================================================
    if (formRegistro) {
        formRegistro.addEventListener('submit', async (e) => {
            e.preventDefault();
            mostrarEstado('Almacenando datos en la base de datos...', 'info');

            const payload = {
                usuario: document.getElementById('usuario').value.trim(),
                edad: parseInt(document.getElementById('edad').value, 10),
                pais: document.getElementById('pais').value.trim(),
                correo: document.getElementById('correo').value.trim(),
                hora: document.getElementById('hora').value.trim(),
                pass: document.getElementById('pass').value
            };

            try {
                // 1. Enviar los datos al backend PHP que los almacena en la base de datos
                const respGuardar = await fetch('guardar_usuario.php', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const resultadoGuardar = await respGuardar.json();

                if (!respGuardar.ok || !resultadoGuardar.ok) {
                    throw new Error(resultadoGuardar.error || 'Error al guardar el usuario.');
                }

                mostrarEstado('Datos almacenados. Generando hash con mecanismo Blockchain...', 'info');

                // 2. Petición al archivo que obtiene los datos de este usuario en MySQL y genera el hash Blockchain
                const respHash = await fetch(`generar_hash.php?id=${encodeURIComponent(resultadoGuardar.id)}`);
                const resultadoHash = await respHash.json();

                if (!respHash.ok || !resultadoHash.ok) {
                    throw new Error(resultadoHash.error || 'Error al generar el hash Blockchain.');
                }

                // 3. Dar el pantallazo para que el usuario copie el hash
                hashGeneradoTexto.textContent = resultadoHash.hash;
                modalHash.classList.add('activo');
                mostrarEstado('¡Hash Blockchain generado con éxito!', 'exito');

            } catch (err) {
                mostrarEstado(err.message, 'error');
            }
        });
    }

    if (btnSoloCopiar) {
        btnSoloCopiar.addEventListener('click', async () => {
            const hash = hashGeneradoTexto.textContent.trim();
            await copiarAlPortapapeles(hash);
            btnSoloCopiar.textContent = '✓ ¡Hash Copiado al Portapapeles!';
        });
    }

    if (btnCopiarYRedirigir) {
        btnCopiarYRedirigir.addEventListener('click', async () => {
            const hash = hashGeneradoTexto.textContent.trim();
            await copiarAlPortapapeles(hash);
            window.location.href = 'verificar.php';
        });
    }

    // =========================================================================
    // PASO 3: Pantalla de Verificación Pública (Sin exponer datos de usuarios)
    // =========================================================================
    const formVerificar = document.getElementById('formVerificar');
    if (formVerificar) {
        const inputHash = document.getElementById('hashGuardado');

        // Al pegar un hash de 64 caracteres, avisar únicamente si es reconocido o no (sin mostrar datos personales)
        if (inputHash) {
            inputHash.addEventListener('input', async () => {
                const hashVal = inputHash.value.trim();
                if (hashVal.length === 64) {
                    try {
                        const resp = await fetch(`generar_hash.php?verificar_existencia=${encodeURIComponent(hashVal)}`);
                        const data = await resp.json();
                        if (resp.ok && data.ok) {
                            if (data.reconocido) {
                                mostrarEstado('✓ Hash reconocido en la cadena de bloques. Presiona el botón para acceder.', 'exito');
                            } else {
                                mostrarEstado('✕ Hash no reconocido.', 'error');
                            }
                        }
                    } catch (_) {
                        // La validación definitiva ocurre al enviar el formulario
                    }
                } else {
                    if (estadoMensaje) estadoMensaje.style.display = 'none';
                }
            });
        }

        // Enviar únicamente el hash a validar_acceso.php
        formVerificar.addEventListener('submit', async (e) => {
            e.preventDefault();
            mostrarEstado('Verificando hash en el servidor...', 'info');

            const payloadVerificacion = {
                hash: inputHash.value.trim()
            };

            try {
                const respValidar = await fetch('validar_acceso.php', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payloadVerificacion)
                });
                const resultadoValidar = await respValidar.json();

                if (!respValidar.ok || !resultadoValidar.ok) {
                    throw new Error(resultadoValidar.error || '✕ Hash no reconocido.');
                }

                mostrarEstado(resultadoValidar.mensaje, 'exito');
                setTimeout(() => {
                    window.location.href = resultadoValidar.redirect || 'area_privada.php';
                }, 700);

            } catch (err) {
                mostrarEstado(err.message, 'error');
            }
        });
    }

    function mostrarEstado(texto, tipo) {
        if (!estadoMensaje) return;
        estadoMensaje.textContent = texto;
        estadoMensaje.className = 'alerta ' + tipo;
        estadoMensaje.style.display = 'block';
    }

    async function copiarAlPortapapeles(texto) {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(texto);
        } else {
            const inputTemp = document.createElement('textarea');
            inputTemp.value = texto;
            document.body.appendChild(inputTemp);
            inputTemp.select();
            document.execCommand('copy');
            document.body.removeChild(inputTemp);
        }
    }
});