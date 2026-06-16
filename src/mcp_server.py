"""
Servidor MCP (Model Context Protocol) para el recomendador Next Best Product.
Expone herramientas para consultar predicciones de modelos, perfiles de clientes y métricas de desempeño.
Expone además un servidor de métricas Prometheus en el puerto 8000 para observabilidad.
"""

import os
import json
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import threading
import duckdb
import pandas as pd
from mcp.server.fastmcp import FastMCP
from prometheus_client import start_http_server, Counter, Gauge, Summary

# Resolver de forma portable la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Configurar logger para el servidor MCP
log_file = PROJECT_ROOT / "logs" / "mcp.log"
log_file.parent.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("mcp_server")
logger.setLevel(logging.INFO)
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    c_handler = logging.StreamHandler(sys.stderr)
    c_handler.setFormatter(formatter)
    logger.addHandler(c_handler)
    f_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    f_handler.setFormatter(formatter)
    logger.addHandler(f_handler)

# Instanciar el servidor FastMCP
mcp = FastMCP("Next Best Product Server")

# ─── DEFINICIÓN DE MÉTRICAS PROMETHEUS ───────────────────────────────────────
MCP_TOOL_CALLS = Counter(
    'mcp_tool_calls_total', 
    'Cantidad total de llamadas a herramientas MCP', 
    ['tool_name']
)
MCP_TOOL_LATENCY = Summary(
    'mcp_tool_latency_seconds', 
    'Tiempo de ejecución de las herramientas MCP', 
    ['tool_name']
)

# Métricas del Modelo de ML
MODEL_AUC = Gauge('nbp_model_auc_percent', 'ROC-AUC de validación del modelo entrenado (%)')
MODEL_ACC1 = Gauge('nbp_model_accuracy_top1_percent', 'Accuracy@1 de validación del modelo (%)')
MODEL_ACC3 = Gauge('nbp_model_accuracy_top3_percent', 'Accuracy@3 de validación del modelo (%)')

# Métricas del Pipeline de Ingesta
PIPELINE_ROWS = Gauge(
    'nbp_pipeline_rows_processed_total', 
    'Cantidad de registros procesados por el pipeline Medallón', 
    ['layer']
)

def update_metrics_from_files():
    """Lee los archivos de métricas generados por el pipeline y actualiza los Gauges de Prometheus."""
    logger.info("Actualizando Gauges de Prometheus desde métricas en disco...")
    
    # 1. Métricas de Modelado
    metrics_path = PROJECT_ROOT / "models" / "metrics.json"
    if metrics_path.exists():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            MODEL_AUC.set(data.get("roc_auc", 0.0) * 100)
            MODEL_ACC1.set(data.get("accuracy_at_1", 0.0) * 100)
            MODEL_ACC3.set(data.get("accuracy_at_3", 0.0) * 100)
            logger.info("Gauges de modelo actualizados con éxito.")
        except Exception as e:
            logger.error(f"Error al leer metrics.json: {str(e)}")
            
    # 2. Métricas del Pipeline
    pipe_path = PROJECT_ROOT / "models" / "pipeline_metrics.json"
    if pipe_path.exists():
        try:
            with open(pipe_path, "r", encoding="utf-8") as f:
                pipe_data = json.load(f)
            PIPELINE_ROWS.labels(layer="bronze").set(pipe_data.get("bronze_rows_processed", 0))
            PIPELINE_ROWS.labels(layer="silver").set(pipe_data.get("silver_rows_processed", 0))
            PIPELINE_ROWS.labels(layer="gold_train").set(pipe_data.get("gold_train_rows_processed", 0))
            PIPELINE_ROWS.labels(layer="gold_test").set(pipe_data.get("gold_test_rows_processed", 0))
            logger.info("Gauges de procesamiento de datos actualizados con éxito.")
        except Exception as e:
            logger.error(f"Error al leer pipeline_metrics.json: {str(e)}")

# Levantar servidor HTTP de Prometheus en hilo secundario (daemon)
def start_prometheus_server(port=8800):
    try:
        start_http_server(port)
        logger.info(f"Servidor de métricas Prometheus levantado exitosamente en el puerto {port}")
        while True:
            update_metrics_from_files()
            time.sleep(10)
    except Exception as e:
        logger.error(f"No se pudo iniciar el servidor Prometheus en puerto {port}: {str(e)}")

threading.Thread(target=start_prometheus_server, daemon=True).start()

def get_db_connection():
    """Retorna una conexión DuckDB en memoria."""
    return duckdb.connect(database=":memory:")

