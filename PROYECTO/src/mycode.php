<?php

// encabezados o titulares
define ("P","principal"); # h1
define ("S","secundario"); # h2
define ("M","mediano"); # h3
define ("MI","minusculo"); # h4
define ("MIN","miniatura"); # h5
define ("D","diminuto"); # h6
define ('INI',false); # inicio
define ('FIN',true); # fin

function estructura (string $nombre = 'default', bool $barra_diagonal = INI) {
    $estructuras_validas = [
        'header', 'footer', 'nav', 'main', 'section', 'article', 'aside', 'div', '!DOCTYPE',
        'html', 'head', 'meta', 'body', 'title', 'style', 'span', 'pre', 'code'
    ];

    // Separar solo en el primer espacio para permitir múltiples atributos o clases
    $arreglo = explode(" ", trim($nombre), 2);
    $tag = $arreglo[0];
    $atributos = isset($arreglo[1]) ? ' ' . $arreglo[1] : '';

    if (!in_array($tag, $estructuras_validas)) {
        die('
            Estructuras validas [ 
                header,footer,nav,main,section,article,aside,div,
                !DOCTYPE,html,head,meta,body,title,style,span,pre,code
            ]
            <br>utiliza echo para imprimir y INI para apertura y FIN para cierre
        ');
    }

    if ($barra_diagonal) {
        return "</" . htmlspecialchars($tag) . ">";
    } else {
        return "<" . htmlspecialchars($tag) . $atributos . ">";
    }
}

function meta (string $atributos = 'name="viewport" content="width=device-width, initial-scale=1.0"') {
    return "<meta $atributos>";
}

function nuevo (string $path, string $nombreArchivo = 'index.php'): string|false {
    // Limpiar barras finales de la ruta del directorio
    $directorio = rtrim($path, '/\\');
    if ($directorio === '') {
        $directorio = '.';
    }

    // Asegurar que el archivo tenga extensión .php por defecto si no se especificó ninguna
    $extension = pathinfo($nombreArchivo, PATHINFO_EXTENSION);
    if ($extension === '') {
        $nombreArchivo .= '.php';
    }

    // Crear el directorio si no existe
    if (!is_dir($directorio) && !mkdir($directorio, 0755, true) && !is_dir($directorio)) {
        return false;
    }

    $rutaCompleta = $directorio . DIRECTORY_SEPARATOR . ltrim($nombreArchivo, '/\\');

    // Contenido exacto de la plantilla usando Nowdoc para evitar interpolación de variables
    $contenido = <<<'PHP'
    <?php require_once "./src/mycode.php"; syntax (); ?>

        <?= decodificar ( lista (['Item 1']) ); ?>

    <?php sanctuary (); ?>
    PHP;

    if (file_put_contents($rutaCompleta, $contenido . PHP_EOL) === false) {
        return false;
    }

    return $rutaCompleta;
}

function codigocss ($path) {
    echo '<link rel="stylesheet" href="'.$path.'">';
}

function syntax ($title = 'AryiCodTel',$seo = '') {
    echo estructura ( '!DOCTYPE html' ) .
     estructura ( 'html lang=es' ) .
     estructura ( 'head' ) .
         meta ( 'charset="UTF-8"' ) .
         meta () .
         estructura ( 'title' ) .
            $title .
         estructura ( 'title' , FIN ) .
         $seo .
     estructura ( 'head' , FIN ) .
     estructura ( 'body' );
}

function sanctuary () {
    echo estructura ( 'body' , FIN ) . estructura ( 'html' , FIN );
}

function encabezado (string $texto = 'default' , string $tamano = 'default') {

    if ($texto === 'default') {
        die('Ingresa el Texto que quieras imprimir por pantalla<br>
        dentro de los parentesis ("texto") seguido del tama&ntilde;o<br>
        separado por coma asi: encabezado("texto",CONSTANTE);<br>
        Utiliza echo para imprimir el resultado<br>
        deja el segundo parametro vacio para ver la 
        <br>lista de constantes.');
    } else {

        switch ($tamano) {
            case 'principal': 
                return "<h1>".htmlspecialchars($texto)."</h1>";
            break;
            case 'secundario':
                return "<h2>".htmlspecialchars($texto)."</h2>";
            break;
            case 'mediano':
                return "<h3>".htmlspecialchars($texto)."</h3>";
            break;
            case 'minusculo':
                return "<h4>".htmlspecialchars($texto)."</h4>";
            break;
            case 'miniatura':
                return "<h5>".htmlspecialchars($texto)."</h5>";
            break;
            case 'diminuto':
                return "<h6>".htmlspecialchars($texto)."</h6>";
            break;
            default: return "
                <br>Utiliza las constantes [P,S,M,MI,MIN,D]<br>
                <ol>
                    <li>P para h1 , ".P."</li>
                    <li>S para h2 , ".S."</li>
                    <li>M para h3 , ".M."</li>
                    <li>MI para h4 , ".MI."</li>
                    <li>MIN para h5 , ".MIN."</li>
                    <li>D para h6 , ".D."</li>
                </ol>
            ";
        }

    }

}

function parrafo (array $texto = []) {
    if (empty($texto)) {
        die ('Utiliza un arreglo para insertar tu parrafo.<br> y echo para imprimir');
    } else {
        $parrafo = '';
        for ($i=0; $i < count($texto); $i++) { 
            if (array_key_exists($i,$texto)) {
            $parrafo .= htmlspecialchars($texto[$i]) . '<br>';
            } else {
                die ('Tipo de dato Incorrecto');
            }
        }
        return "<p>$parrafo</p>";
    }
}

function enlace (array $enlaces = [] , string $modo = 'default') {

    $salida = '';
    $salida_ = [];

    if (empty($enlaces)) {
        die('El arreglo esta vacio o tiene una estructura incorrecta.<br>utiliza un arreglo asociativo porfavor. y echo para imprimir la salida.<br>
        utiliza el valor "string" para que el programa no retorne un arreglo.');
    } elseif ($modo == 'string') {
        foreach ($enlaces as $item => $url) {
            $salida .= "<a href=\"".htmlspecialchars($url)."\" target=\"_blank\">".htmlspecialchars($item)."</a>";
        }
        return $salida;
    } else {
        foreach ($enlaces as $item => $url) {
            $salida_[] = "<a href=\"".htmlspecialchars($url)."\" target=\"_blank\">".htmlspecialchars($item)."</a>";
        }
        return $salida_;
    }
    
}

function lista ( array $items = [] , string $tipo = '' ) {
    if (empty($items)) {
        die('El arreglo $items no puede estar vacio.');
    }

    $items_ = '';

    if ($tipo == 'ordenada') {
        for ($i=0; $i < count($items); $i++) { 
            $items_ .= '<li>'.$items[$i].'</li>';
        }
        return '<ol>'.htmlspecialchars($items_).'</ol>';
    } else {
        for ($i=0; $i < count($items); $i++) { 
            $items_ .= '<li>'.$items[$i].'</li>';
        }
        return '<ul>'.htmlspecialchars($items_).'</ul>';
    }
}

function decodificar ($string) {
    return htmlspecialchars_decode($string, ENT_QUOTES);
}