<?php
/**
 * Unified Telemetry Dashboard - ROBUST EDITION (Sin operadores problemáticos)
 * + IP Blur Security Feature
 */

header("Access-Control-Allow-Origin: *");
header("Access-Control-Allow-Methods: POST, GET, OPTIONS");
header("Access-Control-Allow-Headers: Content-Type, Accept");

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

$action = isset($_GET['action']) ? $_GET['action'] : 'ui';$registryFile = __DIR__ . '/origins_registry.json';

function getRegistry($file) {
    if (!file_exists($file)) {
        return [];
    }
    $content = file_get_contents($file);
    $data = json_decode($content, true);
    if (json_last_error() === JSON_ERROR_NONE) {
        if (is_array($data)) {
            return $data;
        }
    }
    return [];
}

function saveRegistry($file,$data) {
    $fp = fopen($file, 'c');
    if (flock($fp, LOCK_EX)) {
        ftruncate($fp, 0);
        fwrite($fp, json_encode($data, JSON_PRETTY_PRINT));
        fflush($fp);
        flock($fp, LOCK_UN);
    }
    fclose($fp);
}

// 2. ENDPOINT DE REGISTRO
if ($action === 'register' && $_SERVER['REQUEST_METHOD'] === 'POST') {$input = json_decode(file_get_contents('php://input'), true);
    
    if (empty($input)) {
        http_response_code(400);
        echo json_encode(['error' => 'No payload received']);
        exit;
    }

    $clientId = htmlspecialchars(trim(isset($input['client_id']) ?$input['client_id'] : 'node_unknown'));
    $username = htmlspecialchars(trim(isset($input['username']) ? $input['username'] : 'guest'));$url      = htmlspecialchars(trim(isset($input['url']) ?$input['url'] : 'unknown_url'));
    
    $ip =$_SERVER['REMOTE_ADDR'];
    if (!empty($_SERVER['HTTP_CF_CONNECTING_IP'])) {
        $ip =$_SERVER['HTTP_CF_CONNECTING_IP'];
    } elseif (!empty($_SERVER['HTTP_X_FORWARDED_FOR'])) {
        $ip = explode(',',$_SERVER['HTTP_X_FORWARDED_FOR'])[0];
    }
    $ip = trim($ip);

    $userAgent = isset($_SERVER['HTTP_USER_AGENT']) ? $_SERVER['HTTP_USER_AGENT'] : 'Desconocido';$port      = isset($_SERVER['REMOTE_PORT']) ?$_SERVER['REMOTE_PORT'] : 'N/A';
    
    $hostname = @gethostbyaddr($ip);
    
    // EVITAMOS EL USO DE || (OR) AQUÍ:
    if (!$hostname) {$hostname = 'N/D';
    } elseif ($hostname === $ip) {$hostname = 'N/D';
    }

    $registry = getRegistry($registryFile);

    $registry[$clientId] = [
        'client_id'  => $clientId,
        'username'   => $username,
        'url'        => $url,
        'ip'         => $ip,
        'hostname'   => $hostname,
        'user_agent' => $userAgent,
        'port'       => $port,
        'last_seen'  => time()
    ];

    foreach ($registry as $id =>$node) {
        if ((time() - $node['last_seen']) > 900) {
            unset($registry[$id]);
        }
    }

    saveRegistry($registryFile,$registry);
    
    header('Content-Type: application/json');
    echo json_encode(['status' => 'success', 'client_id' => $clientId, 'saved' => true]);
    exit;
}

