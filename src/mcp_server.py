"""
Servidor MCP (Model Context Protocol) para el recomendador Next Best Product.
Expone herramientas para consultar predicciones de modelos, perfiles de clientes y métricas de desempeño.
"""

import os
import json
import sys
from pathlib import Path
import duckdb
import pandas as pd
from mcp.server.fastmcp import FastMCP

# Resolver de forma portable la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Instanciar el servidor FastMCP
mcp = FastMCP("Next Best Product Server")

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
        # Convertir fechas a strings para que sean serializables en JSON
        for k, v in profile.items():
            if pd.api.types.is_datetime64_any_dtype(type(v)) or hasattr(v, 'strftime'):
                profile[k] = str(v)
            elif pd.isna(v):
                profile[k] = None
                
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
    metrics_path = PROJECT_ROOT / "models" / "metrics.json"
    if not metrics_path.exists():
        return json.dumps({"error": "Métricas no encontradas. Corre train_model.py primero para entrenar y evaluar el modelo."}, ensure_ascii=False)
        
    try:
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
        return json.dumps({"status": "success", "data": metrics}, indent=4, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error al cargar las métricas del modelo: {str(e)}"}, ensure_ascii=False)

@mcp.tool()
def get_product_catalog() -> str:
    """
    Obtiene la lista completa de productos financieros disponibles en el catálogo de la institución.
    
    Returns:
        str: JSON con el catálogo de productos financieros.
    """
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
        return json.dumps({"status": "success", "data": catalog}, indent=4, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error al consultar el catálogo de productos: {str(e)}"}, ensure_ascii=False)
    finally:
        con.close()

if __name__ == "__main__":
    # Iniciar el servidor MCP (comunicación estándar por stdin/stdout)
    mcp.run()