@mcp.tool()
def get_client_profile(client_id: int) -> str:
    """
    Obtiene el perfil demográfico, comportamiento y estado financiero actual de un cliente específico.
    
    Args:
        client_id (int): Identificador único del cliente.
        
    Returns:
        str: JSON con el perfil del cliente o un mensaje de error si no se encuentra.
    """
    MCP_TOOL_CALLS.labels(tool_name="get_client_profile").inc()
    start_t = time.time()
    
    silver_dir = PROJECT_ROOT / "data" / "silver"
    gold_dir = PROJECT_ROOT / "data" / "gold"
    clientes_path = silver_dir / "clientes.parquet"
    gold_dataset_path = gold_dir / "dataset_next_best_product_gold.parquet"
    
    if not (clientes_path.exists() and gold_dataset_path.exists()):
        return json.dumps({"error": "Los datos de la capa Silver o Gold no existen. Corre el pipeline completo primero."}, ensure_ascii=False)
        
    con = get_db_connection()
    try:
        query = f"""
            SELECT 
                c.id_cliente,
                c.sexo,
                c.fecha_alta,
                c.canal_entrada,
                g.fecha_corte,
                g.edad,
                g.antiguedad,
                g.renta,
                g.segmento,
                g.ind_actividad_cliente as es_activo,
                g.cantidad_productos_actuales,
                g.tiene_cuenta,
                g.tiene_credito,
                g.tiene_tarjeta,
                g.tiene_inversion
            FROM read_parquet('{clientes_path}') c
            LEFT JOIN read_parquet('{gold_dataset_path}') g ON c.id_cliente = g.id_cliente
            WHERE c.id_cliente = {client_id}
            LIMIT 1
        """
        df = con.execute(query).df()
        if df.empty:
            return json.dumps({"error": f"Cliente con ID {client_id} no encontrado en la base de datos."}, ensure_ascii=False)
            
        profile = df.iloc[0].to_dict()
        for k, v in profile.items():
            if pd.api.types.is_datetime64_any_dtype(type(v)) or hasattr(v, 'strftime'):
                profile[k] = str(v)
            elif pd.isna(v):
                profile[k] = None
                
        # Medir latencia
        MCP_TOOL_LATENCY.labels(tool_name="get_client_profile").observe(time.time() - start_t)
        return json.dumps({"status": "success", "data": profile}, indent=4, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error al consultar el perfil del cliente: {str(e)}"}, ensure_ascii=False)
    finally:
        con.close()

@mcp.tool()
def get_client_recommendation(client_id: int) -> str:
    """
    Obtiene la recomendación del siguiente mejor producto (NBP) y la lista de candidatos
    evaluados para un cliente, ordenados por probabilidad de adquisición descendente.
    
    Args:
        client_id (int): Identificador único del cliente.
        
    Returns:
        str: JSON con el ranking de recomendaciones del cliente.
    """
    MCP_TOOL_CALLS.labels(tool_name="get_client_recommendation").inc()
    start_t = time.time()
    
    gold_dir = PROJECT_ROOT / "data" / "gold"
    predicciones_path = gold_dir / "predicciones_next_best_product.parquet"
    
    if not predicciones_path.exists():
        return json.dumps({"error": "No se han generado las predicciones. Corre predict.py primero."}, ensure_ascii=False)
        
    con = get_db_connection()
    try:
        query = f"""
            SELECT 
                id_cliente,
                fecha_corte,
                nombre_producto,
                categoria_producto,
                probabilidad_adquisicion,
                ranking_producto
            FROM read_parquet('{predicciones_path}')
            WHERE id_cliente = {client_id}
            ORDER BY ranking_producto ASC
        """
        df = con.execute(query).df()
        if df.empty:
            return json.dumps({"error": f"No se encontraron recomendaciones para el cliente con ID {client_id}. Valida si ya posee todos los productos activos."}, ensure_ascii=False)
            
        recommendations = df.to_dict(orient="records")
        for rec in recommendations:
            for k, v in rec.items():
                if pd.api.types.is_datetime64_any_dtype(type(v)) or hasattr(v, 'strftime'):
                    rec[k] = str(v)
                elif pd.isna(v):
                    rec[k] = None
                    
        # Medir latencia
        MCP_TOOL_LATENCY.labels(tool_name="get_client_recommendation").observe(time.time() - start_t)
        return json.dumps({"status": "success", "data": recommendations}, indent=4, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error al consultar las recomendaciones del cliente: {str(e)}"}, ensure_ascii=False)
    finally:
        con.close()

@mcp.tool()
def get_model_performance() -> str:
    """
    Obtiene las métricas de rendimiento del recomendador entrenado (ROC-AUC, Accuracy@1 y Accuracy@3)
    y los mejores hiperparámetros encontrados.
    
    Returns:
        str: JSON con el rendimiento del modelo.
    """
    MCP_TOOL_CALLS.labels(tool_name="get_model_performance").inc()
    start_t = time.time()
    
    metrics_path = PROJECT_ROOT / "models" / "metrics.json"
    if not metrics_path.exists():
        return json.dumps({"error": "Métricas no encontradas. Corre train_model.py primero para entrenar y evaluar el modelo."}, ensure_ascii=False)
        
    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
            
        # Medir latencia
        MCP_TOOL_LATENCY.labels(tool_name="get_model_performance").observe(time.time() - start_t)
        return json.dumps({"status": "success", "data": metrics}, indent=4, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error al cargar las métricas del modelo: {str(e)}"}, ensure_ascii=False)

@mcp.tool()
def get_model_explainability() -> str:
    """
    Obtiene el top 5 de variables con mayor peso predictivo en el Random Forest para transparencia.
    
    Returns:
        str: JSON con la explicabilidad del modelo de recomendación.
    """
    MCP_TOOL_CALLS.labels(tool_name="get_model_explainability").inc()
    start_t = time.time()
    
    metrics_path = PROJECT_ROOT / "models" / "metrics.json"
    if not metrics_path.exists():
        return json.dumps({"error": "Métricas no encontradas. Corre train_model.py primero para entrenar el modelo."}, ensure_ascii=False)
        
    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
        importances = metrics.get("feature_importances", {})
        
        # Medir latencia
        MCP_TOOL_LATENCY.labels(tool_name="get_model_explainability").observe(time.time() - start_t)
        return json.dumps({"status": "success", "data": importances}, indent=4, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error al cargar la explicabilidad del modelo: {str(e)}"}, ensure_ascii=False)

@mcp.tool()
def get_product_catalog() -> str:
    """
    Obtiene la lista completa de productos financieros disponibles en el catálogo de la institución.
    
    Returns:
        str: JSON con el catálogo de productos financieros.
    """
    MCP_TOOL_CALLS.labels(tool_name="get_product_catalog").inc()
    start_t = time.time()
    
    productos_path = PROJECT_ROOT / "data" / "silver" / "productos.parquet"
    if not productos_path.exists():
        return json.dumps({"error": "Catálogo de productos no encontrado. Corre data_processing.py primero."}, ensure_ascii=False)
        
    con = get_db_connection()
    try:
        query = f"""
            SELECT id_producto, nombre_producto, categoria_producto, campo_original
            FROM read_parquet('{productos_path}')
            ORDER BY id_producto ASC
        """
        df = con.execute(query).df()
        catalog = df.to_dict(orient="records")
        
        # Medir latencia
        MCP_TOOL_LATENCY.labels(tool_name="get_product_catalog").observe(time.time() - start_t)
        return json.dumps({"status": "success", "data": catalog}, indent=4, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error al consultar el catálogo de productos: {str(e)}"}, ensure_ascii=False)
    finally:
        con.close()

# ─── DEFINICIÓN DE MCP PROMPTS ────────────────────────────────────────────────
@mcp.prompt()
def preparar_briefing_comercial(client_id: int) -> str:
    """
    Crea una plantilla estructurada de propuesta comercial (sales pitch) y briefing
    para un cliente específico basado en sus recomendaciones del modelo.
    """
    # Intentar obtener perfil y recomendación directamente
    profile_json = get_client_profile(client_id)
    rec_json = get_client_recommendation(client_id)
    
    return f"""Eres un asesor comercial bancario altamente experimentado. 
Utilizando la información provista, prepara una propuesta de venta hiper-personalizada (sales pitch) para el cliente {client_id}.

### Información de Perfil del Cliente:
{profile_json}

### Recomendación del Siguiente Mejor Producto:
{rec_json}

### Instrucciones del Briefing:
1. **Apertura de la conversación:** Un saludo profesional y empático.
2. **Justificación de la oferta:** Explica por qué este producto específico le conviene al cliente (por ejemplo, basándote en su segmento, ingresos o comportamiento).
3. **Manejo de objeciones:** Anticipa una posible objeción basada en su perfil.
4. **Llamado a la acción (Call to Action):** Cierre claro para concertar una cita o activar el producto.

Genera el guion en un tono profesional, claro y persuasivo."""

if __name__ == "__main__":
    logger.info("Iniciando servidor MCP...")
    # Iniciar el servidor MCP (comunicación estándar por stdin/stdout)
    mcp.run()
