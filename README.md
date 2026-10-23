# 🌌 Syntax Sanctuary (`AryiCodTel`) & Aryi Autonomous Agent








**Syntax Sanctuary** es una plataforma web modular y ecosistema de desarrollo en contenedor **LAMP (Linux, Apache, MySQL 8.0, PHP 8.2)** con exposición Zero-Trust mediante **Cloudflare Tunnel**. Combina un **motor propio de generación de vistas en PHP (`mycode.php`)**, un **sistema de identidad criptográfica basado en prueba de trabajo (Proof-of-Work Blockchain SHA-256)** con terminal secreta de acceso rápido, una **Estación Privada multi-herramienta** (Sandbox de archivos aislado por usuario, Blog/Nexus comunitario en tiempo real y Test Bench), un **Media Center híbrido** (YouTube + almacenamiento local MP4/WebM/OGV/MOV) y el agente autónomo **Aryi (`aryiCodigo.py`)** para ingeniería de software y auditoría de código.

## 🏗️ Arquitectura General del Ecosistema

El proyecto se divide en cinco pilares principales que operan de forma integrada:

1. **Infraestructura Contenerizada (`docker-compose.yml` & `Dockerfile`)**: Orquestación de 4 contenedores en una red bridge aislada (`red_web`): servidor de aplicaciones `Syntax_Sanctuary` (`php:8.2-apache`), motor relacional `mysql:8.0`, interfaz administrativa `phpmyadmin` y demonio `cloudflare/cloudflared` para publicación directa hacia `https://syntaxsanctuary.com`.
2. **Motor DSL de Renderizado HTML (`src/mycode.php`)**: Micro-framework declarativo en PHP que abstrae la creación de documentos HTML5 semánticos (`syntax()`, `sanctuary()`, `estructura()`, `encabezado()`, `parrafo()`, `enlace()`, `lista()`) y automatiza la generación de plantillas nuevas mediante `nuevo()`.
3. **Módulo de Identidad Criptográfica Blockchain & Terminal Oculta (`public/InicioDeSesion/`)**: Sistema de registro y verificación sin exposición de datos sensibles en el área pública, respaldado por minería de bloques SHA-256 (`Block` y `Blockchain` con PoW) y una consola interactiva estilo Linux (`Ctrl + Shift + L` / `Ctrl + Alt + T`) para login por credenciales con migración automática a hashes `Bcrypt`.
4. **Estación Central Privada (`public/InicioDeSesion/area_privada.php`)**: Panel unificado con regeneración dinámica del Hash Blockchain al actualizar el perfil, gestor de archivos Sandbox con aislamiento estricto por usuario (`storage_usuarios/user_<id>`), red de apuntes **Nexus Blog** (visibilidad pública o privada con bloqueo atómico `LOCK_EX`) y **Test Bench** de validación.
5. **Media Center (`public/player/index.php`) & Agente Autónomo Aryi (`aryiCodigo.py`)**: Reproductor y catálogo multimedia con soporte para YouTube (estándar, Shorts y Live) y subida de archivos locales hasta 1 GB con protección CSRF, acompañado por el motor de herramientas en Python de **Aryi** para inspección, parcheo y ejecución segura en el sistema de archivos.

## 📂 Estructura Completa del Proyecto

