# Informe Técnico de Modelado Predictivo: "Next Best Product"

Este informe detalla las decisiones de diseño, algoritmos, y métricas de evaluación asociadas a la solución analítica para el recomendador predictivo de productos financieros.

---

## 1. Tipo de Problema y Enfoque Algorítmico

El problema comercial de recomendar el "Siguiente Mejor Producto" (NBP) se formula como una tarea de **clasificación supervisada binaria**. 
Cada fila del conjunto de datos analítico representa un par **(cliente, producto candidato)** que el cliente **no posee actualmente** en el periodo de observación. El objetivo del modelo es estimar la probabilidad posterior de adquisición del producto:

$$\hat{y} = P(y = 1 \mid \text{cliente}, \text{mes}, \text{historial}, \text{producto candidato})$$

### Algoritmo: Random Forest Classifier
Se seleccionó un ensamble de árboles de decisión **Random Forest** debido a:
* **Manejo No Lineal de Relaciones**: Gran habilidad para capturar interacciones no lineales complejas entre variables demográficas (edad, ingresos) y tenencias actuales (diversificación).
* **Resistencia a Outliers y Sesgos**: Adecuado para trabajar con distribuciones sesgadas de ingresos (`renta`) y edad sin necesidad de transformaciones matemáticas complejas.
* **Tolerancia a Categorías Dispersas**: Excelente soporte nativo para variables categóricas previamente codificadas en One-Hot (como segmentos o categorías de productos).

---

## 2. Definición del Preprocesamiento de Variables

Para prevenir la fuga de información (data leakage) y asegurar la portabilidad, el modelado acopla todas las fases en un único objeto `Pipeline` de Scikit-Learn mediante un **ColumnTransformer**:

### Variables Cuantitativas (Numéricas)
* **edad**, **antiguedad**, **renta**, **cantidad_productos_actuales**.
* **Preprocesamiento**: Normalización estándar (`StandardScaler`) centrando la media en 0 y escalando a varianza unitaria.

### Variables Cualitativas (Categóricas)
* **segmento**, **categoria_producto_candidato**.
* **Preprocesamiento**: Codificación en One-Hot (`OneHotEncoder`). Para soportar la inferencia en producción con nuevas categorías desconocidas, el codificador se entrena con la configuración `handle_unknown='ignore'`, evitando caídas en tiempo de ejecución.

### Variables de Paso Directo (Passthrough)
* **ind_actividad_cliente** (transaccionalidad en el mes).
* **tiene_cuenta**, **tiene_credito**, **tiene_tarjeta**, **tiene_inversion** (variables booleanas de tenencias por categoría agregada).
* **Preprocesamiento**: Se pasan al estimador sin transformación adicional.

---

## 3. Estrategia de Validación y Optimización de Hiperparámetros

### Validación Cruzada por Cliente (Group Split)
Para evitar sesgar la evaluación (ya que un cliente puede tener múltiples filas candidatos en el mismo mes), el conjunto de entrenamiento se divide reservando un **80% de clientes para entrenamiento** y un **20% para validación**. Al segmentar por IDs únicos de clientes y no por registros individuales, se garantiza que ningún dato histórico del mismo cliente se filtre en validación cruzada.

### Optimización de Hiperparámetros (Tuning Layer)
Se implementa una búsqueda aleatoria cruzada (`RandomizedSearchCV`) con 3 pliegues (CV=3) optimizando la métrica **ROC-AUC** sobre el espacio de hiperparámetros del Random Forest:
* `classifier__n_estimators`: `[50, 100]` (número de estimadores).
* `classifier__max_depth`: `[6, 10, 14]` (profundidad máxima para prevenir sobreajuste).
* `classifier__min_samples_leaf`: `[2, 5]` (registros mínimos por hoja).

---

## 4. Métricas de Rendimiento en Validación

Las métricas del modelo entrenado se evalúan utilizando validación cruzada y se registran en `models/metrics.json`.

* **ROC-AUC**: Evalúa la capacidad general del recomendador para discriminar entre conversiones reales ($y=1$) y no-conversiones ($y=0$).
* **Accuracy@1 (Top 1 Recomendación)**: Mide el porcentaje de clientes para los cuales el producto con la **mayor probabilidad de adquisición** ($y_{prob}$ con rango = 1) resultó en una adquisición real en el siguiente periodo.
* **Accuracy@3 (Top 3 Recomendaciones)**: Mide el porcentaje de clientes para los cuales al menos uno de los **tres productos con mayor probabilidad** recomendados fue adquirido en la realidad.

---

## 5. Implementación Vectorizada de Accuracy@K (NumPy)

El cálculo de métricas de ranking para millones de observaciones en Python nativo suele ser lento. Por ello, se diseñó e implementó un algoritmo vectorizado puro en **NumPy** en la función `calculate_accuracy_at_k`:

```python
# Ordenamiento multillave indirecto y estable en memoria continua
sort_idx = np.lexsort((-y_prob, client_ids))
```

### Explicación del Algoritmo Vectorizado:
1. **Ordenamiento Rápido (`np.lexsort`)**: Ordena los registros del conjunto de validación de forma estable utilizando el identificador del cliente como clave primaria y la probabilidad descendente (usando `-y_prob`) como clave secundaria. Esto agrupa los productos de cada cliente de forma contigua, ordenados del más probable al menos probable.
2. **Cálculo de Límites de Clientes (`np.unique`)**: Identifica el índice inicial de cada grupo de cliente en el vector ordenado.
3. **Generación de Rangos Internos Vectoriales**: Resta a cada posición del vector ordenado el índice inicial de su cliente correspondiente. Mediante sustracción matricial pura, genera los rangos en base cero (`[0, 1, 2]` para los candidatos del primer cliente, `[0, 1, 2, 3]` para el segundo, etc.) de forma instantánea sobre millones de filas.
4. **Filtrado Top-K y Cálculo**: Aplica una máscara booleana (`rango < k`) para seleccionar los Top-K candidatos de cada cliente. Se identifican las intersecciones con adquisiciones reales ($y=1$) y se calcula la proporción de clientes con conversiones exitosas.

Esta implementación reduce la complejidad temporal de operaciones repetidas a nivel de intérprete, ejecutándose en complejidad $\mathcal{O}(N \log N)$ dominada por la velocidad en C de `np.lexsort`, haciendo el cálculo de Accuracy@K ideal para escalabilidad masiva en producción.
