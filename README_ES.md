

# Sistema de Fotolitografía para Micro y Nanofabricación (Máscara Digital)

Sistema abierto de fotolitografía sin máscara física (*Maskless Photolithography*) para la transferencia de patrones micrométricos sobre sustratos de cobre recubiertos con película fotosensible seca (*dry film*).

---

## Índice

1. [Requisitos e Instalación](#requisitos-e-instalación)
2. [Configuración Previa del Entorno Físico](#configuración-previa-del-entorno-físico)
3. [Guía de Uso y Manual de Operación](#guía-de-uso-y-manual-de-operación)
   - [Paso 1: Conexión y Enlace con el Hardware](#paso-1-conexión-y-enlace-con-el-hardware)
   - [Paso 2: Carga e Ingesta del Patrón Litográfico](#paso-2-carga-e-ingesta-del-patrón-litográfico)
   - [Paso 3: Acondicionamiento Digital y Binarización](#paso-3-acondicionamiento-digital-y-binarización)
   - [Paso 4: Calibración Espacial ($\mu\text{m/px}$)](#paso-4-calibración-espacial-mutextmpx)
   - [Paso 5: Segmentación y Configuración Step-and-Repeat](#paso-5-segmentación-y-configuración-step-and-repeat)
   - [Paso 6: Ajuste de Dosis y Exposición UV](#paso-6-ajuste-de-dosis-y-exposición-uv)
   - [Paso 7: Módulos Autónomos de Calibración](#paso-7-módulos-autónomos-de-calibración)
4. [Protocolo Químico Rápido (Dry Film)](#protocolo-químico-rápido-dry-film)
5. [Estructura del Repositorio](#estructura-del-repositorio)

---

## Requisitos e Instalación

### Requisitos del Sistema
- **Sistema Operativo:** Windows 10/11 (recomendado) o distribuciones Linux compatibles.
- **Python 3** instalado.
  
### Instalación de Dependencias

1. Clonar el repositorio:
   ```bash
   git clone https://github.com/sasepulveda2/photolith.git
   cd photolith
   ```

2. Crear y activar un entorno virtual:
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux:
   source venv/bin/activate
   ```

3. Instalar dependencias:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

   *Dependencias esenciales:* `PyQt5`, `opencv-python`, `numpy`, `matplotlib`, `pyserial`, `PyMuPDF` (módulo `fitz` para SVG), `ezdxf`.

---

## Configuración Previa del Entorno Físico

1. **Configuración de Pantalla (SO):** Fijar el proyector en modo **Extender estas pantallas**.
2. **Iluminación de Seguridad:** No exponer placas laminadas a luz blanca o solar directa.
3. **Alineación de Sustrato:** Montar la placa de cobre laminada sobre la platina de desplazamiento, nivelando el plano focal con respecto al lente del proyector.

---

## Guía de Uso y Manual de Operación

### Paso 1: Conexión y Enlace con el Hardware

1. Ejecutar la aplicación principal:
   ```bash
   python main.py
   ```
2. Desplegar el panel lateral **MOTORES (X, Y, Z)**.
3. Presionar el botón **CONECTAR HARDWARE**.
   - El software detectará el puerto COM correspondiente y enviará la secuencia de inicialización G-code: deshabilitación de finales de carrera físicos (`M211 S0`), supresión de protecciones térmicas (`M302 S0`) y fijación de coordenadas relativas (`G91`).
   - La consola inferior confirmará el enlace con nivel `[INFO]`.
4. Mediante el pad direccional ($X+$, $X-$, $Y+$, $Y-$, $Z+$, $Z-$), desplazar manualmente la platina hasta la posición de origen del sustrato. Se puede alternar entre pasos enteros (*Steps*) o milímetros (*mm*).
5. Fijar el origen virtual de trabajo para inicializar la odometría interna.

### Paso 2: Carga e Ingesta del Patrón Litográfico

1. Hacer clic en **Cargar patrón** en la barra superior (o arrastrar el archivo directamente sobre el lienzo central).
2. Formatos aceptados:
   - **Raster:** Archivos `.png`, `.jpg`, `.bmp`, `.tiff`. Se cargarán normalizados en escala de grises.
   - **Vectorial SVG:** Se rasterizan internamente a una resolución mínima de $4.000\text{ px}$ en su eje mayor.
   - **Vectorial DXF:** Se renderizan monocromáticamente a una densidad mínima de $400\text{ DPI}$.

### Paso 3: Acondicionamiento Digital y Binarización

1. Abrir el panel lateral **BINARIO**:
   - **Activar modo binario (0/1):** Marca de verificación obligatoria para convertir la imagen en una matriz de corte estricto ($0$ y $255$).
   - **Umbral (Threshold):** Ajustar mediante el deslizador o campo numérico (valor empírico recomendado: $50\% - 65\%$, dependiendo de la densidad de pistas finas).
   - **Invertir Color (Negativo):** Activar si se utiliza película fotorresistente negativa (*Dry Film* azul estándar). Las zonas expuestas polimerizan y resisten el ataque químico posterior; las zonas oscuras se disuelven en el revelador.
   - **Bloquear Umbral:** Activar para evitar alteraciones accidentales durante la manipulación de la interfaz.
2. Modificar el **Brillo de proyección** en la barra superior al $100\%$ para la exposición litográfica.

### Paso 4: Calibración Espacial ($\mu\text{m/px}$)

Para que el software traslade con precisión los desplazamientos del proyector a la base física:
1. Ir a la vista superior **Calibración de patrón**.
2. Cargar una imagen o patrón de dimensión conocida (por ejemplo, una regla de microscopio o un filamento patrón de $100\ \mu\text{m}$).
3. Trazar una línea recta sobre el lienzo haciendo clic entre los dos extremos de la referencia.
4. El sistema calculará la longitud en píxeles ($L_{px}$).
5. En el campo **Medida real**, ingresar el valor físico en milímetros o micrones.
6. Presionar **Guardar calibración**. El software derivará la resolución espacial del sistema:
   $$\text{Factor de Escala} = \frac{\text{Distancia Real (mm)}}{L_{px}}\quad [\text{mm/px}]$$
   $$\text{Resolución} = \text{Factor de Escala} \times 1000\quad [\mu\text{m/px}]$$
   Este factor quedará almacenado en el archivo de preferencias `config.json` para las sesiones siguientes.

### Paso 5: Segmentación y Configuración Step-and-Repeat

Si el patrón supera las dimensiones del campo óptico de enfoque único:
1. Acceder a la vista **Vista grid**.
2. Configurar el tamaño de la cuadrícula:
   - **Modo Grilla (Grid):** Definir el ancho y alto del *chunk* en píxeles. La herramienta aplicará un ajuste magnético (*snap*) para alinear las celdas a las esquinas del diseño.
   - **Modo Automático:** Subdivide automáticamente la imagen tomando celdas estándar según la resolución del proyector.

### Paso 6: Ajuste de Dosis y Exposición UV

1. Desplegar el panel lateral **EXPOSICIÓN**:
   - **Tiempo de exposición:** Fijar el tiempo según la caracterización del sustrato.
     - **Rango óptimo calibrado:** $7\text{ s}$ a $15\text{ s}$.
     - **Wide traces (> 200 µm):** $7–10\text{ s}.
     - **Fine features (30–60 µm):** $15\text{ s}.
     - *Advertencia:* Tiempos cercanos a $20\text{ s}$ o superiores generan sobrepolimerización lateral y engrosamiento indeseado de pistas.
   - **Modo de disparo:** Continuo o Pulsado (frecuencia entre $1$ y $100\text{ Hz}$).
2. Presionar **Proyecciones > Iniciar Secuencia**.
3. El ciclo *Step-and-Repeat* operará de forma autónoma bajo la máquina de estados:
   ```
   [Mover Motor] ──> [Pausa Estabilización (1.5 s)] ──> [Proyectar Chunk] ──> [Exposición UV] ──> [Pantalla Negra] ──> (Siguiente Chunk)
   ```
4. En caso de desalineación o riesgo de los motores, presionar inmediatamente el botón rojo **STOP** para abortar la tarea.

---

### Paso 7: Módulos Autónomos de Calibración

#### Generador de Matrices de Exposición
Permite encontrar la dosis óptima sobre una sola placa virgen:
1. Acceder al menú de utilidades y seleccionar **Matriz de Barrido**.
2. Configurar el tipo de figura (rejilla de líneas paralelas con grosores decrecientes).
3. Iniciar el ensayo: el sistema proyectará las franjas de forma incremental acumulativa mediante temporizadores Qt. Cada franja recibirá una dosis distinta (escalones de $2$ a $20\text{ s}$), permitiendo evaluar bajo microscopio el punto óptimo de polimerización tras el revelado.

#### Módulo de Regla Micrométrica (*RulerScaleMixin*)

Permite fabricar patrones graduados de medición física sobre vidrio o cobre:
1. Abrir la vista **Regla de escala**.
2. Indicar la separación entre marcas principales en píxeles (calculadas a partir del factor de escala del sistema), el número de subdivisiones, grosor de líneas y largo total a recorrer.
3. Presionar **Iniciar secuencia de escala**: la base avanzará secuencialmente en el eje X compensando el *backlash* residual y exponiendo tramo por tramo.

---

## Protocolo Químico Rápido (Dry Film)

Para asegurar la correcta adherencia y definición de los patrones fabricados:

1. **Acondicionamiento Mecánico:** Lijar la placa de cobre virgen con lija al agua grano 1250 con movimientos suaves hasta remover toda la capa superficial de óxido ($CuO / Cu_2O$).
2. **Descontaminación Química:**
   - Limpiar con **Acetona ($C_3H_6O$)** para remover grasas y compuestos orgánicos.
   - Limpiar inmediatamente con **Alcohol Isopropílico ($C_3H_8O$)** para remover residuos de acetona. *No alterar este orden*.
3. **Laminado Térmico:**
   - Precalentar la placa a $110\ ^\circ\text{C}$ (se recomienda utilizar la cama caliente de una impresora 3D).
   - Retirar la lámina protectora interna de polietileno del *dry film* con cinta adhesiva.
   - Aplicar el film sobre la placa caliente e introducir de inmediato en una laminadora de rodillos para expulsar microburbujas de aire.
4. **Exposición:** Proyectar la máscara digital en la plataforma durante $7 - 15\text{ s}$.
5. **Revelado Alcalino:**
   - Retirar la película protectora frontal transparente de poliéster.
   - Sumergir la placa en una solución de **Carbonato de Sodio ($Na_2CO_3$) al $1\%\text{ p/v}$** en agua destilada durante **2 minutos**, agitando suavemente.
6. **Detención y Neutralización:**
   - Retirar la placa con pinzas y sumergirla inmediatamente en un baño de agua destilada limpia durante 2 minutos para detener la acción del revelador.
   - Limpiar suavemente los canales no polimerizados con un pincel de cerdas ultrasuaves bajo el chorro de agua.

---

## Estructura del Repositorio

```text
photolith/
├── main.py                  # Punto de entrada de la aplicación
├── requirements.txt         # Dependencias del entorno Python
├── config.json              # Persistencia de calibración, soft limits y backlash
├── controllers/
│   ├── creality_controller.py # Capa de abstracción G-code, odometría y PySerial
│   └── worker.py             # Hilo de ejecución asíncrono (CamWorker sobre QThread)
├── mixins/
│   ├── ui_setup_mixin.py     # Ensamblaje modular de paneles y widgets
│   ├── image_processing_mixin.py # Binarización, inversión y transformaciones
│   ├── grid_mixin.py         # Algoritmo de división en chunks y solapamiento
│   ├── spatial_calibration_mixin.py # Cálculo de escala micrométrica
│   ├── ruler_scale_mixin.py  # Rutina Step-and-Repeat para reglas graduadas
│   ├── projection_mixin.py   # Control de ciclo de vida del proyector secundario
│   ├── file_management_mixin.py # Ingesta y rasterización de SVG/DXF/raster
│   └── preferences_mixin.py  # Serialización y carga de parámetros JSON
├── docs/
│   └── images/               # Capturas y diagramas técnicos del sistema
└── tests/                   # Pruebas unitarias de cinemática y segmentación
```
