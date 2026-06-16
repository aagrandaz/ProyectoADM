# Guía de Clonado y Ejecución del Proyecto: "Next Best Product"

Esta guía detalla los pasos para clonar el repositorio y ejecutar el pipeline analítico (tanto en local como en Google Colab) en sistemas operativos **Windows, macOS y Linux**.

---

## 1. Prerrequisitos

Asegúrate de tener instalado en tu computadora:
* **Git**: Para clonar el repositorio. [Descargar Git](https://git-scm.com/)
* **Python 3.10 o superior**: Se recomienda Python 3.10 o 3.11. [Descargar Python](https://www.python.org/)
* **VS Code** (Recomendado) con las siguientes extensiones instaladas:
  * *Python* (de Microsoft)
  * *Jupyter* (de Microsoft)

---

## 2. Paso 1: Clonar el Repositorio

Abre una terminal (PowerShell en Windows, Terminal en macOS/Linux) y clona el proyecto con el siguiente comando:

**Por HTTPS:**
```bash
git clone https://github.com/aagrandaz/ProyectoADM.git
```

**Por SSH (si tienes tus llaves configuradas):**
```bash
git clone git@github.com:aagrandaz/ProyectoADM.git
```

Una vez clonado, entra a la carpeta del proyecto:
```bash
cd ProyectoADM
```

---

## 3. Paso 2: Creación e Instalación del Entorno Virtual (.venv)

Elige la sección correspondiente a tu sistema operativo para configurar y activar el entorno de desarrollo local.

### 💻 macOS / Linux (Bash o Zsh)
1. **Crear el entorno virtual:**
   ```bash
   python3 -m venv .venv
   ```
2. **Activar el entorno virtual:**
   ```bash
   source .venv/bin/activate
   ```
3. **Actualizar pip e instalar dependencias:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### 🪟 Windows (PowerShell)
1. **Crear el entorno virtual:**
   ```powershell
   python -m venv .venv
   ```
2. **Activar el entorno virtual:**
   *(Nota: Si te da un error de restricciones de ejecución en PowerShell, abre la terminal como Administrador y ejecuta `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force` antes de activar)*
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
3. **Actualizar pip e instalar dependencias:**
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

### 🪟 Windows (Símbolo del Sistema / CMD)
1. **Crear el entorno virtual:**
   ```cmd
   python -m venv .venv
   ```
2. **Activar el entorno virtual:**
   ```cmd
   .venv\Scripts\activate.bat
   ```
3. **Actualizar pip e instalar dependencias:**
   ```cmd
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 4. Paso 3: Ejecución en Local (Dos Opciones)

### Opción A: Ejecución Directa mediante Scripts Python (Recomendado para testing rápido)
Una vez activado tu entorno virtual `.venv` en la terminal, puedes ejecutar el pipeline completo de ingeniería de datos y entrenamiento del modelo ejecutando estos comandos en orden:

```bash
# 1. Ingesta, Calidad y Limpieza (Raw -> Bronze -> Silver)
python src/data_processing.py

# 2. Creación de la Matriz Analítica de Candidatos (Silver -> Gold)
python src/feature_engineering.py

# 3. Entrenamiento y Ajuste del Random Forest (Genera modelo y métricas)
python src/train_model.py

# 4. Inferencia y Generación de Recomendaciones Comerciales Top-1
python src/predict.py
```

### Opción B: Ejecución mediante VS Code y Jupyter Notebooks (Interactivo)
1. Abre **VS Code**.
2. Selecciona **File -> Open Folder...** (Archivo -> Abrir carpeta...) y selecciona la carpeta raíz del proyecto `ProyectoADM`.
3. En la barra lateral izquierda, navega a la carpeta `notebooks/` y abre el cuaderno `01_ingesta_raw.ipynb`.
4. **IMPORTANTE (Configurar Kernel manualmente):**
   * En la esquina superior derecha del editor del notebook en VS Code, haz clic en **"Select Kernel"** (Seleccionar Kernel) o sobre el Python por defecto.
   * En el menú superior que aparece, haz clic en **"Select Another Kernel..."** -> **"Python Environments..."**.
   * Si no ves el entorno `.venv` del proyecto en la lista, selecciona **"Enter interpreter path..."** (Ingresar ruta del intérprete...) y busca o pega la ruta exacta del ejecutable:
     * **macOS / Linux:** `ProyectoADM/.venv/bin/python`
     * **Windows:** `ProyectoADM\.venv\Scripts\python.exe`
5. Ejecuta las celdas secuencialmente. Repite el proceso seleccionando el mismo Kernel para los notebooks del `02` al `06`.

---

## 5. Paso 4: Ejecución en Google Colab

Si prefieres ejecutar los notebooks de forma agnóstica en la nube de Google Colab:
1. Sube la carpeta del proyecto a tu Google Drive (por ejemplo, en `Mi unidad/Colab Notebooks/Proyecto`).
2. Abre cualquier notebook desde Drive haciendo clic derecho -> **Abrir con -> Google Colaboratory**.
3. La primera celda de código de cada cuaderno detectará automáticamente el entorno de Colab (`IN_COLAB = True`), instalará las librerías necesarias mediante pip y te pedirá permiso para montar Google Drive (`drive.mount('/content/drive')`) para poder acceder de forma transparente a las carpetas `data/` y `models/`.

---

## 6. Paso 5: Levantamiento y Uso de la Observabilidad (Grafana Stack Premium)

El proyecto incluye un entorno de observabilidad pre-configurado para monitorear el pipeline, las métricas del recomendador y el servidor MCP.

### Iniciar el Servidor MCP (Métricas Prometheus):
El servidor MCP publica sus métricas en el puerto `8800`. Levántalo primero en segundo plano desde la carpeta raíz:
```bash
python src/mcp_server.py
```

### Iniciar el Stack de Observabilidad (Docker):
Asegúrate de tener Docker instalado y ejecutándose, luego corre desde la raíz del proyecto:
```bash
cd observability
docker compose up -d
```
Esto levantará de forma aislada:
* **Grafana (Puerto 3000):** Consola de visualización (iniciar sesión con usuario `admin` y contraseña `admin123`).
* **Loki (Puerto 3100):** Servidor de Logs (configurado para leer automáticamente los archivos en `logs/` mediante Alloy).
* **Mimir (Puerto 9009):** Servidor de Métricas Prometheus (recibe las métricas enviadas por Alloy).
* **Alloy (Puerto 12345):** Colector central que raspa los logs locales y el endpoint de métricas del MCP en `localhost:8800`.

### Visualizar el Dashboard Premium de Grafana:
1. Abre tu navegador e ingresa a `http://localhost:3000`.
2. Ve al menú de **Dashboards** y selecciona **"Next Best Product - ML & Ingestion Observability"**.
3. Verás la consola organizada en secciones colapsables premium:
   * **🧠 Inteligencia Artificial: Métricas del Modelo & Explicabilidad**: Visualiza los indicadores clave del modelo de Machine Learning (AUC, Accuracy@1 y Accuracy@3) y la importancia analítica de las variables del modelo en tiempo real (explicabilidad del Random Forest).
   * **📊 Tubería de Datos: Pipeline de Ingesta Medallón**: Cantidad de registros cargados y tiempos detallados de ejecución en segundos por cada etapa del pipeline (Bronze, Silver, Gold, ML, Inferencia) para diagnóstico de rendimiento.
   * **📞 Integración con IA: Monitoreo de Herramientas MCP Server**: Tráfico de llamadas a las herramientas del Servidor MCP y latencias de respuesta suavizadas con gradiente de opacidad.
   * **📄 Diagnósticos del Sistema: Logs en Tiempo Real (Loki)**: Visor directo de logs sincronizado en orden descendente para depurar fallos en caliente.


