<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0">
    <title>SyntaxSanctuary</title>
    <link rel="stylesheet" href="bit.css">
</head>
<body>

    <!-- Canvas Fondo -->
    <canvas id="particle-canvas"></canvas>

    <!-- Navegación Top -->
    <nav class="navbar">
        <div class="logo">
            <div style="width:10px;height:10px;background:var(--accent-green);border-radius:50%;box-shadow:0 0 10px var(--accent-green);"></div>
            SyntaxSanctuary
        </div>
        <div class="controls">
            <button class="menu-toggle" onclick="toggleSidebar()">☰</button>
        </div>
    </nav>

    <!-- Contenedor Principal -->
    <div class="layout">
        <!-- Menú Lateral -->
        <aside class="sidebar" id="sidebar">
            <!--<ul>
                <li class="lang-es"><a href="machine_status/">Active Nodes</a></li>
                <li class="lang-es"><a href="proyectos.php">Portafolio</a></li>
                <li class="lang-es"><a href="mvp1">Syntax Sanctuary</a></li>
            </ul>-->
            <?php require_once "../../../src/mycode.php"; syntax (); ?>

            <?= decodificar ( lista (enlace([
                'Videos' => '../../player/' ,
                'Area Priv' => '../../InicioDeSesion/area_privada.php' ,
                'Chat' => '../../chat' ,
                'Aryi' => '../../agente' ,
                'GitHub' => 'https://github.com/radaptow' ,
                'Juego' => '../../game' ,
                'Vision' => '../../VISION/VISION.php' ,
                'Texto' => '../../TEXT/TEXT.php' ,
                'Blog' => '../../blog' ,
                'Status' => '../../machine_status' ,
                'Plantilla' => '../../machine_status/Template' ,
                'Archivos' => '../../../files.php'
            ])) ); ?>
        </aside>

        <!-- Contenido -->
        <main class="main-content">
            
            <div class="section-block">
                <h2 style="border-bottom: 1px dashed var(--border-color); padding-bottom: 10px; margin-bottom: 1.5rem;">
                    ¿Tu proyecto ya está en línea? Descubre quién lo visita en tiempo real.
                </h2>

                <p style="margin-bottom: 1.5rem;">
                    Dar el salto a la web y publicar tus primeras páginas es emocionante, pero programar a ciegas y preguntarte si alguien realmente las está viendo puede ser frustrante. Olvídate de configurar servidores complejos o registrarte en herramientas de analítica aburridas. Te ofrecemos un radar en vivo para tus proyectos, completamente gratis.
                </p>

                <h3 style="margin-bottom: 1rem;">Monitoreo de tráfico sin esfuerzo</h3>
                
                <ul class="styled-list" style="margin-bottom: 2rem;">
                    <li><strong>Visibilidad instantánea:</strong> Observa en este preciso momento si alguien entra a tu página, qué ruta exacta está explorando y desde qué entorno se conecta.</li>
                    <li><strong>Implementación en 10 segundos:</strong> Sin instalaciones pesadas, sin dependencias y sin tocar el backend. Solo copia la etiqueta de nuestro tracker, pégala en tu archivo HTML y el radar comenzará a funcionar.</li>
                    <li><strong>Servicio gratuito para desarrolladores:</strong> No te entregamos código complicado de mantener; nosotros ponemos el servidor y procesamos los datos. Tú solo usas el script y disfrutas viendo cómo fluye tu tráfico en la red.</li>
                    <li><strong>Rendimiento intacto (Carga Asíncrona):</strong> Tu código es sagrado. Nuestro script de rastreo es ultra ligero y funciona silenciosamente en segundo plano, garantizando que el tiempo de carga de tu interfaz no se vea afectado ni un milisegundo.</li>
                </ul>

                <div style="padding-top: 1.5rem; border-top: 1px dashed var(--border-color);">
                    <p style="margin: 0;">
                        <strong style="color: var(--accent-color);">Siente el pulso de tu web:</strong> Genera tu identificador único ahora mismo, inyecta el script y experimenta la satisfacción de ver tu primer tráfico web en vivo. No dejes que tus proyectos se sientan vacíos.
                    </p>
                </div>
            </div>

        </main>
    </div>

    <script src="bitHtml.js"></script>
</body>
</html>
