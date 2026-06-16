# Guión y Pitch Comercial: Recomendador Predictivo "Next Best Product" & Integración Inteligente MCP

Este documento sirve como recurso nemotécnico y guión paso a paso estructurado para exponer y "vender" el proyecto ante un jurado calificador, destacando tanto el rigor técnico de la ingeniería de datos como su impacto comercial de negocio.

---

## 💡 Resumen Ejecutivo (El Elevator Pitch)
* **Objetivo:** Transformar la oferta comercial del banco de reactiva (esperar a que el cliente pida algo) a proactiva (ofrecer el producto ideal antes de que lo pida), incrementando el *cross-selling* y reduciendo la deserción.
* **Resultado:** Un motor analítico basado en arquitectura Medallón (con DuckDB y Parquet) y aprendizaje supervisado que predice con un **77.8% de precisión (ROC-AUC)** la propensión de compra del cliente, integrado a agentes cognitivos de IA mediante el protocolo industrial **MCP (Model Context Protocol)** y monitoreado bajo un stack de observabilidad de nivel empresarial (**Grafana + Loki + Mimir + Tempo**).

---

## 🎙️ Guión de Exposición Paso a Paso (Notebook a Notebook)

### 📊 Diapositiva 1: La Oportunidad de Negocio y el Problema
* **Guión del Orador:**
  > *"Muy buenas tardes. Hoy en día, las instituciones financieras gastan millones de dólares en campañas de marketing genéricas que aburren al cliente y dañan la conversión. El paradigma moderno exige hiper-personalización: ofrecer el producto financiero idóneo en el momento exacto.
  >
  > Presentamos nuestro recomendador **Next Best Product** (Siguiente Mejor Producto). Una solución integral de extremo a extremo que procesa millones de transacciones históricas, limpia e imputa de forma inteligente los datos de clientes, entrena un modelo predictivo robusto y expone los resultados a asistentes de Inteligencia Artificial en lenguaje natural. Veamos cómo lo logramos etapa por etapa."*
* **Idea Fuerza:** Hiper-personalización bancaria en tiempo real para optimizar ventas.

---

### 📥 Diapositiva 2: Notebook 01 - Ingesta de Datos (Capa Raw)
* **Guión del Orador:**
  > *"Todo proyecto exitoso de Machine Learning depende de la calidad de sus cimientos. En el primer notebook, **Ingesta Raw**, implementamos un módulo automático de validación e integridad de datos. 
  > 
  > Antes de procesar un solo registro, el sistema verifica que las 8 fuentes maestras (datos demográficos de clientes, saldos mensuales, transacciones de productos, catálogos y ubicaciones geográficas) estén completas y cumplan con los esquemas requeridos. Esto garantiza que nuestro pipeline sea inmune a fallas silenciosas en producción."*
* **Logro Clave:** Validación del 100% de consistencia previa a la transformación.

---

### ⚡ Diapositiva 3: Notebook 02 - Conversión Columnar Eficiente (Capa Bronze)
* **Guión del Orador:**
  > *"En la capa **Bronze**, atacamos un problema típico de Big Data: la velocidad de lectura. Los archivos CSV planos son lentos e ineficientes. 
  >
  > En esta etapa, el sistema realiza una conversión automática 1:1 de todos los CSVs brutos a formato binario columnar **Parquet** utilizando **DuckDB**. DuckDB nos permite ejecutar operaciones analíticas vectorizadas directamente en memoria a velocidades de milisegundos, reduciendo el tamaño físico de los datos y acelerando el tiempo de lectura secuencial del modelo en más de un 100x."*
* **Logro Clave:** Adopción del estándar industrial Parquet + procesamiento en memoria ultrarrápido con DuckDB.

---

### 🧼 Diapositiva 4: Notebook 03 - Calidad, Estandarización y Tendencias (Capa Silver)
* **Guión del Orador:**
  > *"En la capa **Silver**, aplicamos el corazón del gobierno de datos. Los datos del mundo real vienen sucios. 
  > 
  > Primero, implementamos una imputación demográfica inteligente: los valores faltantes en campos críticos como edad e ingresos (renta) se calculan a través de la mediana del grupo para evitar sesgos artificiales en el modelo. 
  > 
  > Segundo, calculamos el indicador **Month-over-Month (MoM)**. Esto no solo nos dice qué productos tiene un cliente hoy, sino qué productos dio de alta netamente este mes en comparación con el anterior. Esta tendencia temporal añade un valor predictivo inmenso al modelo."*
* **Logro Clave:** Imputación libre de sesgos y alistamiento de datos limpios.

---

