"""
Módulo de Ingesta y Procesamiento de Datos (Raw -> Bronze -> Silver).
Gobernado por la clase DataProcessor para la arquitectura Medallón.
"""

import sys
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import pandas as pd
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

class DataProcessor:
    """
    Clase para el procesamiento de datos del pipeline Medallón:
    - Capa Bronze: Ingesta de CSV a Parquet 1:1.
    - Capa Silver: Limpieza, tipado y consistencia relacional.
    """
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "data" / "raw"
        self.bronze_dir = self.base_dir / "data" / "bronze"
        self.silver_dir = self.base_dir / "data" / "silver"
        
        # Asegurar existencia de directorios
        self.bronze_dir.mkdir(parents=True, exist_ok=True)
        self.silver_dir.mkdir(parents=True, exist_ok=True)
        
        # Configurar logger
        log_file = self.base_dir / "logs" / "pipeline.log"
        self.logger = setup_logger(log_file)

    def raw_to_bronze(self):
        """
        Capa Bronze: Convierte archivos CSV a Parquet conservando el esquema original.
        """
        start_time = time.time()
        self.logger.info("[Bronze] Iniciando conversión 1:1 de CSV a Parquet...")
        csv_files = list(self.raw_dir.glob("*.csv"))
        if not csv_files:
            self.logger.warning(f"[Bronze] No se encontraron archivos CSV en {self.raw_dir}")
            return
            
        total_rows = 0
        for csv_file in csv_files:
            table_name = csv_file.stem
            parquet_path = self.bronze_dir / f"{table_name}.parquet"
            df = pd.read_csv(csv_file)
            df.to_parquet(parquet_path, index=False)
            total_rows += df.shape[0]
            self.logger.info(f"[Bronze] Convertido: {csv_file.name} -> {table_name}.parquet ({df.shape[0]} filas)")
            
        execution_time = time.time() - start_time
        save_pipeline_metric(self.base_dir, "bronze_rows_processed", total_rows)
        save_pipeline_metric(self.base_dir, "bronze_execution_time_seconds", round(execution_time, 4))
        self.logger.info(f"[Bronze] Conversión finalizada. Total filas: {total_rows} en {execution_time:.2f}s")

    def bronze_to_silver(self):
        """
        Capa Silver: Limpieza de cadenas, tipado estricto, imputación estadística
        de valores faltantes mediante la mediana y cálculo MoM de altas de producto.
        """
        start_time = time.time()
        self.logger.info("[Silver] Iniciando transformaciones de limpieza y tipado...")
        con = duckdb.connect(database=":memory:")
        
        # Registrar tablas de Bronze en DuckDB
        parquet_files = list(self.bronze_dir.glob("*.parquet"))
        if not parquet_files:
            self.logger.error(f"[Silver] No hay archivos Parquet en {self.bronze_dir} para procesar.")
            return
            
        for p in parquet_files:
            con.execute(f"CREATE OR REPLACE VIEW bronze_{p.stem} AS SELECT * FROM read_parquet('{p}')")

        # 1. Provincias
        self.logger.info("[Silver] Procesando provincias...")
        con.execute(f"""
            CREATE OR REPLACE TABLE silver_provincias AS
            SELECT DISTINCT
                CAST(cod_prov AS INTEGER) as cod_prov,
                TRIM(CAST(nombre_provincia AS VARCHAR)) as nombre_provincia
            FROM bronze_provincias
            WHERE cod_prov IS NOT NULL
        """)
        con.execute(f"COPY silver_provincias TO '{self.silver_dir / 'provincias.parquet'}' (FORMAT PARQUET)")

        # 2. Segmentos
        self.logger.info("[Silver] Procesando segmentos...")
        con.execute(f"""
            CREATE OR REPLACE TABLE silver_segmentos AS
            SELECT DISTINCT
                CAST(id_segmento AS INTEGER) as id_segmento,
                TRIM(CAST(descripcion_segmento AS VARCHAR)) as descripcion_segmento
            FROM bronze_segmentos
            WHERE id_segmento IS NOT NULL
        """)
        con.execute(f"COPY silver_segmentos TO '{self.silver_dir / 'segmentos.parquet'}' (FORMAT PARQUET)")

        # 3. Productos
        self.logger.info("[Silver] Procesando productos...")
        con.execute(f"""
            CREATE OR REPLACE TABLE silver_productos AS
            SELECT DISTINCT
                CAST(id_producto AS INTEGER) as id_producto,
                TRIM(CAST(campo_original AS VARCHAR)) as campo_original,
                TRIM(CAST(nombre_producto AS VARCHAR)) as nombre_producto,
                TRIM(CAST(categoria_producto AS VARCHAR)) as categoria_producto
            FROM bronze_productos
            WHERE id_producto IS NOT NULL
        """)
        con.execute(f"COPY silver_productos TO '{self.silver_dir / 'productos.parquet'}' (FORMAT PARQUET)")

        # 4. Clientes
        self.logger.info("[Silver] Procesando clientes...")
        con.execute(f"""
            CREATE OR REPLACE TABLE silver_clientes AS
            SELECT DISTINCT
                CAST(id_cliente AS INTEGER) as id_cliente,
                TRIM(CAST(ind_empleado AS VARCHAR)) as ind_empleado,
                TRIM(CAST(pais_residencia AS VARCHAR)) as pais_residencia,
                TRIM(CAST(sexo AS VARCHAR)) as sexo,
                strptime(fecha_alta, '%Y-%m-%d')::DATE as fecha_alta,
                TRIM(CAST(conyuemp AS VARCHAR)) as conyuemp,
                TRIM(CAST(canal_entrada AS VARCHAR)) as canal_entrada,
                TRIM(CAST(indfall AS VARCHAR)) as indfall,
                CAST(aparece_en_train AS INTEGER) as aparece_en_train,
                CAST(aparece_en_test AS INTEGER) as aparece_en_test
            FROM bronze_clientes
            WHERE id_cliente IS NOT NULL
        """)
        con.execute(f"COPY silver_clientes TO '{self.silver_dir / 'clientes.parquet'}' (FORMAT PARQUET)")

        # Mediana para imputaciones en Estado Mensual
        median_age = con.execute("SELECT MEDIAN(age) FROM bronze_cliente_estado_mensual").fetchone()[0]
        median_renta = con.execute("SELECT MEDIAN(renta) FROM bronze_cliente_estado_mensual").fetchone()[0]

        # 5. Cliente Estado Mensual
        self.logger.info("[Silver] Procesando cliente_estado_mensual...")
        con.execute(f"""
            CREATE OR REPLACE TABLE silver_cliente_estado_mensual AS
            SELECT
                CAST(id_cliente AS INTEGER) as id_cliente,
                strptime(fecha_corte, '%Y-%m-%d')::DATE as fecha_corte,
                TRIM(CAST(origen_datos AS VARCHAR)) as origen_datos,
                CAST(es_test AS INTEGER) as es_test,
                COALESCE(CAST(age AS INTEGER), CAST({median_age} AS INTEGER)) as age,
                CAST(antiguedad AS INTEGER) as antiguedad,
                CAST(ind_nuevo AS INTEGER) as ind_nuevo,
                CAST(indrel AS INTEGER) as indrel,
                TRIM(CAST(indrel_1mes AS VARCHAR)) as indrel_1mes,
                TRIM(CAST(tiprel_1mes AS VARCHAR)) as tiprel_1mes,
                TRIM(CAST(indresi AS VARCHAR)) as indresi,
                TRIM(CAST(indext AS VARCHAR)) as indext,
                CAST(ind_actividad_cliente AS INTEGER) as ind_actividad_cliente,
                COALESCE(renta, {median_renta}) as renta,
                CAST(cod_prov AS INTEGER) as cod_prov,
                COALESCE(CAST(id_segmento AS INTEGER), -1) as id_segmento
            FROM bronze_cliente_estado_mensual
            WHERE id_cliente IS NOT NULL
        """)
        con.execute(f"COPY silver_cliente_estado_mensual TO '{self.silver_dir / 'cliente_estado_mensual.parquet'}' (FORMAT PARQUET)")

        # 6. Cliente Producto Mensual (Tenencia de productos)
        self.logger.info("[Silver] Procesando cliente_producto_mensual...")
        con.execute(f"""
            CREATE OR REPLACE TABLE silver_cliente_producto_mensual AS
            SELECT
                CAST(id_cliente AS INTEGER) as id_cliente,
                strptime(fecha_corte, '%Y-%m-%d')::DATE as fecha_corte,
                TRIM(CAST(origen_datos AS VARCHAR)) as origen_datos,
                CAST(id_producto AS INTEGER) as id_producto,
                MAX(CAST(estado_producto AS INTEGER)) as estado_producto
            FROM bronze_cliente_producto_mensual
            WHERE id_cliente IS NOT NULL AND id_producto IS NOT NULL
            GROUP BY 1, 2, 3, 4
        """)
        con.execute(f"COPY silver_cliente_producto_mensual TO '{self.silver_dir / 'cliente_producto_mensual.parquet'}' (FORMAT PARQUET)")

        # 7. Cliente Producto Alta (Cálculo lógico MoM)
        self.logger.info("[Silver] Calculando cliente_producto_alta...")
        con.execute(f"""
            CREATE OR REPLACE TABLE silver_cliente_producto_alta AS
            WITH lag_tenure AS (
                SELECT 
                    id_cliente,
                    fecha_corte,
                    origen_datos,
                    id_producto,
                    estado_producto,
                    LAG(estado_producto) OVER(PARTITION BY id_cliente, id_producto ORDER BY fecha_corte) as prev_estado
                FROM silver_cliente_producto_mensual
            )
            SELECT 
                id_cliente,
                fecha_corte,
                origen_datos,
                id_producto,
                1 AS flag_alta_producto
            FROM lag_tenure
            WHERE prev_estado = 0 AND estado_producto = 1
        """)
        con.execute(f"COPY silver_cliente_producto_alta TO '{self.silver_dir / 'cliente_producto_alta.parquet'}' (FORMAT PARQUET)")
        
        # Conteo final de registros en la capa Silver
        silver_rows = con.execute("SELECT COUNT(*) FROM silver_cliente_estado_mensual").fetchone()[0]
        execution_time = time.time() - start_time
        save_pipeline_metric(self.base_dir, "silver_rows_processed", silver_rows)
        save_pipeline_metric(self.base_dir, "silver_execution_time_seconds", round(execution_time, 4))
        
        self.logger.info(f"[Silver] Procesamiento y exportación finalizados con éxito. Filas Silver: {silver_rows} en {execution_time:.2f}s")
        con.close()

def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    processor = DataProcessor(base)
    processor.raw_to_bronze()
    processor.bronze_to_silver()

if __name__ == "__main__":
    main()