```text
├── docker-compose.yml                              # Orquestación multicontenedor (Web, MySQL, phpMyAdmin, Cloudflare)
├── Dockerfile                                      # Configuración de permisos base (www-data:www-data, 775)
├── aryiCodigo.py                                   # Agente IA autónomo de ingeniería de software y despacho de herramientas
└── PROYECTO/                                       # Volumen montado en /var/www/html dentro de Syntax_Sanctuary
    ├── index.php                                   # Portal principal construido con el DSL de src/mycode.php
    ├── src/
    │   └── mycode.php                              # Librería core de generación HTML semántico y scaffolding PHP
    └── public/
        ├── InicioDeSesion/                         # Subsistema de Autenticación Blockchain y Estación Privada
        │   ├── conexion.php                        # Conexión PDO MySQL + Clases Block, Blockchain y generarHashConBlockchain()
        │   ├── index.php                           # Paso 1: Formulario de Registro y Modal de entrega de Hash SHA-256
        │   ├── guardar_usuario.php                 # Endpoint POST de inserción de nuevos usuarios en MySQL
        │   ├── generar_hash.php                    # Endpoint GET/POST de minado de bloque y verificación ciega de existencia
        │   ├── verificar.php                       # Paso 2: Pantalla pública de acceso por Hash + carga de Terminal Secreta
        │   ├── validar_acceso.php                  # Endpoint POST de validación criptográfica hash_equals() y apertura de sesión
        │   ├── auth_credenciales.php               # Endpoint dual: actualización Bcrypt y login desde Terminal Secreta
        │   ├── area_privada.php                    # Estación Central: Perfil, Archivador Sandbox, Nexus Blog y Test Bench
        │   ├── app.js                              # Lógica frontend Fetch para registro, copiado de hash y validación reactiva
        │   ├── terminal_secreta_login.js           # Consola oculta (Ctrl+Shift+L / Ctrl+Alt+T) con intérprete de comandos
        │   ├── ui_credenciales_privada.js          # Widget inyectado en Área Privada para configurar usuario/correo/password Bcrypt
        │   ├── storage_blog_unificado.json         # Almacenamiento JSON concurrente (flock LOCK_EX) para el Nexus Blog
        │   └── storage_usuarios/                   # Sandboxes individuales aislados por ID de usuario
        │       ├── user_1/
        │       ├── user_6/
        │       └── user_7/
        └── player/                                 # Subsistema Multimedia (Syntax Sanctuary Media Center)
            ├── index.php                           # Monolito MVC + API AJAX para reproducción y administración de vídeos
            ├── videos_data.json                    # Catálogo persistente con escritura atómica (.tmp + rename)
            └── uploads_videos/                     # Almacenamiento local de vídeos subidos (.mp4, .webm, .ogv, .mov)
```

## 🐳 Infraestructura y Despliegue con Docker

La infraestructura está diseñada para levantarse con un solo comando mediante **Docker Compose**, autoconfigurando las extensiones de PHP (`pdo`, `pdo_mysql`, `mysqli`), permisos de Apache y módulos de proxy/reescritura.

### Servicios del Clúster (`docker-compose.yml`)

| Servicio | Nombre de Contenedor | Imagen Base | Puerto Local → Interno | Función Principal |
| :--- | :--- | :--- | :--- | :--- |
| `web` | `Syntax_Sanctuary` | `php:8.2-apache` | `8000:80` | Servidor web principal, compila `pdo_mysql`/`mysqli`, activa `proxy`, `proxy_http`, `rewrite` y monta `./PROYECTO` en `/var/www/html`. |
| `mysql` | `mysql` | `mysql:8.0` | `3306:3306` | Base de datos relacional con persistencia en el volumen `mysql_data`. |
| `phpmyadmin` | `phpmyadmin` | `phpmyadmin:latest` | `8001:80` | Panel visual de administración MySQL con límite de subida ampliado a `128M`. |
| `cloudflare` | `cloudflare_tunnel_frontend` | `cloudflare/cloudflared:latest` | Red interna `red_web` | Túnel seguro sin apertura de puertos en el router mediante `--token ${TOKEN_DE_CLOUDFLARE}`. |

### 1. Variables de Entorno (`.env`)

Crea un archivo `.env` en el mismo directorio donde se encuentra `docker-compose.yml`:

```ini
MYSQL_ROOT_PASSWORD=1993
MYSQL_DATABASE=syntax_sanctuary
TOKEN_DE_CLOUDFLARE=tu_token_de_cloudflare_zero_trust_aqui
```

> **Nota sobre credenciales de conexión**: En `public/InicioDeSesion/conexion.php`, la conexión PDO apunta por defecto al host `mysql`, base de datos `syntax_sanctuary`, usuario `root` y contraseña `1993`. Mantener `MYSQL_ROOT_PASSWORD=1993` y `MYSQL_DATABASE=syntax_sanctuary` en tu `.env` garantiza compatibilidad inmediata sin editar el código fuente.

### 2. Esquema de Base de Datos MySQL (`usuarios`)

