<?php require_once "./src/mycode.php"; syntax (); ?>

    <?= decodificar ( lista (enlace([
        'Videos' => './public/player/' ,
        'Area Priv' => './public/InicioDeSesion/area_privada.php' ,
        'Chat' => './public/chat' ,
        'Aryi' => './public/agente' ,
        'GitHub' => 'https://github.com/radaptow' ,
        'Juego' => './public/game' ,
        'Vision' => './public/VISION/VISION.php' ,
        'Texto' => './public/TEXT/TEXT.php' ,
        'Blog' => './public/blog' ,
        'Status' => './public/machine_status' ,
        'Plantilla' => './public/machine_status/Template' ,
        'Archivos' => './files.php'
    ])) ); ?>

    <?= encabezado ('password: ss-tfh-free',MIN); ?>

<?php sanctuary (); ?>