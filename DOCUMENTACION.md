# Documentación de Transferencia Rápida PRO

Esta aplicación utiliza el motor de **Robocopy** (Robust File Copy) integrado en Windows para realizar transferencias de archivos de manera ultra rápida, eficiente y segura.

## ¿Qué tipo de archivos puede clonar?

La aplicación puede clonar **absolutamente cualquier tipo de archivo**. 
Al usar el motor de Robocopy a nivel del sistema operativo, el programa es capaz de copiar:
- Todos los formatos de archivos (fotos, videos pesados, documentos, programas, bases de datos).
- Toda la estructura de carpetas y subcarpetas (incluso si están vacías).
- Archivos ocultos o protegidos por el sistema.
- Archivos de gran tamaño (decenas o cientos de gigabytes) sin crashear.

El programa está diseñado para tomar una carpeta origen, leer su nombre, y clonarla *exactamente igual* dentro del directorio destino elegido.

---

## Parámetros de Robocopy Utilizados

En el código fuente de la aplicación (`app.py`), el comando que se ejecuta en segundo plano es el siguiente:
`robocopy <origen> <destino> /E /MT:8 /R:1 /W:1 /NFL /NDL`

Cada parámetro tiene un propósito específico para optimizar la copia:

- **`/E` (Empty):** Copia todos los subdirectorios, incluyendo aquellos que están vacíos. Esto garantiza que la estructura de carpetas se replique perfectamente.
- **`/MT:8` (Multi-Threading):** Es el **parámetro estrella**. Permite copiar usando 8 hilos (procesos) en paralelo. El copiador normal de Windows copia archivo por archivo (1 hilo). Al usar 8 hilos, la velocidad de transferencia se multiplica drásticamente.
- **`/R:1` (Retries):** Si Robocopy encuentra un archivo bloqueado, corrupto o ilegible, intentará volver a leerlo **solo 1 vez** en lugar de atorarse intentándolo un millón de veces (que es el valor predeterminado de Windows).
- **`/W:1` (Wait):** Es el tiempo de espera entre intentos. Si falla, espera **1 segundo** y continúa. Junto con `/R:1`, esto evita que toda la transferencia se cancele por culpa de un solo archivo dañado.
- **`/NFL` y `/NDL` (No File List / No Directory List):** Oculta la lista masiva de nombres de archivos y carpetas en la consola para no saturar la memoria y el rendimiento de la aplicación, permitiendo que la interfaz procese el progreso de manera limpia.

---

## Compatibilidad de Discos (HDD, SSD, NVMe, USB)

La configuración utilizada es el "estándar de oro" y es 100% compatible con cualquier medio de almacenamiento formateado para Windows (NTFS, exFAT, FAT32). Robocopy trabaja a nivel de sistema de archivos, por lo que **físicamente no le importa de qué material sea el disco**.

### Casos de Uso:

1. **De SSD a SSD / NVMe (Rendimiento Extremo):**
   Es donde el programa brilla más. Gracias al parámetro `/MT:8`, al no tener partes mecánicas, los discos de estado sólido pueden leer y escribir los 8 archivos simultáneos sin ningún cuello de botella, logrando velocidades extremas.

2. **De HDD a SSD (o viceversa):**
   Funciona perfectamente. La transferencia se limitará a la velocidad máxima mecánica del disco duro (HDD), pero la transferencia será constante, sin las caídas repentinas de velocidad que suele tener el explorador de Windows.

3. **De USB / SD Card a PC:**
   Los USB pueden ser más lentos o tener desconexiones de microsegundos. Aquí es donde los parámetros `/R:1` y `/W:1` te salvan la vida. Si la USB tiene un archivo corrupto, el programa no se trabará ni cancelará la copia (algo común en Windows); simplemente saltará ese archivo malo y continuará respaldando todo lo demás de forma segura.

4. **Unidades de Red (Carpetas Compartidas):**
   Robocopy fue diseñado originalmente para redes. Maneja micro-cortes de conexión excelentemente, haciéndolo ideal para respaldar datos hacia un servidor o NAS.