Una vez levantados los contenedores, accede a **phpMyAdmin** (`http://localhost:8001`) o conéctate por CLI al contenedor `mysql` y ejecuta el siguiente esquema dentro de la base de datos `syntax_sanctuary`:

```sql
CREATE DATABASE IF NOT EXISTS `syntax_sanctuary`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE `syntax_sanctuary`;

CREATE TABLE IF NOT EXISTS `usuarios` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `nombre` VARCHAR(120) NOT NULL,
    `edad` INT UNSIGNED NOT NULL,
    `pais` VARCHAR(100) NOT NULL,
    `correo` VARCHAR(160) NOT NULL,
    `hora` VARCHAR(20) NOT NULL,
    `password` VARCHAR(255) NOT NULL,
    PRIMARY KEY (`id`),
    INDEX `idx_correo` (`correo`),
    INDEX `idx_nombre` (`nombre`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 3. Puesta en Marcha

```bash
# 1. Descomprimir PROYECTO.rar en la carpeta ./PROYECTO junto al docker-compose.yml
mkdir -p PROYECTO
unrar x PROYECTO.rar ./PROYECTO/

# 2. Levantar toda la pila de contenedores en segundo plano
docker compose up -d

# 3. Verificar el estado y la instalación de extensiones PHP en Syntax_Sanctuary
docker logs -f Syntax_Sanctuary
```

Accesos locales disponibles tras iniciar el clúster:

- **Portal Principal (`index.php`)**: `http://localhost:8000/`
- **Registro e Identidad Blockchain**: `http://localhost:8000/public/InicioDeSesion/index.php`
- **Verificación de Hash y Terminal Secreta**: `http://localhost:8000/public/InicioDeSesion/verificar.php`
- **Estación Privada**: `http://localhost:8000/public/InicioDeSesion/area_privada.php`
- **Media Center**: `http://localhost:8000/public/player/`
- **phpMyAdmin**: `http://localhost:8001/`

## ⛓️ Motor de Autenticación Blockchain (`conexion.php`)

A diferencia de los sistemas tradicionales que solo almacenan sesiones simples, **Syntax Sanctuary** implementa una cadena de bloques local (`Block` y `Blockchain`, inspirada en `minibc.php`) para generar y validar llaves de acceso criptográficas de 64 caracteres en formato hexadecimal.

### Cómo Funciona el Minado de Identidad

1. **Bloque Génesis**: Cada instancia de `Blockchain($hora)` inicializa la cadena con un bloque índice `0`, marca temporal igual a la hora de registro del usuario (`$userData['hora']`), payload `{"mensaje": "Bloque Genesis"}` y `previousHash = "0"`.
2. **Construcción del Bloque de Usuario**: La función `generarHashConBlockchain(array $userData)` construye el bloque índice `1` combinando exactamente los atributos de identidad del usuario:
   - `id` (Identificador primario en MySQL)
   - `nombre` (Nombre de usuario)
   - `correo` (Correo electrónico)
   - `hora` (Marca de tiempo registrada)
3. **Prueba de Trabajo (Proof-of-Work)**: El método `mineBlock($difficulty)` incrementa iterativamente un contador `$nonce` desde `0` y calcula `hash('sha256', $index . $timestamp . json_encode($data) . $previousHash . $nonce)` hasta que el hash resultante comienza con tantos ceros como indique `$difficulty` (configurado en dificultad `2`, es decir, prefijo `"00..."`).
4. **Validación sin Exposición Pública (`validar_acceso.php` y `generar_hash.php`)**:
   - Cuando el usuario pega su hash de 64 caracteres en `verificar.php`, el frontend (`app.js`) realiza una consulta reactiva a `generar_hash.php?verificar_existencia=<hash>` que devuelve únicamente `{"ok": true, "reconocido": true|false}` sin filtrar nombres, correos ni IDs.
   - Al enviar el formulario a `validar_acceso.php`, el servidor compara en tiempo constante con `hash_equals()`, regenera el ID de sesión (`session_regenerate_id(true)`) y establece `$_SESSION['acceso_autorizado']`, `$_SESSION['usuario_id']` y `$_SESSION['hash_verificado']`.
