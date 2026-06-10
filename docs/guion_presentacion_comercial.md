# Guión y Pitch Comercial: Recomendador Predictivo "Next Best Product" & Integración Inteligente MCP

Este documento sirve como recurso nemotécnico y guión paso a paso estructurado para exponer y "vender" el proyecto ante un jurado calificador, destacando tanto el rigor técnico de la ingeniería de datos como su impacto comercial de negocio.

---

## 💡 Resumen Ejecutivo (El Elevator Pitch)
* **Objetivo:** Transformar la oferta comercial del banco de reactiva (esperar a que el cliente pida algo) a proactiva (ofrecer el producto ideal antes de que lo pida), incrementando el *cross-selling* y reduciendo la deserción.
* **Resultado:** Un motor analítico basado en arquitectura Medallón (con DuckDB y Parquet) y aprendizaje supervisado que predice con un **77.8% de precisión (ROC-AUC)** la propensión de compra del cliente, integrado a agentes cognitivos de IA mediante el protocolo industrial **MCP (Model Context Protocol)**.

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
* **Logro Clave:** Imputación libre de sesgos y modelado temporal MoM para capturar tendencias de compra.

---

### 🎯 Diapositiva 5: Notebook 04 - Ingeniería de Características y Reglas de Negocio (Capa Gold)
* **Guión del Orador:**
  > *"La capa **Gold** es donde las reglas de negocio bancario y las matemáticas se cruzan. Construimos la **Matriz Analítica de Candidatos**. 
  > 
  > Sería un error y una pérdida de dinero recomendarle una tarjeta de crédito a un cliente que ya la tiene activa. Por eso, nuestro algoritmo realiza un cruce cartesiano de clientes contra todo el catálogo de productos y excluye proactivamente los productos vigentes. 
  > 
  > Posteriormente, generamos las variables agregadas (features) de tenencia financiera por categoría (ahorro, inversión, seguros, crédito) y simulamos de forma reproducible el target de conversión de compras históricas para entrenar el cerebro predictivo."*
* **Logro Clave:** Matriz de candidatos filtrada (cero ofertas redundantes) y preparación de variables de comportamiento de tenencia.

---

### 🧠 Diapositiva 6: Notebook 05 - Entrenamiento, Tuning y Validación Realista
* **Guión del Orador:**
  > *"Para predecir la propensión, seleccionamos un algoritmo ensemble de **Random Forest**, caracterizado por su robustez ante datos multivariados y su explicabilidad comercial.
  > 
  > Un error común en ML es la filtración de datos (*data leakage*). Para evitarlo, implementamos una validación cruzada agrupada por clientes (`GroupKFold`). Esto asegura que el modelo se valide con clientes completamente nuevos, garantizando que su rendimiento en producción sea idéntico al observado en la fase de pruebas.
  > 
  > Realizamos el tuning de hiperparámetros mediante `RandomizedSearchCV`, alcanzando un rendimiento sobresaliente: un **ROC-AUC en validación del 77.83%**. Evaluamos además métricas directas de conversión comercial: logramos un **Accuracy@1 del 18.5%** y un **Accuracy@3 del 23.5%**, lo que significa que casi 1 de cada 4 veces que ofrecemos un Top-3 de productos, el cliente aceptará uno de ellos."*
* **Logro Clave:** Validación cruzada limpia, tuning hiper-optimizado y métricas comerciales realistas (ROC-AUC 77.8%, Accuracy@3 23.5%).

---

### 📈 Diapositiva 7: Notebook 06 - Inferencia y Recomendación Top-1 para Canales Comerciales
* **Guión del Orador:**
  > *"Finalmente, el modelo entrenado se ejecuta sobre los clientes activos de prueba para generar las predicciones comerciales. 
  > 
  > El sistema calcula la probabilidad de compra para cada cliente potencial y cada producto disponible, y filtra el listado extrayendo la recomendación óptima **Top-1** con su respectivo scoring. Como pueden observar en pantalla, el sistema ha generado exitosamente recomendaciones comerciales priorizadas y personalizadas para **1,000 clientes activos únicos**, listas para ser desplegadas inmediatamente a través de la banca móvil, la web, o el call center."*
* **Logro Clave:** Entrega de un listado de scoring comercial procesado para 1,000 clientes únicos en la capa Gold.

---

### 🌐 Diapositiva 8: Innovación Tecnológica - Servidor MCP (Integración Inteligente con Agentes de IA)
* **Guión del Orador:**
  > *"Para finalizar, queremos presentar la mayor innovación arquitectónica de este proyecto. Un modelo predictivo encerrado en un notebook no genera valor. Para democratizar sus resultados, construimos un servidor **MCP (Model Context Protocol)**.
  > 
  > MCP es el estándar global desarrollado para conectar sistemas de datos con grandes modelos de lenguaje (LLMs). Nuestro servidor expone herramientas seguras como `get_client_profile` (perfil del cliente) y `get_client_recommendation` (siguiente mejor producto y su probabilidad).
  > 
  > Esto permite que cualquier asistente cognitivo de IA (como Gemini o Claude) converse directamente con nuestro modelo analítico en tiempo real. Un gerente o ejecutivo comercial puede simplemente preguntarle a la IA en lenguaje natural: *'¿Por qué deberíamos ofrecerle una hipoteca a Juan Pérez hoy?'* y la IA responderá con los datos de nuestro modelo. Estamos uniendo la potencia analítica predictiva clásica con la flexibilidad y el lenguaje natural de la IA generativa."*
* **Logro Clave:** Servidor MCP que expone perfiles y propensiones predictivas para habilitar agentes cognitivos de IA en lenguaje natural.

---

### 🚀 Diapositiva 9: Conclusiones y Retorno de Inversión (ROI)
* **Guión del Orador:**
  > *"En resumen, esta solución ofrece al banco:
  > 1. **Reducción de costos de computación** mediante almacenamiento Parquet y procesamiento DuckDB ultra-eficiente.
  > 2. **Incremento medible de las ventas** enfocando la fuerza comercial en ofertas con alta probabilidad de éxito (Accuracy@3 del 23.5%).
  > 3. **Flexibilidad en la nube:** Un diseño agnóstico que corre tanto localmente (en Anaconda) como en Google Colab.
  > 4. **Modernización de canales** listos para agentes autónomos de IA a través de MCP.
  > 
  > Esta es la banca del futuro: ágil, predictiva y centrada en el cliente. Quedo a su disposición para cualquier pregunta técnica o de negocio. Muchas gracias."*
* **Idea Fuerza:** Eficiencia, rentabilidad y preparación tecnológica del proyecto.
