"""
Módulo de Entrenamiento y Validación del Modelo Predictivo.
Crea el preprocesador, el clasificador y entrena el pipeline completo.
Guarda las métricas en un JSON para consumo del servidor MCP.
"""

import sys
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import RandomizedSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score

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

def calculate_accuracy_at_k(y_true, y_prob, client_ids, k=3):
    """
    Calcula la métrica Accuracy@K utilizando operaciones vectorizadas puras de NumPy sin bucles.
    """
    sort_idx = np.lexsort((-y_prob, client_ids))
    sorted_clients = client_ids[sort_idx]
    sorted_y = y_true[sort_idx]
    
    unique_clients, first_indices = np.unique(sorted_clients, return_index=True)
    
    repeats = np.diff(np.concatenate((first_indices, [len(sorted_clients)])))
    first_idx_repeated = np.repeat(first_indices, repeats)
    ranks = np.arange(len(sorted_clients)) - first_idx_repeated
    
    is_top_k = ranks < k
    top_k_y = sorted_y[is_top_k]
    top_k_clients = sorted_clients[is_top_k]
    
    hits_clients = top_k_clients[top_k_y == 1]
    unique_hits = np.unique(hits_clients)
    
    return len(unique_hits) / len(unique_clients) if len(unique_clients) > 0 else 0.0

def train_model(base_dir: Path):
    """
    Entrena el pipeline de machine learning completo, realiza tuning
    de hiperparámetros y evalúa el rendimiento sobre validación cruzada.
    """
    base_dir = Path(base_dir)
    gold_dir = base_dir / "data" / "gold"
    models_dir = base_dir / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Configurar logger
    log_file = base_dir / "logs" / "pipeline.log"
    logger = setup_logger(log_file)
    
    start_time = time.time()
    logger.info("[ML] Cargando matrices analíticas de la capa Gold...")
    train_path = gold_dir / "dataset_entrenamiento_nbp.parquet"
    if not train_path.exists():
        logger.error(f"[ML] No existe el dataset de entrenamiento en {train_path}. Por favor ejecuta feature_engineering.py primero.")
        return
        
    train_df = pd.read_parquet(train_path)
    
    # 2. Definir preprocesamiento de variables (Añadiendo las 2 nuevas features)
    num_cols = ["edad", "antiguedad", "renta", "cantidad_productos_actuales", "ratio_tenencia_ahorro", "ratio_tenencia_credito"]
    cat_cols = ["segmento", "categoria_producto_candidato"]
    passthrough_cols = ["ind_actividad_cliente", "tiene_cuenta", "tiene_credito", "tiene_tarjeta", "tiene_inversion"]
    
    preprocessor = ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols)
        ],
        remainder="passthrough"
    )
    
    # 3. Estructurar el Pipeline Completo
    full_pipeline = Pipeline(steps=[
        ("preprocessor", preprocessor),
        ("classifier", RandomForestClassifier(random_state=42, n_jobs=-1))
    ])
    
    # 4. Dividir en Entrenamiento y Validación (80/20 por cliente)
    unique_clients = train_df["id_cliente"].unique()
    np.random.seed(42)
    np.random.shuffle(unique_clients)
    split_idx = int(len(unique_clients) * 0.8)
    train_clients = unique_clients[:split_idx]
    val_clients = unique_clients[split_idx:]
    
    train_sub = train_df[train_df["id_cliente"].isin(train_clients)]
    val_sub = train_df[train_df["id_cliente"].isin(val_clients)]
    
    features = num_cols + cat_cols + passthrough_cols
    
    X_train = train_sub[features]
    y_train = train_sub["y"].astype(int)
    X_val = val_sub[features]
    y_val = val_sub["y"].astype(int)
    
    logger.info(f"[ML] Entrenamiento: {X_train.shape[0]} filas | Validación: {X_val.shape[0]} filas")
    
    # 5. Tuning de Hiperparámetros con RandomizedSearchCV
    param_dist = {
        "classifier__n_estimators": [50, 100],
        "classifier__max_depth": [6, 10, 14],
        "classifier__min_samples_leaf": [2, 5]
    }
    
    logger.info("[ML] Iniciando optimización de hiperparámetros (Tuning Layer)...")
    search = RandomizedSearchCV(
        full_pipeline, param_distributions=param_dist, 
        n_iter=5, cv=3, scoring="roc_auc", random_state=42, n_jobs=-1
    )
    search.fit(X_train, y_train)
    
    best_pipeline = search.best_estimator_
    logger.info(f"[ML] Mejores parámetros: {search.best_params_}")
    
    # 6. Evaluación de Validación
    val_probs = best_pipeline.predict_proba(X_val)[:, 1]
    val_auc = roc_auc_score(y_val, val_probs)
    logger.info(f"[ML] Validación ROC-AUC: {val_auc:.4%}")
    
    client_ids_val = val_sub["id_cliente"].values
    acc_1 = calculate_accuracy_at_k(y_val.values, val_probs, client_ids_val, k=1)
    acc_3 = calculate_accuracy_at_k(y_val.values, val_probs, client_ids_val, k=3)
    
    logger.info(f"[ML] Validación Accuracy@1: {acc_1:.4%}")
    logger.info(f"[ML] Validación Accuracy@3: {acc_3:.4%}")
    
    # 7. Extracción de Importancia de Variables (Feature Importance / Explicabilidad)
    logger.info("[ML] Calculando importancia de las variables para explicabilidad...")
    cat_encoder = best_pipeline.named_steps["preprocessor"].named_transformers_["cat"]
    cat_features_out = list(cat_encoder.get_feature_names_out(cat_cols))
    
    # Orden de columnas resultante de ColumnTransformer
    transformed_feature_names = num_cols + cat_features_out + passthrough_cols
    importances = best_pipeline.named_steps["classifier"].feature_importances_
    
    feature_importance_dict = dict(zip(transformed_feature_names, importances))
    sorted_importances = sorted(feature_importance_dict.items(), key=lambda x: x[1], reverse=True)
    top_5_importances = {k: round(float(v), 5) for k, v in sorted_importances[:5]}
    logger.info(f"[ML] Top 5 variables más influyentes: {top_5_importances}")
    
    # 8. Guardar las métricas de rendimiento en JSON
    metrics = {
        "roc_auc": float(val_auc),
        "accuracy_at_1": float(acc_1),
        "accuracy_at_3": float(acc_3),
        "best_params": search.best_params_,
        "feature_importances": top_5_importances
    }
    metrics_path = models_dir / "metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=4, ensure_ascii=False)
    logger.info(f"[ML] Métricas y explicabilidad guardadas en: {metrics_path}")
    
    # 9. Guardar el Pipeline Completo
    model_path = models_dir / "modelo_next_best_product.pkl"
    joblib.dump(best_pipeline, model_path)
    logger.info(f"[ML] Pipeline de inferencia guardado en: {model_path}")
    
    # Registrar métricas del pipeline
    execution_time = time.time() - start_time
    save_pipeline_metric(base_dir, "ml_execution_time_seconds", round(execution_time, 4))

def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    train_model(base)

if __name__ == "__main__":
    main()
