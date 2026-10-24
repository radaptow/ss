<?php session_start();

ini_set('display_errors', 1); // Enable error display
ini_set('display_startup_errors', 1); // Show startup errors
error_reporting(E_ALL); // Report all types of errors

if (empty($_SESSION['acceso_autorizado']) || empty($_SESSION['usuario_id']) || empty($_SESSION['hash_verificado'])) {
    header('Location: ../../InicioDeSesion/verificar.php');
    exit;
}

require 'config.php';
require '../functions.php';

$conexion = conexion($bd_config);

// Comprobamos si la session esta iniciada, sino, redirigimos.
comprobarSession();


if (!$conexion) {
	header("Location: ../error.php");
}

$posts = obtener_post($blog_config['post_por_pagina'], $conexion);

require '../views/admin_index.view.php';
?>