5. **Re-hasheo Dinámico por Integridad**: Si el usuario modifica su nombre o correo dentro de `area_privada.php`, el sistema recalcula automáticamente su bloque en la cadena y actualiza `$_SESSION['hash_verificado']` en vivo sin cerrar su sesión.

## 💻 Terminal Secreta de Acceso Rápido (`terminal_secreta_login.js`)

En la pantalla de verificación (`public/InicioDeSesion/verificar.php`), el inicio de sesión tradicional mediante **Correo/Usuario + Contraseña** permanece completamente oculto para proteger la superficie pública.

### Activación y Comandos Soportados

Presiona **`Ctrl + Shift + L`** o **`Ctrl + Alt + T`** en cualquier momento dentro de `verificar.php` para desplegar la consola interactiva `root@syntax-sanctuary:~` (`Syntax Sanctuary Secure Shell v2.4 [LAMP Stack]`). Presiona `Esc` para ocultarla.

| Comando en Consola | Acción Ejecutada |
| :--- | :--- |
| `login` / `sudo login` / `auth` / `auth --user` | Verifica privilegios y despliega el cajón oculto (`#secLoginDrawer`) para iniciar sesión con Correo/Usuario y Contraseña. |
| `help` / `?` | Lista en pantalla todos los comandos soportados por la terminal interactiva. |
| `redirect` / `redir` | Inicia una cuenta regresiva de 10 segundos en consola y redirige automáticamente al dominio de producción `https://syntaxsanctuary.com/`. |
| `clear` / `cls` | Limpia el historial de salida de la terminal. |
| `exit` / `quit` | Cierra la ventana de la terminal y vuelve a ocultar el cajón de credenciales. |

### Migración Automática de Contraseñas (`auth_credenciales.php`)

El endpoint `auth_credenciales.php` soporta tres niveles de verificación criptográfica al autenticar desde la Terminal Secreta (`accion = 'login_credenciales'`):

1. **Bcrypt / Argon2 nativo (`password_verify`)**: Verifica contraseñas hasheadas con `password_hash($pass, PASSWORD_DEFAULT)`.
2. **SHA-256 directo**: Verifica compatibilidad con hashes SHA-256 mediante `hash_equals()`.
3. **Auto-migración transparente desde texto plano**: Si detecta que el registro inicial en `guardar_usuario.php` almacenó la contraseña sin hashear, autentica al usuario e inmediatamente ejecuta un `UPDATE` en MySQL reemplazándola por un hash **Bcrypt** seguro.

Además, desde el Área Privada, el módulo `ui_credenciales_privada.js` inyecta el botón **"🔐 Configurar Acceso por Correo y Contraseña Hasheada"**, permitiendo actualizar usuario, correo y contraseña en Bcrypt y mostrando en pantalla el hash Bcrypt resultante junto con el nuevo hash Blockchain de la sesión.

## 🛡️ Estación Central Privada (`area_privada.php`)

Una vez autenticado (por Hash Blockchain o mediante la Terminal Secreta), el usuario accede a `area_privada.php`, estructurada en cuatro pestañas interactivas:

### 1. 👤 Mi Perfil y Hash (`?tab=perfil`)
- Visualización en tiempo real del **Hash de Acceso Actual (SHA-256 Blockchain)**.
- Formulario de edición de **Nombre Completo**, **Edad**, **País** y **Correo Electrónico**.
- Al guardar cambios, recalcula el bloque criptográfico y sincroniza la sesión automáticamente.
- Incluye al final el panel desplegable de `ui_credenciales_privada.js` para rotación de contraseña con **Bcrypt**.

