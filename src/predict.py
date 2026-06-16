"""
Módulo de Inferencia (Predict).
Carga el modelo serializado, realiza predicciones sobre candidatos del mes de prueba,
calcula rankings de recomendaciones y exporta las predicciones completas y las recomendaciones Top-1.
"""

import sys
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import joblib
import pandas as pd

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

def make_predictions(base_dir: Path):
    """
    Carga el pipeline entrenado, corre la inferencia sobre el set de predicción,
    ordena los candidatos y guarda los archivos resultantes en la capa Gold.
    """
    base_dir = Path(base_dir)
    gold_dir = base_dir / "data" / "gold"
    models_dir = base_dir / "models"
    
    # Configurar logger
    log_file = base_dir / "logs" / "pipeline.log"
    logger = setup_logger(log_file)
    
    start_time = time.time()
    
    # 1. Cargar modelo y datos de prueba
    model_path = models_dir / "modelo_next_best_product.pkl"
    pred_data_path = gold_dir / "dataset_prediccion_nbp.parquet"
    
    if not model_path.exists():
        logger.error(f"[Inferencia] No se encontró el modelo en {model_path}. Corre train_model.py primero.")
        return
    if not pred_data_path.exists():
        logger.error(f"[Inferencia] No se encontró el dataset de predicción en {pred_data_path}. Corre feature_engineering.py primero.")
        return
        
    logger.info("[Inferencia] Cargando modelo serializado y dataset de predicción...")
    model = joblib.load(model_path)
    test_df = pd.read_parquet(pred_data_path)
    
    # Variables explicativas (Añadiendo las 2 nuevas features)
    num_cols = ["edad", "antiguedad", "renta", "cantidad_productos_actuales", "ratio_tenencia_ahorro", "ratio_tenencia_credito"]
    cat_cols = ["segmento", "categoria_producto_candidato"]
    passthrough_cols = ["ind_actividad_cliente", "tiene_cuenta", "tiene_credito", "tiene_tarjeta", "tiene_inversion"]
    features = num_cols + cat_cols + passthrough_cols
    
    # 2. Correr inferencia probabilística
    logger.info("[Inferencia] Calculando probabilidades de adquisición...")
    X_test = test_df[features]
    test_probs = model.predict_proba(X_test)[:, 1]
    
    test_results = test_df.copy()
    test_results["probabilidad_adquisicion"] = test_probs
    
    # 3. Calcular ranking de candidatos por cliente (orden descendente por probabilidad)
    logger.info("[Inferencia] Generando ranking de recomendaciones por cliente...")
    test_results["ranking_producto"] = test_results.groupby("id_cliente")["probabilidad_adquisicion"].rank(
        method="first", ascending=False
    ).astype(int)
    
    # 4. Tabla de Predicciones Completa
    predicciones = test_results[[
        "id_cliente", "fecha_corte", "id_producto_candidato", 
        "nombre_producto_candidato", "categoria_producto_candidato", 
        "probabilidad_adquisicion", "ranking_producto"
    ]].rename(columns={
        "nombre_producto_candidato": "nombre_producto",
        "categoria_producto_candidato": "categoria_producto"
    }).sort_values(["id_cliente", "ranking_producto"])
    
    predictions_out = gold_dir / "predicciones_next_best_product.parquet"
    predicciones.to_parquet(predictions_out, index=False)
    logger.info(f"[Inferencia] Tabla completa de predicciones guardada en: {predictions_out} ({predicciones.shape[0]} filas)")
    
    # 5. Tabla de Recomendaciones (Solo el Top-1)
    recomendaciones = predicciones[predicciones["ranking_producto"] == 1].rename(columns={
        "nombre_producto": "producto_recomendado",
        "probabilidad_adquisicion": "probabilidad",
        "ranking_producto": "posicion_ranking"
    })
    
    recommendations_out = gold_dir / "recomendaciones_next_best_product.parquet"
    recomendaciones.to_parquet(recommendations_out, index=False)
    logger.info(f"[Inferencia] Tabla de recomendaciones Top-1 guardada en: {recommendations_out} ({recomendaciones.shape[0]} filas)")
    
    execution_time = time.time() - start_time
    save_pipeline_metric(base_dir, "inference_execution_time_seconds", round(execution_time, 4))
    
    logger.info(f"[Inferencia] Flujo de scoring y predicción completado exitosamente en {execution_time:.2f}s")

def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    make_predictions(base)

if __name__ == "__main__":
    main()
