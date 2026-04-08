"""
═══════════════════════════════════════════════════════════════════════════════
SIMULADOR DE LITOGRAFÍA ÓPTICA - SISTEMA DE SLICE Y PROYECCIÓN
═══════════════════════════════════════════════════════════════════════════════

SISTEMA DE SEGMENTACIÓN Y CORTES (SLICE):
-----------------------------------------
✓ UN ÚNICO CORTE ACTIVO: Solo existe un corte automático en todo momento
✓ CÁLCULO AUTOMÁTICO: El corte se calcula usando las coordenadas extremas del contenido
✓ CACHE DETERMINISTA: El mismo corte se reutiliza si no cambian:
    • La imagen (mismo objeto)
    • La posición de la imagen en el grid
    • La configuración del grid (segments_x, segments_y)
✓ NO SE PERMITEN CORTES SOBRE CORTES: El único corte válido identifica exactamente
  los chunks donde la imagen está presente
✓ ORDEN SECUENCIAL ESTRICTO: Los chunks se procesan uno a uno, en orden

VISUALIZACIÓN Y RENDERIZADO:
----------------------------
✓ CHUNKS SECUENCIALES: Los chunks se muestran uno a la vez, estrictamente en orden
✓ ESCALADO MÁXIMO: Cada chunk se renderiza al máximo tamaño posible que permita
  la pantalla (object-fit: contain)
✓ RESOLUCIÓN FIJA: Los píxeles de la pantalla son fijos, la adaptación ocurre
  dentro del chunk
✓ INVERSIÓN DISPONIBLE: Opción para invertir la imagen en el preview y proyección

CONSISTENCIA Y DETERMINISMO:
---------------------------
✓ CACHE INTELIGENTE: No se recalcula el corte si los datos no cambian
✓ LOGGING DETALLADO: Se registra cuando se usa cache vs. recálculo
✓ LIMPIEZA MANUAL: Opción en menú de preferencias para limpiar cache si es necesario

Fecha última actualización: 2025-11-25
═══════════════════════════════════════════════════════════════════════════════
"""
import sys
from PyQt5.QtWidgets import QApplication
from system_functions import LithographySimulator

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LithographySimulator()
    window.show()
    sys.exit(app.exec_())