// 3. ENDPOINT DE DATOS (AJAX)
if ($action === 'data') {
    header('Content-Type: application/json');
    
    $metrics = [
        'os'           => PHP_OS_FAMILY,
        'disk_total'   => @disk_total_space('/'),
        'disk_free'    => @disk_free_space('/'),
        'cpu'          => 0,
        'ram_total'    => 0,
        'ram_used'     => 0,
        'ram_percent'  => 0,
        'disk_percent' => 0
    ];
    
    if ($metrics['disk_total'] > 0) {
        $metrics['disk_percent'] = round((($metrics['disk_total'] - $metrics['disk_free']) /$metrics['disk_total']) * 100, 2);
    }

    if (PHP_OS_FAMILY === 'Linux') {
        $load = sys_getloadavg();$metrics['cpu'] = isset($load[0]) ?$load[0] : 0;
        $meminfo = @file_get_contents('/proc/meminfo');
        if ($meminfo) {
            if (preg_match_all('/^(\w+):\s+(\d+)\s+kB/m', $meminfo,$matches)) {
                $mem = array_combine($matches[1], $matches[2]);$memTotal = isset($mem['MemTotal']) ?$mem['MemTotal'] : 0;
                $memAvail = isset($mem['MemAvailable']) ?$mem['MemAvailable'] : 0;
                
                $metrics['ram_total'] =$memTotal * 1024;
                $metrics['ram_used']  = ($memTotal -$memAvail) * 1024;
                
                if ($metrics['ram_total'] > 0) {$metrics['ram_percent'] = round(($metrics['ram_used'] /$metrics['ram_total']) * 100, 2);
                }
            }
        }
    }

    $registry = getRegistry($registryFile);$activeHosts = [];
    foreach ($registry as $id =>$node) {
        if ((time() - $node['last_seen']) <= 900) {
            $activeHosts[] =$node;
        }
    }

    echo json_encode([
        'system'  => $metrics,
        'origins' => array_values($activeHosts)
    ]);
    exit;
}

