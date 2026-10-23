# SyntaxSanctuary

SyntaxSanctuary es un proyecto innovador que busca mejorar la experiencia de programación para los entusiastas de la tecnología. Nuestro objetivo es proporcionar herramientas y recursos que faciliten el desarrollo de software y hagan que el proceso sea más agradable y productivo.

## 🎯 Características Principales

- **Interfaz Amigable**: Diseñada con el usuario en mente, SyntaxSanctuary ofrece una interfaz intuitiva que facilita la navegación y el uso del software.
- **Personalización**: Permite a los usuarios personalizar su experiencia según sus preferencias, desde temas hasta configuraciones avanzadas.
- **Comunidad Activa**: SyntaxSanctuary cuenta con una comunidad activa y amigable donde los usuarios pueden compartir conocimientos, resolver dudas y colaborar en proyectos.

## 🐳 Instalación con Docker

Para instalar SyntaxSanctuary utilizando contenedores Docker, sigue estos pasos detallados:

### Requisitos Previos

- **Sistema Operativo**: Windows 10/11 (64-bit)
- **Docker Desktop**: Instalado y actualizado a la última versión
- **Docker CLI**: Disponible en el sistema operativo
- **Python**: 3.8 o superior

### Paso 1: Verificar que Docker esté instalado

```bash
# En PowerShell o CMD
docker --version
```

Si el comando no devuelve una versión, sigue las instrucciones de instalación desde [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

### Paso 2: Configurar el archivo .env

El archivo `.env` contiene las variables de configuración del proyecto.

1. **Crea el archivo .env** en la raíz del proyecto:
   ```bash
   echo "APP_NAME=SyntaxSanctuary" > .env
   echo "DATABASE_URL=postgres://localhost:5432/syntaxsanctuary" >> .env
   echo "SECRET_KEY=your-secret-key-here" >> .env
   ```

2. **Verifica que el archivo .env sea accesible**:
   ```bash
   cat .env
   ```

### Paso 3: Iniciar los contenedores Docker

```bash
# Inicia todos los contenedores del proyecto
docker-compose up -d
```

### Paso 4: Verificar que los contenedores estén funcionando

```bash
# Verifica que todos los contenedores estén en ejecución
docker ps -a
```

### Paso 5: Acceder al servicio desde la terminal

```bash
# Accede a la aplicación desde el navegador
http://localhost:3000
```

## 📋 Instrucciones de Instalación (Español)

### Requisitos Previos

- **Sistema Operativo**: Windows 10/11 (64-bit)
- **Docker Desktop**: Instalado y actualizado a la última versión
- **Docker CLI**: Disponible en el sistema operativo
- **Python**: 3.8 o superior

### Paso 1: Verificar que Docker esté instalado

```bash
# En PowerShell o CMD
docker --version
```

Si el comando no devuelve una versión, sigue las instrucciones de instalación desde [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

### Paso 2: Configurar el archivo .env

El archivo `.env` contiene las variables de configuración del proyecto.

1. **Crea el archivo .env** en la raíz del proyecto:
   ```bash
   echo "APP_NAME=SyntaxSanctuary" > .env
   echo "DATABASE_URL=postgres://localhost:5432/syntaxsanctuary" >> .env
   echo "SECRET_KEY=your-secret-key-here" >> .env
   ```

2. **Verifica que el archivo .env sea accesible**:
   ```bash
   cat .env
   ```

### Paso 3: Iniciar los contenedores Docker

```bash
# Inicia todos los contenedores del proyecto
docker-compose up -d
```

### Paso 4: Verificar que los contenedores estén funcionando

```bash
# Verifica que todos los contenedores estén en ejecución
docker ps -a
```

### Paso 5: Acceder al servicio desde la terminal

```bash
# Accede a la aplicación desde el navegador
http://localhost:3000
```

## 🚀 Uso

SyntaxSanctuary es fácil de usar. Aquí tienes un ejemplo básico de cómo comenzar:

```python
# Ejemplo de código en Python
print("¡Bienvenido a SyntaxSanctuary!")
```

## 🤝 Contribución

¡Somos abiertos a contribuciones! Si tienes ideas para mejorar SyntaxSanctuary, no dudes en abrir un issue o enviar un pull request.

## 📜 Licencia

SyntaxSanctuary está licenciado bajo la MIT License. Consulta el archivo [LICENSE](LICENSE) para más detalles.

## 📞 Contacto

Si tienes alguna pregunta o problema, no dudes en contactarnos a través de nuestro [repositorio de GitHub](https://github.com/radaptow/ss).

---

## 🌐 Versión en Inglés

### Requirements

- **Operating System**: Windows 10/11 (64-bit)
- **Docker Desktop**: Installed and updated to the latest version
- **Docker CLI**: Available in the operating system
- **Python**: 3.8 or higher

### Step 1: Verify Docker is Installed

```bash
# In PowerShell or CMD
docker --version
```

If the command does not return a version, follow the installation instructions from [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

### Step 2: Configure the .env File
n
The `.env` file contains the project configuration variables.

1. **Create the .env file** in the project root:
   ```bash
   echo "APP_NAME=SyntaxSanctuary" > .env
   echo "DATABASE_URL=postgres://localhost:5432/syntaxsanctuary" >> .env
   echo "SECRET_KEY=your-secret-key-here" >> .env
   ```

2. **Verify that the .env file is accessible**:
   ```bash
   cat .env
   ```

### Step 3: Start Docker Containers
n
```bash
# Start all project containers
docker-compose up -d
```

### Step 4: Verify Docker Containers are Running
n
```bash
# Check if all containers are running
docker ps -a
```

### Step 5: Access the Service from Terminal
n
```bash
# Access the application from the browser
http://localhost:3000
```

## 📝 Notas Importantes

- **No compartir el archivo .env**: Las variables de configuración deben mantenerse privadas.
- **Backup de datos**: Realiza copias de seguridad antes de realizar cambios.
- **Actualizaciones**: Mantén Docker y sus dependencias actualizadas para evitar problemas.

---

## 🎉 ¡Gracias por usar SyntaxSanctuary! 

¡Esperamos que disfrutes de tu experiencia de programación!
