<?php
/**
 * conexion.php
 * Configuración de la conexión PDO a MySQL y definición de las clases Block y Blockchain (basadas en minibc.php).
 */

$host = 'mysql'; // Cambiar a '127.0.0.1' o 'localhost' si no usas contenedor Docker llamado 'mysql'
$db   = 'syntax_sanctuary';
$user = 'root';
$pass = '1993';
$charset = 'utf8mb4';

$dsn = "mysql:host=$host;dbname=$db;charset=$charset";
$options = [
    PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    PDO::ATTR_EMULATE_PREPARES   => false,
];

try {
    $pdo = new PDO($dsn, $user, $pass, $options);
} catch (PDOException $e) {
    header('Content-Type: application/json; charset=utf-8');
    http_response_code(500);
    echo json_encode([
        'ok' => false,
        'error' => 'Error de conexión a la base de datos: ' . $e->getMessage()
    ]);
    exit;
}

// Definición de la clase Block (idéntica a tu archivo minibc.php)
class Block {
    public $index;
    public $timestamp;
    public $data;
    public $previousHash;
    public $hash;
    public $nonce;

    public function __construct($index, $timestamp, $data, $previousHash = '') {
        $this->index = $index;
        $this->timestamp = $timestamp;
        $this->data = $data;
        $this->previousHash = $previousHash;
        $this->nonce = 0;
        $this->hash = $this->calculateHash();
    }

    // Calcula el hash SHA-256 del bloque
    public function calculateHash() {
        return hash('sha256', $this->index . $this->timestamp . json_encode($this->data) . $this->previousHash . $this->nonce);
    }

    // Simula la minería ajustando el nonce hasta encontrar un hash con la dificultad requerida
    public function mineBlock($difficulty) {
        $target = str_repeat('0', $difficulty);
        while (substr($this->hash, 0, $difficulty) !== $target) {
            $this->nonce++;
            $this->hash = $this->calculateHash();
        }
    }
}

// Definición de la cadena de bloques (idéntica a tu archivo minibc.php)
class Blockchain {
    public $chain;
    public $difficulty;
    public $hora;

    public function __construct($hora) {
        $this->chain = [$this->createGenesisBlock()];
        $this->difficulty = 2; // Dificultad baja para agilizar la prueba local
        $this->hora = $hora;
    }

    private function createGenesisBlock() {
        return new Block(0, $this->hora, ["mensaje" => "Bloque Genesis"], "0");
    }

    public function getLatestBlock() {
        return $this->chain[count($this->chain) - 1];
    }

    public function addBlock($newBlock) {
        $newBlock->previousHash = $this->getLatestBlock()->hash;
        $newBlock->mineBlock($this->difficulty);
        $this->chain[] = $newBlock;
    }
}

/**
 * Función auxiliar que toma la fila obtenida de la base de datos ($userData)
 * y genera exactamente el mismo hash que minibc.php
 */
function generarHashConBlockchain(array $userData): array {
    $accessBlockchain = new Blockchain($userData['hora']);

    $newBlockData = [
        "id"     => $userData['id'],
        "nombre" => $userData['nombre'],
        "correo" => $userData['correo'],
        "hora"   => $userData['hora']
    ];

    $blockIndex = count($accessBlockchain->chain);
    $userBlock = new Block($blockIndex, $newBlockData['hora'], $newBlockData);

    // Agregar y minar el bloque en la cadena
    $accessBlockchain->addBlock($userBlock);

    return [
        'hash'       => $userBlock->hash,
        'nonce'      => $userBlock->nonce,
        'datos_hash' => $newBlockData
    ];
}