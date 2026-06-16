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
* **edad**, **antiguedad**, **renta**, **cantidad_productos_actuales**, **ratio_tenencia_ahorro**, **ratio_tenencia_credito**.
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

## 4. Métricas de Rendimiento en Validación (Fase 2)

Las métricas del modelo entrenado y optimizado en la **Fase 2** (registradas en `models/metrics.json`) reflejan el impacto de las nuevas reglas comerciales cruzadas en la conversión:

* **ROC-AUC (77.70%)**: Muestra una excelente capacidad de discriminación general del recomendador entre adquisiciones reales ($y=1$) y no adquisiciones ($y=0$).
* **Accuracy@1 (27.00%)**: El 27.00% de las veces que el modelo recomienda prioritariamente su mejor opción (rango 1), el cliente adquiere el producto en la realidad (un incremento respecto al 19.00% inicial).
* **Accuracy@3 (34.00%)**: El 34.00% de los clientes adquiere al menos uno de los tres mejores productos sugeridos (un incremento respecto al 23.00% inicial).

### Reglas de Conversión del Negocio (Simulación en Capa Gold)
Para entrenar un recomendador de alto impacto, la variable objetivo `y` en `feature_engineering.py` se refina implementando reglas de propensión financiera cruzada realistas:
1. **Inversión**: Clientes de segmento 'TOP' con cuenta activa y altos ingresos (`renta > 100,000`) muestran alta conversión a inversión.
2. **Cuenta**: Clientes de segmento 'UNIVERSITARIO' que tienen saldos o tenencias de ahorro (`ratio_tenencia_ahorro > 0.0`) muestran alta conversión a cuentas corrientes.
3. **Crédito**: Clientes en su pico laboral (`edad` entre 30 y 50 años) con renta estable (`renta > 80,000`) muestran propensión a créditos.
4. **Tarjeta**: Clientes con alta renta (`renta > 120,000`) y con crédito activo muestran alta propensión a conversión de tarjeta.
5. **Fidelización**: Clientes con 3 o más productos activos se consideran altamente fidelizados, con propensión incrementada en todo el portafolio.

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

---

## 6. Explicabilidad del Modelo (Feature Importance)

Para garantizar la transparencia del recomendador y facilitar la auditoría comercial en el ámbito financiero, el sistema extrae de forma nativa la **importancia de las variables (feature importances)** desde el clasificador Random Forest.

Esta importancia se calcula determinando la reducción media de la impureza de Gini provocada por cada variable a lo largo de todos los árboles del ensamble:

* **Top-5 Variables Influyentes (Fase 2):**
  1. `renta` (38.88%): Nivel de ingresos estimado del cliente.
  2. `categoria_producto_candidato_Cuenta` (21.83%): Si la oferta candidata es una cuenta.
  3. `edad` (14.30%): Rango de edad del cliente.
  4. `categoria_producto_candidato_Depósito` (4.98%): Si la oferta candidata es un depósito.
  5. `categoria_producto_candidato_Inversión` (3.17%): Si la oferta candidata es un fondo de inversión.
* **Consumo Dinámico:** El servidor MCP expone este listado a través de la herramienta `get_model_explainability()`, permitiendo que agentes de IA consulten estas métricas. Además, el dashboard de Grafana muestra este Top de forma gráfica en la sección de ML mediante la métrica `nbp_model_feature_importance`.