$hasPermissions = true;
$permissionError = "";
if (!file_exists($registryFile)) {
    if (!@touch($registryFile)) {$hasPermissions = false;
        $permissionError = "No se pudo crear el archivo. PHP no tiene permisos de escritura en: " . __DIR__;
    }
} elseif (!is_writable($registryFile)) {$hasPermissions = false;
    $permissionError = "El archivo existe pero PHP no puede escribir en él. Verifica los permisos de: " . $registryFile;
}
?>
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Telemetry Dashboard | Robust</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0d1117; color: #c9d1d9; }
        .card { background-color: #161b22; border: 1px solid #30363d; }
        .bar-bg { background-color: #21262d; height: 8px; border-radius: 4px; overflow: hidden; }
        .bar-fill { height: 100%; transition: width 0.3s ease; }
        tbody tr { transition: all 0.3s ease; }
        
        /* Sistema de protección Blur para IPs */
        .protected-ip { filter: blur(6px); user-select: none; transition: filter 0.3s ease; cursor: pointer; }
        body.ips-unlocked .protected-ip { filter: blur(0); user-select: text; cursor: default; }
    </style>
</head>
<body class="p-6 font-sans">
    <div class="max-w-7xl mx-auto">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-2xl font-bold text-cyan-400">System & Telemetry Dashboard</h1>
            <span id="os-badge" class="px-3 py-1 bg-gray-800 rounded-full text-xs border border-gray-600 font-mono">--</span>
        </div>

        <?php if (!$hasPermissions): ?>
        <div class="bg-red-900 border border-red-500 text-red-100 px-4 py-3 rounded relative mb-6 shadow-lg" role="alert">
            <strong class="font-bold">⚠️ Error Crítico de Permisos:</strong>
            <span class="block sm:inline"><?php echo $permissionError; ?></span>
            <p class="text-sm mt-2 font-mono bg-red-950 p-2 rounded">Solución en terminal: <br>chmod 777 <?php echo __DIR__; ?></p>
        </div>
        <?php endif; ?>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <div class="card p-4 rounded-lg shadow">
                <span class="text-xs font-semibold text-violet-400 uppercase">CPU Load (1m)</span>
                <div id="cpu-val" class="text-lg font-mono mt-1 text-gray-200">--</div>
            </div>
            <div class="card p-4 rounded-lg shadow">
                <span class="text-xs font-semibold text-violet-400 uppercase">Memoria RAM</span>
                <div id="ram-val" class="text-lg font-mono mt-1 text-gray-200">--</div>
                <div class="bar-bg mt-2"><div id="ram-bar" class="bar-fill bg-cyan-500" style="width: 0%"></div></div>
            </div>
            <div class="card p-4 rounded-lg shadow">
                <span class="text-xs font-semibold text-violet-400 uppercase">Disco Libre</span>
                <div id="disk-val" class="text-lg font-mono mt-1 text-gray-200">--</div>
                <div class="bar-bg mt-2"><div id="disk-bar" class="bar-fill bg-purple-500" style="width: 0%"></div></div>
            </div>
        </div>

        <div class="card p-5 rounded-lg shadow mb-8 flex flex-col md:flex-row items-center justify-between gap-4">
            <div class="w-full">
                <label class="block text-xs font-semibold text-gray-400 mb-1">Identificador de Usuario (data-user):</label>
                <input type="text" id="input-user" value="SyntaxSanctuary_RGG" class="w-full bg-gray-950 border border-gray-700 rounded px-3 py-1.5 text-sm text-cyan-300 mb-2 focus:outline-none focus:border-cyan-500">
                <input type="text" id="script-tag" readonly class="w-full bg-gray-950 border border-gray-700 rounded px-3 py-1.5 text-xs font-mono text-gray-300 select-all" value='<script src="https://syntaxsanctuary.com/public/machine_status/Template/bit.js" data-user="SyntaxSanctuary_RGG"></script>'>
            </div>
            <button onclick="copyScript()" id="copy-btn" class="w-full md:w-auto bg-cyan-600 hover:bg-cyan-500 text-gray-950 font-bold px-4 py-2 rounded text-sm transition whitespace-nowrap">
                Copiar Script
            </button>
        </div>

        <div class="flex justify-between items-center mb-4">
            <h2 class="text-lg font-bold text-cyan-300 flex items-center gap-2">
                Orígenes y Dispositivos Activos 
                <span id="sync-dot" class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            </h2>
            <span id="counter" class="px-3 py-1 bg-cyan-950 text-cyan-300 rounded-full text-xs border border-cyan-800 font-mono">0 activos</span>
        </div>

        <div class="card rounded-lg shadow overflow-x-auto">
            <table class="w-full text-left text-sm whitespace-nowrap">
                <thead class="bg-gray-800 text-gray-400 text-xs uppercase border-b border-gray-700">
                    <tr>
                        <th class="p-3">Usuario</th>
                        <th class="p-3">ID de Nodo</th>
                        <th class="p-3">URL / Origen</th>
                        <th class="p-3">
                            <div class="flex items-center gap-2">
                                IP / Hostname
                                <button onclick="toggleIpLock()" id="unlock-btn" class="text-xs bg-gray-700 hover:bg-gray-600 px-2 py-0.5 rounded border border-gray-600 transition outline-none cursor-pointer">🔒</button>
                            </div>
                        </th>
                        <th class="p-3">Último Pulso</th>
                    </tr>
                </thead>
                <tbody id="origins-table">
                    <tr><td colspan="5" class="p-6 text-center text-gray-500">Escuchando red...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const formatGB = (bytes) => (bytes / 1073741824).toFixed(2) + ' GB';
        const inputUser = document.getElementById('input-user');
        const scriptTag = document.getElementById('script-tag');
        const syncDot = document.getElementById('sync-dot');

        // === CONFIGURACIÓN DEL PIN AQUÍ ===
        const SECURITY_PIN = "3456"; 
        let isUnlocked = false;

        function toggleIpLock() {
            if (isUnlocked) {
                isUnlocked = false;
                document.body.classList.remove('ips-unlocked');
                document.getElementById('unlock-btn').innerText = '🔒';
            } else {
                const pin = prompt("Ingrese el PIN de seguridad para revelar las IPs:");
                if (pin === SECURITY_PIN) {
                    isUnlocked = true;
                    document.body.classList.add('ips-unlocked');
                    document.getElementById('unlock-btn').innerText = '🔓';
                } else if (pin !== null) {
                    alert("PIN incorrecto. Acceso denegado.");
                }
            }
        }

        inputUser.addEventListener('input', () => {
            // EVITAMOS EL USO DE || AQUÍ TAMBIÉN
            let user = inputUser.value.trim();
            if (user === '') {
                user = 'guest';
            }
            scriptTag.value = '<script src="https://syntaxsanctuary.com/bit.js" data-user="' + user + '"><\/script>';
        });

        function copyScript() {
            scriptTag.select();
            document.execCommand('copy');
            const btn = document.getElementById('copy-btn');
            btn.innerText = '¡Copiado!';
            setTimeout(() => btn.innerText = 'Copiar Script', 2000);
        }

        async function fetchData() {
            try {
                const res = await fetch('?action=data', { cache: 'no-store' });
                if (!res.ok) throw new Error('Network response was not ok');
                const data = await res.json();
                
                syncDot.classList.remove('bg-red-500');
                syncDot.classList.add('bg-green-500');
                
                const sys = data.system;
                
                // EVITAMOS EL USO DE ||
                const osName = sys.os ? sys.os : 'Desconocido';
                document.getElementById('os-badge').innerText = osName;
                
                document.getElementById('cpu-val').innerText = sys.cpu !== 0 ? sys.cpu.toFixed(2) : '0.00';
                
                if(sys.ram_total > 0) {
                    document.getElementById('ram-val').innerText = `${formatGB(sys.ram_used)} / ${formatGB(sys.ram_total)} (${sys.ram_percent}%)`;
                    document.getElementById('ram-bar').style.width = `${sys.ram_percent}%`;
                }
                
                if(sys.disk_total > 0) {
                    document.getElementById('disk-val').innerText = `${formatGB(sys.disk_free)} libres (${sys.disk_percent}%)`;
                    document.getElementById('disk-bar').style.width = `${sys.disk_percent}%`;
                }

                const tbody = document.getElementById('origins-table');
                document.getElementById('counter').innerText = data.origins.length + ' activos';

                if (data.origins.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="p-6 text-center text-gray-500">No hay orígenes activos actualmente.</td></tr>';
                    return;
                }

                let newHtml = '';
                data.origins.forEach(item => {
                    const ago = Math.floor((Date.now() / 1000) - item.last_seen);
                    const statusColor = ago > 60 ? 'text-yellow-500' : 'text-gray-400';
                    const dotColor = ago > 10 ? 'bg-yellow-500' : 'bg-green-500';
                    
                    newHtml += `
                        <tr class="border-t border-gray-800 hover:bg-gray-900/50">
                            <td class="p-3 font-semibold text-violet-400 flex items-center gap-2">
                                <span class="w-2 h-2 rounded-full ${dotColor}"></span>
                                ${item.username}
                            </td>
                            <td class="p-3 font-mono text-xs text-gray-400">${item.client_id}</td>
                            <td class="p-3 text-cyan-300 max-w-[220px] truncate"><a href="${item.url}" target="_blank" class="hover:underline">${item.url}</a></td>
                            <td class="p-3">
                                <div class="font-mono text-gray-200 protected-ip" onclick="if(!isUnlocked) toggleIpLock()">${item.ip}</div>
                                <div class="text-[10px] text-gray-500 protected-ip" onclick="if(!isUnlocked) toggleIpLock()">${item.hostname}</div>
                            </td>
                            <td class="p-3 font-mono text-xs ${statusColor}">${ago}s atrás</td>
                        </tr>
                    `;
                });
                
                if(tbody.innerHTML !== newHtml) {
                    tbody.innerHTML = newHtml;
                }

            } catch (e) {
                console.error("Error cargando dashboard:", e);
                syncDot.classList.remove('bg-green-500');
                syncDot.classList.add('bg-red-500');
            }
        }

        setInterval(fetchData, 2000);
        fetchData();
    </script>
</body>
</html>
