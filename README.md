# Recomendador Predictivo de Productos Financieros: "Next Best Product"

Este repositorio contiene la solución completa de ingeniería de datos y modelado predictivo para implementar un recomendador bancario de "Mejor Siguiente Producto" (Next Best Product).

El sistema procesa la información de transacciones y tenencias de clientes mediante una arquitectura de datos Medallón (Raw $\rightarrow$ Bronze $\rightarrow$ Silver $\rightarrow$ Gold) y entrena un modelo predictivo supervisado basado en Random Forest, evaluando su precisión mediante métricas de ranking comercial. Adicionalmente, incluye un servidor **MCP (Model Context Protocol)** para interactuar con los resultados desde un asistente de IA.

---

## 1. Arquitectura de Datos Medallón

El flujo de procesamiento relacional se realiza en memoria mediante **DuckDB**, garantizando velocidades OLAP en milisegundos:

1. **Capa Raw**: Archivos originales de entrada en formato CSV localizados en `data/raw/`.
2. **Capa Bronze**: Conversión directa 1:1 de los archivos CSV a binarios estructurados en formato columnar **Parquet** (`data/bronze/`). Preserva metadatos y acelera las lecturas secuenciales.
3. **Capa Silver**: Limpieza, estandarización de tipos, imputación de nulos (edad y renta) usando la mediana para evitar sesgos, y cálculoMonth-over-Month (MoM) de altas netas de productos financieros (`data/silver/`).
4. **Capa Gold**: Matriz de candidatos cruzando clientes y productos (excluyendo los productos que el cliente ya posee activamente para evitar ofertas redundantes), creación de variables agregadas de tenencia por categoría y simulación reproducible de conversiones bancarias (`data/gold/`).

---

## 2. Estructura del Repositorio

El proyecto sigue rigurosamente la estructura modular académica sugerida para la solución:

```
next-best-product-project/
├── data/
│   ├── raw/         # CSVs originales y guías PDF de insumo
│   ├── bronze/      # Parquets de ingesta 1:1
│   ├── silver/      # Parquets limpios, tipados y con altas MoM
│   └── gold/        # Matriz analítica de candidatos y recomendaciones
├── notebooks/
│   ├── 01_ingesta_raw.ipynb
│   ├── 02_convertir_bronze.ipynb
│   ├── 03_limpieza_silver.ipynb
│   ├── 04_construccion_gold.ipynb
│   ├── 05_entrenamiento_modelo.ipynb
│   └── 06_prediccion_recomendacion.ipynb
├── src/
│   ├── data_processing.py      # Flujo Raw -> Bronze -> Silver
│   ├── feature_engineering.py   # Flujo Silver -> Gold
│   ├── train_model.py          # Entrenamiento, tuning y métricas del modelo
│   ├── predict.py              # Inferencia y generación de recomendaciones
│   └── mcp_server.py           # Servidor de integración inteligente MCP
├── models/
│   ├── modelo_next_best_product.pkl   # Pipeline de inferencia Scikit-Learn
│   └── metrics.json                   # Métricas finales del recomendador
├── docs/
│   ├── diccionario_datos.md    # Explicación de esquemas y relaciones
│   └── informe_modelo.md       # Reporte técnico del modelo predictivo
├── requirements.txt            # Dependencias del entorno virtual
└── README.md                   # Esta guía
```

---

## 3. Instrucciones de Ejecución

Para ejecutar el pipeline analítico completo paso a paso, utiliza el entorno virtual `.venv` de la siguiente forma:

### Paso 1: Ingesta y Limpieza Inicial (Raw a Silver)
Lee los archivos CSV de `data/raw/`, los convierte a Parquet en `data/bronze/` y luego aplica los criterios de calidad e imputación exportando a `data/silver/`:
```bash
.venv/bin/python src/data_processing.py
```

### Paso 2: Creación de la Matriz de Candidatos (Silver a Gold)
Cruza los registros de clientes con los productos del catálogo que no posean y simula el target predictivo bancario:
```bash
.venv/bin/python src/feature_engineering.py
```

### Paso 3: Entrenamiento del Modelo
Entrena el Random Forest, realiza la validación por clientes (para evitar data leakage) buscando hiperparámetros óptimos, evalúa ROC-AUC, Accuracy@1 y Accuracy@3 de manera vectorizada en NumPy, y exporta el modelo y métricas:
```bash
.venv/bin/python src/train_model.py
```

### Paso 4: Inferencia y Recomendaciones Comerciales
Aplica el modelo predictivo sobre los candidatos de prueba, ordena las probabilidades descendientes por cliente y exporta la recomendación Top-1:
```bash
.venv/bin/python src/predict.py
```

---

## 4. Servidor MCP (Model Context Protocol)

El servidor MCP permite conectar un asistente de inteligencia artificial (como Gemini o Claude) con los datos y predicciones generados por el modelo.

### Herramientas Expuestas por el Servidor MCP:
* `get_client_profile(client_id)`: Retorna la edad, sexo, segmento, ingresos, antigüedad y tenencia actual por categorías financieras del cliente consultando la capa Silver.
* `get_client_recommendation(client_id)`: Retorna el ranking de productos recomendados y su probabilidad de adquisición calculados por el Random Forest en la capa Gold.
* `get_model_performance()`: Retorna el ROC-AUC, Accuracy@1 y Accuracy@3 medidos en validación.
* `get_product_catalog()`: Retorna la lista de productos del catálogo de la institución.

### Ejecución del Servidor MCP:
El servidor se comunica a través de entrada/salida estándar (stdin/stdout) mediante mensajería JSON-RPC. Para iniciarlo:
```bash
.venv/bin/python src/mcp_server.py
```

Para configurarlo dentro de clientes MCP (como Claude Code, Cursor, Windsurf, etc.), agrega la siguiente configuración en tu archivo de configuración de servidores MCP (por ejemplo, `.mcp.json` o `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "next-best-product-server": {
      "command": "/Volumes/HD/0.2.Sistemas_de_Informacion_UG/11vo-semestre/ANÁLISIS DE DATOS MASIVO/Proyecto/.venv/bin/python",
      "args": [
        "/Volumes/HD/0.2.Sistemas_de_Informacion_UG/11vo-semestre/ANÁLISIS DE DATOS MASIVO/Proyecto/src/mcp_server.py"
      ]
    }
  }
}
```
