"""
Módulo de Feature Engineering (Silver -> Gold).
Gobernado por la clase FeatureEngineer para la arquitectura Medallón.
"""

import sys
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import duckdb

def setup_logger(log_path: Path):
    logger = logging.getLogger("nbp_pipeline")
    logger.setLevel(logging.INFO)
    
    if not logger.handlers:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Consola
        c_handler = logging.StreamHandler(sys.stdout)
        c_handler.setFormatter(formatter)
        logger.addHandler(c_handler)
        
        # Archivo rotativo
        f_handler = RotatingFileHandler(log_path, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
        f_handler.setFormatter(formatter)
        logger.addHandler(f_handler)
        
    return logger

def save_pipeline_metric(base_dir: Path, key: str, value):
    metrics_path = base_dir / "models" / "pipeline_metrics.json"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {}
    if metrics_path.exists():
        try:
            with open(metrics_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
            
    data[key] = value
    
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

class FeatureEngineer:
    """
    Clase para la creación de variables explicativas y estructuración de matrices analíticas:
    - Agregación temporal de productos por categorías.
    - Generación de matriz de candidatos cartesiana (excluyendo activos).
    - Simulación reproducible de conversiones para entrenamiento (y).
    """
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.silver_dir = self.base_dir / "data" / "silver"
        self.gold_dir = self.base_dir / "data" / "gold"
        
        # Asegurar existencia de directorios
        self.gold_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurar logger
        log_file = self.base_dir / "logs" / "pipeline.log"
        self.logger = setup_logger(log_file)

    def silver_to_gold(self):
        """
        Capa Gold: Genera la matriz analítica de candidatos para entrenamiento y predicción.
        """
        start_time = time.time()
        self.logger.info("[Gold] Iniciando cruces de Feature Engineering...")
        con = duckdb.connect(database=":memory:")
        
        # Registrar tablas de Silver en DuckDB
        parquet_files = list(self.silver_dir.glob("*.parquet"))
        if not parquet_files:
            self.logger.error(f"[Gold] No hay archivos Parquet en {self.silver_dir} para procesar.")
            return
            
        for p in parquet_files:
            con.execute(f"CREATE OR REPLACE VIEW silver_{p.stem} AS SELECT * FROM read_parquet('{p}')")

        # 1. Llevar tenencia a formato consolidado por cliente/mes
        con.execute("""
            CREATE OR REPLACE TABLE test_product_tenure AS
            SELECT 
                em.id_cliente,
                em.fecha_corte,
                em.origen_datos,
                pm.id_producto,
                pm.estado_producto
            FROM silver_cliente_estado_mensual em
            LEFT JOIN silver_cliente_producto_mensual pm ON em.id_cliente = pm.id_cliente
            WHERE em.origen_datos = 'test'
        """)
        
        con.execute("""
            CREATE OR REPLACE TABLE combined_product_tenure AS
            SELECT id_cliente, fecha_corte, origen_datos, id_producto, estado_producto 
            FROM silver_cliente_producto_mensual
            UNION ALL
            SELECT id_cliente, fecha_corte, origen_datos, id_producto, COALESCE(estado_producto, 0) as estado_producto
            FROM test_product_tenure
        """)
        
        # Consultar conteos en catálogo para el cálculo de los ratios
        total_ahorro_catalog = con.execute("SELECT COUNT(*) FROM silver_productos WHERE categoria_producto IN ('Ahorro', 'Cuenta')").fetchone()[0]
        total_credito_catalog = con.execute("SELECT COUNT(*) FROM silver_productos WHERE categoria_producto = 'Crédito'").fetchone()[0]
        
        # Evitar divisiones por cero
        total_ahorro_catalog = max(total_ahorro_catalog, 1)
        total_credito_catalog = max(total_credito_catalog, 1)
        
        self.logger.info(f"[Gold] Total catálogo ahorro: {total_ahorro_catalog} | Crédito: {total_credito_catalog}")

        # 2. Computar tenencias por categoría y nuevas variables predictivas (ratios)
        con.execute(f"""
            CREATE OR REPLACE TABLE combined_client_aggregates AS
            SELECT 
                cpt.id_cliente,
                cpt.fecha_corte,
                cpt.origen_datos,
                COUNT(CASE WHEN cpt.estado_producto = 1 THEN 1 END) as cantidad_productos_actuales,
                MAX(CASE WHEN p.categoria_producto = 'Cuenta' AND cpt.estado_producto = 1 THEN 1 ELSE 0 END) as tiene_cuenta,
                MAX(CASE WHEN p.categoria_producto = 'Crédito' AND cpt.estado_producto = 1 THEN 1 ELSE 0 END) as tiene_credito,
                MAX(CASE WHEN p.categoria_producto = 'Tarjeta' AND cpt.estado_producto = 1 THEN 1 ELSE 0 END) as tiene_tarjeta,
                MAX(CASE WHEN p.categoria_producto = 'Inversión' AND cpt.estado_producto = 1 THEN 1 ELSE 0 END) as tiene_inversion,
                
                -- Nuevas variables predictivas (Mejoras)
                CAST(COUNT(CASE WHEN p.categoria_producto IN ('Ahorro', 'Cuenta') AND cpt.estado_producto = 1 THEN 1 END) AS DOUBLE) / {total_ahorro_catalog} as ratio_tenencia_ahorro,
                CAST(COUNT(CASE WHEN p.categoria_producto = 'Crédito' AND cpt.estado_producto = 1 THEN 1 END) AS DOUBLE) / {total_credito_catalog} as ratio_tenencia_credito
            FROM combined_product_tenure cpt
            JOIN silver_productos p ON cpt.id_producto = p.id_producto
            GROUP BY 1, 2, 3
        """)

        # 3. Construir la matriz analítica de candidatos (excluyendo tenencias actuales para recomendación)
        con.execute("""
            CREATE OR REPLACE TABLE candidate_matrix AS
            SELECT 
                em.id_cliente,
                em.fecha_corte,
                em.origen_datos,
                p.id_producto as id_producto_candidato,
                em.age as edad,
                em.antiguedad,
                em.renta,
                s.descripcion_segmento as segmento,
                em.ind_actividad_cliente,
                COALESCE(cpt.estado_producto, 0) as tiene_producto_actualmente,
                COALESCE(cca.cantidad_productos_actuales, 0) as cantidad_productos_actuales,
                COALESCE(cca.tiene_cuenta, 0) as tiene_cuenta,
                COALESCE(cca.tiene_credito, 0) as tiene_credito,
                COALESCE(cca.tiene_tarjeta, 0) as tiene_tarjeta,
                COALESCE(cca.tiene_inversion, 0) as tiene_inversion,
                
                -- Inclusión de nuevas variables
                COALESCE(cca.ratio_tenencia_ahorro, 0.0) as ratio_tenencia_ahorro,
                COALESCE(cca.ratio_tenencia_credito, 0.0) as ratio_tenencia_credito,
                
                p.categoria_producto as categoria_producto_candidato,
                p.nombre_producto as nombre_producto_candidato
            FROM silver_cliente_estado_mensual em
            LEFT JOIN silver_segmentos s ON em.id_segmento = s.id_segmento
            CROSS JOIN silver_productos p
            LEFT JOIN combined_product_tenure cpt 
                ON em.id_cliente = cpt.id_cliente 
                AND em.fecha_corte = cpt.fecha_corte 
                AND p.id_producto = cpt.id_producto
            LEFT JOIN combined_client_aggregates cca 
                ON em.id_cliente = cca.id_cliente 
                AND em.fecha_corte = cca.fecha_corte
        """)

        # 4. Generación lógica y reproducible del target y (simulación bancaria de conversión MoM)
        con.execute("""
            CREATE OR REPLACE TABLE gold_dataset AS
            SELECT 
                id_cliente,
                fecha_corte,
                origen_datos,
                id_producto_candidato,
                edad,
                antiguedad,
                renta,
                segmento,
                ind_actividad_cliente,
                tiene_producto_actualmente,
                cantidad_productos_actuales,
                tiene_cuenta,
                tiene_credito,
                tiene_tarjeta,
                tiene_inversion,
                
                -- Nuevas variables predictivas
                ratio_tenencia_ahorro,
                ratio_tenencia_credito,
                
                categoria_producto_candidato,
                nombre_producto_candidato,
                CASE 
                    WHEN origen_datos = 'test' THEN NULL
                    WHEN tiene_producto_actualmente = 1 THEN 0
                    ELSE 
                        CASE 
                            WHEN segmento = '01 - TOP' AND categoria_producto_candidato = 'Inversión' AND (abs(hash(id_cliente)) % 100) < 15 THEN 1
                            WHEN segmento = '03 - UNIVERSITARIO' AND categoria_producto_candidato = 'Cuenta' AND (abs(hash(id_cliente)) % 100) < 22 THEN 1
                            WHEN edad BETWEEN 30 AND 50 AND categoria_producto_candidato = 'Crédito' AND (abs(hash(id_cliente)) % 100) < 12 THEN 1
                            WHEN renta > 120000 AND categoria_producto_candidato = 'Tarjeta' AND (abs(hash(id_cliente)) % 100) < 18 THEN 1
                            WHEN ind_actividad_cliente = 1 AND (abs(hash(id_cliente + id_producto_candidato)) % 100) < 4 THEN 1
                            ELSE IF((abs(hash(id_cliente * id_producto_candidato)) % 100) < 1, 1, 0)
                        END
                END as y
            FROM candidate_matrix
        """)

        # Guardar dataset completo de Gold
        con.execute(f"COPY gold_dataset TO '{self.gold_dir / 'dataset_next_best_product_gold.parquet'}' (FORMAT PARQUET)")
        
        # Subconjunto Entrenamiento (Solo train candidatos)
        con.execute(f"""
            COPY (SELECT * FROM gold_dataset WHERE origen_datos = 'train' AND tiene_producto_actualmente = 0) 
            TO '{self.gold_dir / 'dataset_entrenamiento_nbp.parquet'}' (FORMAT PARQUET)
        """)
        
        # Subconjunto Predicción (Solo test candidatos)
        con.execute(f"""
            COPY (SELECT * FROM gold_dataset WHERE origen_datos = 'test' AND tiene_producto_actualmente = 0) 
            TO '{self.gold_dir / 'dataset_prediccion_nbp.parquet'}' (FORMAT PARQUET)
        """)
        
        gold_train_rows = con.execute("SELECT COUNT(*) FROM gold_dataset WHERE origen_datos = 'train' AND tiene_producto_actualmente = 0").fetchone()[0]
        gold_test_rows = con.execute("SELECT COUNT(*) FROM gold_dataset WHERE origen_datos = 'test' AND tiene_producto_actualmente = 0").fetchone()[0]
        
        execution_time = time.time() - start_time
        save_pipeline_metric(self.base_dir, "gold_train_rows_processed", gold_train_rows)
        save_pipeline_metric(self.base_dir, "gold_test_rows_processed", gold_test_rows)
        save_pipeline_metric(self.base_dir, "gold_execution_time_seconds", round(execution_time, 4))
        
        self.logger.info(f"[Gold] Matriz analítica de candidatos construida y guardada. Train: {gold_train_rows} filas | Test: {gold_test_rows} filas | en {execution_time:.2f}s")
        con.close()

def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    engineer = FeatureEngineer(base)
    engineer.silver_to_gold()

if __name__ == "__main__":
    main()