---

## Características Nivel Empresarial (IT Deployment)

Se han integrado funciones exclusivas para el departamento de IT (como en entornos Safran) para automatizar y asegurar el despliegue de software industrial:

### 1. Auto-Descubrimiento de Perfiles
Un menú desplegable permite elegir perfiles de software (`Catia V5`, `AutoCAD`, `SolidWorks`). El sistema escanea en milisegundos todas las unidades conectadas buscando la carpeta específica del instalador y autocompleta la ruta de origen mágicamente, sin importar qué letra asigne Windows a la USB.

### 2. Guardián de Espacio
El sistema calcula el peso total de la carpeta origen de forma invisible y verifica la capacidad del disco destino antes de comenzar la copia. Si no hay espacio suficiente (dejando un 2% de margen de seguridad para que Windows no colapse), bloquea la operación para evitar fallas a mitad del proceso.

### 3. Motor de Orquestación JSON (Pipeline Engine)
Al seleccionar un perfil y hacer clic en Iniciar, el sistema lee un archivo de configuración en la carpeta `pipelines/` (ej. `catia_v5.json`) y ejecuta secuencialmente:
1. Copia de archivos mediante Robocopy Multihilo.
2. Ejecución silenciosa del instalador con parámetros predefinidos (ej. `/qn /norestart`).
3. Ejecución de scripts de PowerShell post-instalación desde la carpeta `scripts/` (ej. inyección de variables de entorno y claves de registro).

### 4. Base de Datos SQLite y Dashboard Analítico
La aplicación utiliza una base de datos embebida (`audit_logs.db`) para registrar de forma inmutable la telemetría de cada ticket (Hostname, perfil, tiempos de ejecución, códigos de estado). Un Dashboard interactivo en el Frontend permite visualizar el total de operaciones, la tasa de éxito y las últimas transferencias en tiempo real.

### 5. Lanzador LAPS (UAC) Integrado
Si prefieres instalaciones manuales, al completar una copia al 100% aparece el botón **"Instalar como Administrador (UAC)"**. Alternativamente, si corres la plataforma `.exe` como administrador desde el inicio con las credenciales LAPS, todo el Pipeline automatizado heredará esos privilegios sin pedir contraseña nuevamente.

### 6. Interfaz de Usuario (UI) Moderna
- **Diseño Glassmorphism**: Interfaz moderna, oscura y fluida.
- **Alertas Animadas (Toasts)**: Notificaciones y errores aparecen como alertas flotantes no intrusivas.
- **Responsive Design**: La aplicación se adapta a cualquier tamaño de ventana.

---

## Cómo compilar en un Ejecutable Portable (.exe)

Para llevar esta aplicación en una USB y ejecutarla en las computadoras de los ingenieros o usuarios finales **sin necesidad de instalar Python ni librerías**, debes empaquetarla usando **PyInstaller** o mediante el módulo de Eel.

### Comando de Compilación:
Abre una terminal en la carpeta principal del proyecto (`C:\RobocopyApp`) y ejecuta lo siguiente:

```powershell
pip install pyinstaller
python -m eel app.py web --onefile --noconsole --icon=web/logo.ico --name="TransferenciaRapida_IT"
```

**Explicación de parámetros:**
- `app.py web`: Le dice al compilador que `app.py` es el script principal y que empaquete la carpeta `web` entera.
- `--onefile`: Empaqueta todo (Python, librerías, frontend) en un **único archivo `.exe`**.
- `--noconsole`: Oculta la ventana negra del CMD de Windows, mostrando únicamente la interfaz gráfica elegante.
- `--icon=web/logo.ico`: Le asigna el logo oficial al ejecutable.

### Resultado:
Al terminar el proceso, se creará una carpeta llamada **`dist`**. Adentro encontrarás el archivo `TransferenciaRapida_IT.exe`. 
**Ese único archivo `.exe` es el que debes copiar a tu memoria USB.** Ya puedes hacer doble clic en él en cualquier computadora y la aplicación funcionará por completo de manera nativa.
