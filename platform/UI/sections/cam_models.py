"""
modelos de datos para el layout editor cam.

contiene las estructuras inmutables que representan los elementos
del canvas, las instrucciones de proyeccion y el estado de la maquina.
"""
import uuid
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LayoutItem:
    """representa un elemento arrastrable en el canvas del layout editor."""
    uid: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    item_type: str = "rect"         # "image" | "rect" | "line" | "circle"
    name: str = ""
    x_mm: float = 0.0              # esquina superior izquierda, eje x (mm)
    y_mm: float = 0.0              # esquina superior izquierda, eje y (mm)
    w_mm: float = 10.0             # ancho fisico (mm)
    h_mm: float = 10.0             # alto fisico (mm)
    w_px: int = 0                  # ancho en pixeles de la imagen fuente
    h_px: int = 0                  # alto en pixeles de la imagen fuente
    inverted: bool = False         # si la imagen tiene los colores invertidos
    rotation_deg: float = 0.0      # rotacion en grados (0-360)
    data: Optional[np.ndarray] = field(default=None, repr=False)
    exposure_s: float = 10.0       # tiempo de exposicion (segundos)
    delay_s: float = 5.0           # tiempo de estabilizacion previo (segundos)
    filepath: str = ""             # ruta al archivo original (solo imagenes)

    # posicion previa para revertir si hay colision
    _prev_x: float = field(default=0.0, repr=False)
    _prev_y: float = field(default=0.0, repr=False)

    def save_position(self):
        """guarda la posicion actual antes de un arrastre."""
        self._prev_x = self.x_mm
        self._prev_y = self.y_mm

    def revert_position(self):
        """restaura la posicion previa (collision rollback)."""
        self.x_mm = self._prev_x
        self.y_mm = self._prev_y

    def bounding_box(self):
        """retorna (x_min, y_min, x_max, y_max) en mm."""
        return (self.x_mm, self.y_mm, self.x_mm + self.w_mm, self.y_mm + self.h_mm)

    def contains_point(self, px_mm: float, py_mm: float) -> bool:
        """verifica si un punto (mm) esta dentro del bounding box."""
        x0, y0, x1, y1 = self.bounding_box()
        return x0 <= px_mm <= x1 and y0 <= py_mm <= y1

    def exceeds_bounds(self, bed_x_max: float, bed_y_max: float) -> bool:
        """verifica si el item se sale de los limites fisicos del bed."""
        _, _, x1, y1 = self.bounding_box()
        return (self.x_mm < 0 or self.y_mm < 0 or
                x1 > bed_x_max or y1 > bed_y_max)


@dataclass
class ProjectionTask:
    """instruccion atomica para el orquestador asincrono."""
    target_x_mm: float = 0.0       # coordenada absoluta destino x (mm)
    target_y_mm: float = 0.0       # coordenada absoluta destino y (mm)
    image_data: Optional[np.ndarray] = field(default=None, repr=False)
    exposure_s: float = 10.0       # duracion de la exposicion (s)
    delay_s: float = 5.0           # espera de estabilizacion previa (s)
    source_item_uid: str = ""      # uid del LayoutItem padre
    tile_row: int = 0              # fila del tile dentro del item
    tile_col: int = 0              # columna del tile dentro del item
    tile_total: int = 1            # total de tiles de este item

    def __repr__(self):
        shape = self.image_data.shape if self.image_data is not None else "None"
        return (f"ProjectionTask(x={self.target_x_mm:.2f}, y={self.target_y_mm:.2f}, "
                f"img={shape}, exp={self.exposure_s}s, tile={self.tile_row}x{self.tile_col})")


@dataclass
class MachineState:
    """instantanea del estado actual de la maquina."""
    bed_x_mm: float = 0.0          # posicion actual x (mm)
    bed_y_mm: float = 0.0          # posicion actual y (mm)
    bed_x_max_mm: float = 40.0     # limite maximo x (mm)
    bed_y_max_mm: float = 40.0     # limite maximo y (mm)
    fov_w_mm: float = 14.1         # ancho del fov del proyector (mm)
    fov_h_mm: float = 7.9          # alto del fov del proyector (mm)
    fov_w_px: int = 1920           # ancho fov en pixeles
    fov_h_px: int = 1080           # alto fov en pixeles
    mm_per_pixel: float = 0.00735  # calibracion optica
    steps_per_mm: int = 80         # resolucion del motor
    is_connected: bool = False     # si el controlador esta conectado
    is_calibrated: bool = False    # si la calibracion optica fue realizada

    @classmethod
    def from_app(cls, main_app, controller):
        """construye el estado leyendo los datos reales de la aplicacion."""
        state = cls()

        # calibracion optica
        mm_per_px = getattr(main_app, "mm_per_pixel", None) if main_app else None
        if mm_per_px and mm_per_px > 0:
            state.mm_per_pixel = mm_per_px
            state.is_calibrated = True
            state.fov_w_mm = 1920 * mm_per_px
            state.fov_h_mm = 1080 * mm_per_px

        # intentar leer resolution real (steps_per_mm) del controlador
        if controller and hasattr(controller, "step_size") and controller.step_size > 0:
            state.steps_per_mm = int(round(1.0 / controller.step_size))

        # limites de motores
        if controller and hasattr(controller, "limits"):
            lx = controller.limits.get("X")
            ly = controller.limits.get("Y")
            spm = state.steps_per_mm
            if lx is not None and lx > 0:
                state.bed_x_max_mm = lx / spm
            if ly is not None and ly > 0:
                state.bed_y_max_mm = ly / spm

        # posicion actual
        if controller and hasattr(controller, "positions"):
            spm = state.steps_per_mm
            state.bed_x_mm = controller.positions.get("X", 0) / spm
            state.bed_y_mm = controller.positions.get("Y", 0) / spm

        # conexion
        if controller and hasattr(controller, "ser"):
            state.is_connected = controller.ser is not None

        return state