### 2. 📂 Archivador Personal Sandbox (`?tab=archivador`)
- **Aislamiento por Usuario**: Cada cuenta opera exclusivamente dentro de su directorio `public/InicioDeSesion/storage_usuarios/user_<ID>`.
- **Protección contra Path Traversal**: Las funciones `normalize_relative_path()` y `safe_path()` limpian secuencias `..` y validan con `realpath()` y `str_starts_with()` que ninguna operación salga de la raíz asignada al usuario.
- **Operaciones Soportadas**:
  - Navegación jerárquica por subcarpetas con iconos dinámicos por extensión (`🐘 .php`, `🌐 .html`, `🎨 .css`, `⚡ .js`, `🧩 .json`, `📁 carpetas`).
  - Creación instantánea de carpetas (`action=create_folder`) y archivos nuevos (`action=create_file`).
  - Descarga directa de binarios y código (`action=download`) mediante streams `application/octet-stream`.
  - Eliminación recursiva segura de archivos y directorios (`action=delete` / `delete_directory_recursive()`).

### 3. 📝 Nexus Blog & Apuntes Compartidos (`?tab=blog`)
- Motor de microblogging y fragmentos de código respaldado por `storage_blog_unificado.json`.
- **Control de Visibilidad Dual**:
  - `🔒 Privada`: Visible únicamente para el autor de la nota en su estación privada.
  - `🌐 Pública`: Visible en el feed comunitario de todos los usuarios autenticados en la plataforma.
- **Concurrencia Segura**: Utiliza bloqueos exclusivos de archivo (`flock($fpBlog, LOCK_EX)`) durante la escritura para evitar corrupción de JSON cuando múltiples usuarios publican simultáneamente.
- **Moderación**: Cada usuario puede eliminar sus propias publicaciones (y el usuario administrador con `id === 1` cuenta con permisos globales de moderación).

### 4. 🧪 Test Bench & Guía de Pruebas (`?tab=testbench`)
- Panel de staging interactivo con tarjetas de verificación para auditar:
  1. **Integridad Blockchain**: Comprobación de regeneración de hash tras edición de perfil.
  2. **Aislamiento de Archivos (Sandbox)**: Confirmación de escritura en `storage_usuarios/user_<id>`.
  3. **Sincronización del Blog Comunitario**: Prueba cruzada de publicaciones públicas entre distintas cuentas.

## 🎬 Syntax Sanctuary — Media Center (`public/player/index.php`)

Accesible desde el portal principal o desde el botón **Videos** de la Estación Privada (requiere sesión Blockchain activa), el **Media Center** es una aplicación monolítica en PHP + AJAX para reproducción y gestión de catálogo audiovisual.

### Características Técnicas del Reproductor

- **Soporte Multimedia Híbrido**:
  - **YouTube Embebido**: Expresión regular avanzada (`getYoutubeId()`) compatible con enlaces estándar (`youtube.com/watch?v=...`), enlaces cortos (`youtu.be/...`), **YouTube Shorts** (`youtube.com/shorts/...`), directos (`youtube.com/live/...`) y dominios `youtube-nocookie.com`.
  - **Vídeo Local HTML5 (`<video>`)**: Subida directa de archivos hasta **1 GB (`MAX_VIDEO_BYTES = 1000 MB`)** con validación estricta de MIME mediante `finfo(FILEINFO_MIME_TYPE)` (`video/mp4`, `video/webm`, `video/ogg`, `video/quicktime`) y barra de progreso en tiempo real vía `XMLHttpRequest.upload`.
- **Escritura Atómica del Catálogo (`atomicWriteJson()`)**: Las modificaciones sobre `videos_data.json` se escriben primero en un archivo temporal criptográfico (`videos_data.json.tmp.<random_hex>`) con `LOCK_EX` y luego se reemplazan atómicamente mediante `rename()`, evitando pérdida de datos ante cortes de energía o peticiones concurrentes.
- **Panel de Administración Protegido con CSRF**:
  - Desbloqueable desde el botón `🔒 Administrador` usando la contraseña maestra definida en `ADMIN_PASSWORD` (`ss-tfh-free`, mostrada como pista en el `index.php` raíz).
  - Todas las acciones mutantes (`upload_video`, `delete_video`, `logout`) exigen un token CSRF de 64 caracteres (`$_SESSION['media_csrf']`) validado con `hash_equals()`.
  - Al eliminar un vídeo local desde la playlist, el backend borra automáticamente el archivo físico dentro de `uploads_videos/` además de actualizar el JSON.

## 🧩 Librería DSL de Renderizado PHP (`src/mycode.php`)