### 🎯 Diapositiva 5: Notebook 04 - Ingeniería de Características Avanzada (Capa Gold)
* **Guión del Orador:**
  > *"La capa **Gold** es donde las reglas de negocio bancario y las matemáticas se cruzan. Construimos la **Matriz Analítica de Candidatos**. 
  > 
  > Sería un error y una pérdida de dinero recomendarle una tarjeta de crédito a un cliente que ya la tiene activa. Por eso, nuestro algoritmo realiza un cruce cartesiano de clientes contra todo el catálogo de productos y excluye proactivamente los productos vigentes. 
  > 
  > En esta nueva versión, incorporamos dos variables de alta significancia comercial: el **ratio de tenencia de ahorro** y el **ratio de tenencia de crédito**. Estas variables le dicen al modelo qué tan diversificado está el cliente respecto a su cartera potencial, permitiendo recomendaciones mucho más sofisticadas."*
* **Logro Clave:** Matriz de candidatos filtrada y cálculo de ratios de diversificación de portafolio.

---

### 🧠 Diapositiva 6: Notebook 05 - Modelado Predictivo y Explicabilidad (Machine Learning)
* **Guión del Orador:**
  > *"Para entrenar el recomendador, seleccionamos un clasificador de **Random Forest**. Para evitar la filtración de datos (*data leakage*), implementamos una validación cruzada agrupada por clientes (`GroupKFold`). 
  > 
  > El modelo alcanza un **ROC-AUC del 77.83%** en validación y una métrica comercial **Accuracy@3 del 23.5%**. 
  > 
  > Pero la novedad de esta entrega es la **Explicabilidad del Modelo**. Extraemos de forma nativa la importancia de las variables (Feature Importance), identificando cuáles son los 5 factores que más influyen en la decisión (como la tenencia previa de cuentas y la renta estimada). Esto nos da total transparencia ante auditorías."*
* **Logro Clave:** Métricas validadas con exclusión de data leakage y extracción nativa de feature importances para transparencia.

---

### 📈 Diapositiva 7: Notebook 06 - Inferencia y Scoring Comercial
* **Guión del Orador:**
  > *"En el último notebook del flujo, corremos la inferencia predictiva y el scoring sobre los clientes activos de prueba. 
  > 
  > El recomendador calcula la propensión para cada combinación disponible y filtra el listado extrayendo la recomendación **Top-1** definitiva. En esta ejecución, el sistema ha generado exitosamente recomendaciones comerciales personalizadas para **1,000 clientes activos únicos**, listas para ser inyectadas a campañas de telemarketing o alertas en la banca móvil."*
* **Logro Clave:** Generación automatizada de 1,000 recomendaciones comerciales prioritarias.

---

### 🌐 Diapositiva 8: Servidor MCP - Integración Cognitiva con Agentes de IA
* **Guión del Orador:**
  > *"Como gran salto tecnológico, desarrollamos un servidor **MCP (Model Context Protocol)**. MCP permite conectar directamente nuestro modelo analítico a asistentes de Inteligencia Artificial (como Gemini o Claude) en lenguaje natural.
  > 
  > El servidor expone las herramientas `get_client_profile`, `get_client_recommendation` y la nueva `get_model_explainability`. 
  > 
  > Además, creamos un **MCP Prompt Template** llamado `preparar_briefing_comercial`. Con esto, un ejecutivo comercial del banco puede interactuar con el asistente y este generará automáticamente un guion de venta o correo persuasivo personalizado basado en las predicciones exactas del modelo."*
* **Logro Clave:** Integración nativa de IA conversacional con nuestro recomendador clásico mediante MCP y Prompt Templates.

---

### 🖥️ Diapositiva 9: Observabilidad y Monitoreo de Producción (Grafana Stack)
* **Guión del Orador:**
  > *"Finalmente, pensamos en la puesta en producción. Un modelo bancario requiere monitoreo continuo. 
  > 
  > Implementamos un stack de observabilidad completo basado en **Grafana, Loki, Mimir y Tempo**. A través de un colector **Grafana Alloy**, raspamos en vivo el servidor de métricas del MCP en el puerto `8000` y recolectamos de forma automatizada los logs locales de la aplicación.
  > 
  > El dashboard pre-aprovisionado de Grafana muestra en tiempo real la salud del pipeline Medallón, los tiempos de ejecución, las métricas del modelo (AUC, Accuracy), la tasa de uso de herramientas MCP por parte de la IA, y los logs integrados en Loki para debugging rápido."*
* **Logro Clave:** Telemetría en tiempo real y logs unificados para soporte de IT y Negocios.

---

### 🚀 Diapositiva 10: Conclusiones y Retorno de Inversión (ROI)
* **Guión del Orador:**
  > *"En conclusión, esta solución integral 'Next Best Product' ofrece:
  > 1. **Reducción de costos de computación** mediante almacenamiento Parquet y procesamiento DuckDB ultra-eficiente.
  > 2. **Retorno comercial medible** incrementando el cross-selling enfocado (Accuracy@3 del 23.5%).
  > 3. **Observabilidad total** lista para producción.
  > 4. **Modernización de canales** con agentes autónomos de IA vía MCP.
  > 
  > Quedo a su disposición para cualquier pregunta técnica o de negocio. Muchas gracias."*
* **Idea Fuerza:** Rentabilidad, innovación, robustez y preparación productiva del proyecto.