El archivo `src/mycode.php` define un lenguaje de dominio específico (DSL) en español para construir páginas HTML5 limpias sin mezclar etiquetas crudas con la lógica de negocio.

### Constantes y Funciones Disponibles

| Función / Constante | Firma / Parámetros | Descripción y Ejemplo de Uso |
| :--- | :--- | :--- |
| `syntax()` / `sanctuary()` | `syntax($title = 'AryiCodTel', $seo = '')` | Abre y cierra respectivamente la estructura base del documento (`<!DOCTYPE html><html lang=es><head>...<body>` y `</body></html>`). |
| `estructura()` | `estructura(string $nombre, bool $barra_diagonal = INI)` | Genera etiquetas semánticas validadas (`header`, `footer`, `nav`, `main`, `section`, `article`, `aside`, `div`, `span`, `pre`, `code`, `style`, etc.). Usa `INI` (`false`) para abrir y `FIN` (`true`) para cerrar. |
| `encabezado()` | `encabezado(string $texto, string $tamano)` | Renderiza titulares `<h1>` a `<h6>` escapados con `htmlspecialchars()` usando las constantes `P` (`h1`), `S` (`h2`), `M` (`h3`), `MI` (`h4`), `MIN` (`h5`) y `D` (`h6`). |
| `enlace()` | `enlace(array $enlaces, string $modo = 'default')` | Recibe un arreglo asociativo `['Texto' => 'URL']` y genera etiquetas `<a href="..." target="_blank">`. Devuelve un array de enlaces o un string concatenado si `$modo === 'string'`. |
| `lista()` | `lista(array $items, string $tipo = '')` | Genera listas `<ul>` (por defecto) o `<ol>` (si `$tipo === 'ordenada'`). Se combina con `decodificar()` cuando contiene HTML interno como enlaces. |
| `parrafo()` | `parrafo(array $texto)` | Convierte un arreglo indexado de cadenas en un bloque `<p>` separado por saltos `<br>` con escape XSS automático. |
| `codigocss()` | `codigocss(string $path)` | Imprime la etiqueta `<link rel="stylesheet" href="...">`. |
| `nuevo()` | `nuevo(string $path, string $nombreArchivo = 'index.php')` | Función de scaffolding que crea el directorio destino si no existe y genera automáticamente un archivo `.php` preconfigurado con la plantilla base de `syntax()` y `sanctuary()`. |

### Ejemplo Práctico (`PROYECTO/index.php`)

```php
<?php require_once "./src/mycode.php"; syntax (); ?>

    <?= decodificar ( lista (enlace([
        'Videos' => './public/player/' ,
        'Blog' => './public/InicioDeSesion/area_privada.php'
    ])) ); ?>

    <?= encabezado ('password: ss-tfh-free',MIN); ?>

<?php sanctuary (); ?>
```

## 🤖 Agente Autónomo Aryi (`aryiCodigo.py`)

El repositorio incluye en su raíz el módulo **`aryiCodigo.py`**, que define el núcleo de **Aryi (`aryiCodigo`)**: un agente autónomo de ingeniería de software, administración de sistemas y auditoría de código diseñado para interactuar con el entorno local mediante llamadas estructuradas en JSON.

### Capacidades y Herramientas del Despachador (`execute_tool`)

- **Conciencia del Entorno (`build_system_prompt(os_profile)`)**: Inyecta dinámicamente en el prompt de sistema el sistema operativo (`os`, `release`, `arch`), la shell predeterminada, el gestor de paquetes detectado (`apt`, `pacman`, `winget`, etc.) y el directorio de trabajo actual (`cwd`).
- **Escritura Segura con Respaldo Automático (`tool_write_file`)**:
  - Solicita confirmación interactiva (`confirm_action`) antes de crear o sobrescribir cualquier archivo.
  - Si el archivo destino ya existe, genera automáticamente una copia de respaldo con extensión **`.bak`** (`target.with_suffix('.bak')`) antes de escribir el nuevo contenido en UTF-8.
- **Parcheo Quirúrgico de Código (`patch_file`)**: Sustituye bloques específicos de código (`search_block` → `replace_block`) utilizando expresiones regulares escapadas (`re.sub(re.escape(search_block), replace_block, content)`).
- **Catálogo de Herramientas Integradas**:
  1. `list_dir`: Exploración superficial o recursiva del árbol de directorios.
  2. `read_file`: Lectura previa obligatoria antes de auditar o modificar archivos existentes.
  3. `write_file`: Creación o actualización completa de archivos con generación de backup `.bak`.
  4. `make_dir`: Creación recursiva de directorios (`mkdir(parents=True, exist_ok=True)`).
  5. `search_files`: Búsqueda por expresiones regulares (`TODO|FIXME|function`) en el proyecto.
  6. `run_command`: Ejecución de comandos de consola, compiladores, linters, pruebas y gestores de paquetes del sistema.
  7. `patch_file`: Modificación localizada de fragmentos de código sin reescribir el archivo completo.

## 🔒 Resumen de Mecanismos de Seguridad Implementados

| Capa / Módulo | Mecanismo de Seguridad | Implementación en el Proyecto |
| :--- | :--- | :--- |
| **Autenticación Pública** | Verificación Ciega de Hash | `generar_hash.php` y `validar_acceso.php` recrean la cadena en memoria y comparan con `hash_equals()` sin devolver datos personales en la respuesta JSON pública. |
| **Contraseñas de Usuario** | Hashing Adaptativo + Migración | `auth_credenciales.php` utiliza `password_hash(..., PASSWORD_DEFAULT)` (Bcrypt) y migra automáticamente contraseñas legadas en el primer inicio de sesión. |
| **Base de Datos (MySQL)** | Consultas Preparadas Nativas | `conexion.php` desactiva la emulación (`PDO::ATTR_EMULATE_PREPARES => false`) y usa sentencias preparadas en todas las consultas SQL. |
| **Sesiones PHP** | Prevención de Session Fixation | Uso sistemático de `session_regenerate_id(true)` al superar la validación por Hash Blockchain, Terminal Secreta o Login de Media Center. |
| **Sandbox de Archivos** | Jail por Usuario (`safe_path`) | Normalización de rutas y verificación estricta con `realpath()` y `str_starts_with()` para confinar a cada usuario en `storage_usuarios/user_<id>`. |
| **Media Center** | Protección CSRF + Filtro MIME | Tokens aleatorios de 32 bytes (`bin2hex(random_bytes(32))`), cabeceras `X-Content-Type-Options: nosniff` / `X-Frame-Options: SAMEORIGIN` y validación real de archivos con `finfo`. |
| **Almacenamiento JSON** | Bloqueos Exclusivos y Escritura Atómica | Uso de `flock(..., LOCK_EX)` en `storage_blog_unificado.json` y archivo temporal + `rename()` atómico en `videos_data.json`. |

## 🤝 Guía para Contribuir yExtender el Proyecto

1. **Crear nuevas vistas con el DSL de `mycode.php`**:
   Puedes generar automáticamente el esqueleto de una nueva sección ejecutando `nuevo('./public/nueva_seccion', 'index.php');` desde PHP, lo cual creará la carpeta y el archivo base conectado a `syntax()` y `sanctuary()`.
2. **Ajustar la dificultad del minado Blockchain**:
   En `public/InicioDeSesion/conexion.php`, dentro del constructor de la clase `Blockchain`, puedes modificar `$this->difficulty = 2;` (ten en cuenta que si cambias la dificultad cuando ya existen usuarios, sus hashes cambiarán al recalcularse con el nuevo número de ceros iniciales requeridos).
3. **Ampliar comandos de la Terminal Secreta**:
   Edita `public/InicioDeSesion/terminal_secreta_login.js` dentro del bloque `termInput.addEventListener('keydown', ...)` para añadir nuevos comandos administrativos o atajos personalizados.
4. **Personalizar límites de subida de vídeo**:
   Para subir vídeos mayores a 128 MB / 1 GB en producción, ajusta la constante `MAX_VIDEO_BYTES` en `public/player/index.php` y añade un archivo `uploads.ini` en tu contenedor Apache/PHP con `upload_max_filesize = 1024M` y `post_max_size = 1024M`.
