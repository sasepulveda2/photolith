"""
orquestador asincrono para la cola de proyeccion.

ejecuta la secuencia de movimiento-estabilizacion-exposicion
en un qthread independiente, comunicandose con el hilo principal
exclusivamente mediante señales de qt para evitar bloqueos.
"""
import time
import numpy as np
from math import hypot, ceil

from PyQt5.QtCore import QThread, pyqtSignal


class CamWorker(QThread):
    """state machine que procesa la cola de ProjectionTask en segundo plano."""

    # señales hacia el hilo principal (ui)
    sig_move_started = pyqtSignal(int, float, float)    # (task_idx, x_mm, y_mm)
    sig_stabilizing = pyqtSignal(int, float)             # (task_idx, delay_s)
    sig_exposing = pyqtSignal(int, float)                # (task_idx, exposure_s)
    sig_project_image = pyqtSignal(object)               # numpy array -> proyectar en pantalla
    sig_black_screen = pyqtSignal()                      # apagar proyeccion
    sig_task_done = pyqtSignal(int, int)                 # (task_idx, total_tasks)
    sig_all_done = pyqtSignal(int, float)                # (total_tasks, elapsed_s)
    sig_error = pyqtSignal(str)                          # mensaje de error
    sig_log = pyqtSignal(str, str)                       # (message, level)

    def __init__(self, task_queue, controller=None, steps_per_mm=80, parent=None):
        super().__init__(parent)
        self.task_queue = list(task_queue)
        self.controller = controller
        self.steps_per_mm = steps_per_mm
        self.current_x = 0.0
        self.current_y = 0.0
        self._abort = False
        self._paused = False

        # leer posicion actual del controlador si existe
        if controller and hasattr(controller, "positions"):
            self.current_x = controller.positions.get("X", 0) / steps_per_mm
            self.current_y = controller.positions.get("Y", 0) / steps_per_mm

    def abort(self):
        """solicita la detencion del bucle principal."""
        self._abort = True

    def pause(self):
        """alterna el estado de pausa."""
        self._paused = not self._paused

    def run(self):
        """bucle principal de la state machine."""
        total = len(self.task_queue)
        if total == 0:
            self.sig_all_done.emit(0, 0.0)
            return

        start_time = time.time()
        self.sig_log.emit(
            f"iniciando ejecucion de {total} tareas de proyeccion", "info"
        )

        for i, task in enumerate(self.task_queue):
            if self._abort:
                self.sig_log.emit(
                    f"ejecucion abortada en tarea {i+1}/{total}", "warning"
                )
                break

            # esperar si esta en pausa
            while self._paused and not self._abort:
                time.sleep(0.1)

            if self._abort:
                break

            # --- paso a) mover motores ---
            delta_x_mm = task.target_x_mm - self.current_x
            delta_y_mm = task.target_y_mm - self.current_y

            self.sig_move_started.emit(i, task.target_x_mm, task.target_y_mm)

            if abs(delta_x_mm) > 0.001 or abs(delta_y_mm) > 0.001:
                try:
                    self._move_motors(delta_x_mm, delta_y_mm)
                except Exception as e:
                    self.sig_error.emit(f"error moviendo motores: {str(e)}")
                    break

            # --- paso b) estabilizacion ---
            if task.delay_s > 0:
                self.sig_stabilizing.emit(i, task.delay_s)
                self._safe_sleep(task.delay_s)

            if self._abort:
                break

            # --- paso c) encender proyector ---
            if task.image_data is not None:
                self.sig_project_image.emit(task.image_data)
                self.sig_exposing.emit(i, task.exposure_s)

                # --- paso d) esperar exposicion ---
                self._safe_sleep(task.exposure_s)

                # --- paso e) apagar proyector ---
                self.sig_black_screen.emit()

            # --- paso f) actualizar posicion ---
            self.current_x = task.target_x_mm
            self.current_y = task.target_y_mm
            self.sig_task_done.emit(i, total)

        elapsed = time.time() - start_time
        if not self._abort:
            self.sig_all_done.emit(total, elapsed)
        else:
            self.sig_black_screen.emit()

    def _move_motors(self, dx_mm: float, dy_mm: float):
        """envia comandos de movimiento al controlador de motores."""
        if self.controller is None:
            # modo simulacion: solo esperar un tiempo proporcional a la distancia
            travel_mm = hypot(dx_mm, dy_mm)
            simulated_time = travel_mm * 0.05  # 50ms por mm simulado
            self.sig_log.emit(
                f"simulacion: moviendo ({dx_mm:+.2f}, {dy_mm:+.2f}) mm, "
                f"distancia: {travel_mm:.2f} mm",
                "info"
            )
            self._safe_sleep(simulated_time)
            return

        # convertir mm a steps
        steps_x = int(round(dx_mm * self.steps_per_mm))
        steps_y = int(round(dy_mm * self.steps_per_mm))

        if steps_x != 0:
            self.controller.step_move("X", steps_x, multiplier=1, feedrate=150)
        if steps_y != 0:
            self.controller.step_move("Y", steps_y, multiplier=1, feedrate=150)

        # esperar a que el motor complete el movimiento
        # estimacion: 150 mm/min feedrate -> 2.5 mm/s
        travel_mm = hypot(dx_mm, dy_mm)
        estimated_travel_s = travel_mm / 2.5
        self._safe_sleep(max(0.1, estimated_travel_s))

    def _safe_sleep(self, seconds: float):
        """duerme en intervalos cortos para poder responder a abort/pause."""
        elapsed = 0.0
        interval = 0.05  # 50ms
        while elapsed < seconds:
            if self._abort:
                return
            while self._paused and not self._abort:
                time.sleep(0.1)
            time.sleep(min(interval, seconds - elapsed))
            elapsed += interval


# --- funciones de utilidad para el path planning ---

def compute_tiling(item, fov_w_mm: float, fov_h_mm: float,
                   mm_per_pixel: float, overlap_mm: float = 0.0):
    """
    subdivide un LayoutItem en una lista de ProjectionTask.

    si el item cabe dentro del fov, genera un unico task.
    si excede el fov, lo corta en tiles con el overlap especificado.

    la matematica:
        stride_x = fov_w_mm - overlap_mm
        stride_y = fov_h_mm - overlap_mm
        tiles_x  = ceil(item_w_mm / stride_x)
        tiles_y  = ceil(item_h_mm / stride_y)
    """
    from UI.sections.cam_models import ProjectionTask

    stride_x = max(0.1, fov_w_mm - overlap_mm)
    stride_y = max(0.1, fov_h_mm - overlap_mm)

    tiles_x = max(1, int(ceil(item.w_mm / stride_x)))
    tiles_y = max(1, int(ceil(item.h_mm / stride_y)))

    # si cabe en un solo tile, no subdividir
    if item.w_mm <= fov_w_mm and item.h_mm <= fov_h_mm:
        tiles_x, tiles_y = 1, 1

    total_tiles = tiles_x * tiles_y
    tasks = []

    # resolucion del fov en pixeles
    fov_w_px = int(round(fov_w_mm / mm_per_pixel))
    fov_h_px = int(round(fov_h_mm / mm_per_pixel))

    for ti in range(tiles_y):
        for tj in range(tiles_x):
            # coordenada absoluta del tile en mm
            tile_x_mm = item.x_mm + tj * stride_x
            tile_y_mm = item.y_mm + ti * stride_y

            # recortar la imagen fuente en pixeles
            if item.data is not None:
                px_x = int(round(tj * stride_x / mm_per_pixel))
                px_y = int(round(ti * stride_y / mm_per_pixel))

                src_h, src_w = item.data.shape[:2]
                px_x = min(px_x, src_w)
                px_y = min(px_y, src_h)

                crop_w = min(fov_w_px, src_w - px_x)
                crop_h = min(fov_h_px, src_h - px_y)

                if crop_w <= 0 or crop_h <= 0:
                    continue

                tile_img = item.data[px_y:px_y + crop_h, px_x:px_x + crop_w]

                # padding si el recorte es menor que el fov
                if tile_img.shape[0] < fov_h_px or tile_img.shape[1] < fov_w_px:
                    if tile_img.ndim == 2:
                        padded = np.zeros((fov_h_px, fov_w_px), dtype=tile_img.dtype)
                    else:
                        padded = np.zeros(
                            (fov_h_px, fov_w_px, tile_img.shape[2]),
                            dtype=tile_img.dtype
                        )
                    padded[:tile_img.shape[0], :tile_img.shape[1]] = tile_img
                    tile_img = padded
            else:
                # para primitivas (rect, line), generar imagen blanca del tamanio del fov
                tile_w_px = min(fov_w_px, int(round(item.w_mm / mm_per_pixel)))
                tile_h_px = min(fov_h_px, int(round(item.h_mm / mm_per_pixel)))
                tile_img = np.ones((fov_h_px, fov_w_px), dtype=np.uint8) * 255

                # si es un solo tile, recortar al tamanio real
                if total_tiles == 1:
                    canvas = np.zeros((fov_h_px, fov_w_px), dtype=np.uint8)
                    canvas[:tile_h_px, :tile_w_px] = 255
                    tile_img = canvas

            tasks.append(ProjectionTask(
                target_x_mm=tile_x_mm,
                target_y_mm=tile_y_mm,
                image_data=tile_img,
                exposure_s=item.exposure_s,
                delay_s=item.delay_s,
                source_item_uid=item.uid,
                tile_row=ti,
                tile_col=tj,
                tile_total=total_tiles,
            ))

    return tasks


def optimize_path(tasks):
    """
    ordena la cola usando heuristica de vecino mas cercano desde (0,0).

    esto minimiza la distancia total de viaje en el aire (movimiento
    sin exposicion) reduciendo el tiempo total de ejecucion.
    """
    if len(tasks) <= 1:
        return list(tasks)

    remaining = list(tasks)
    ordered = []
    current = (0.0, 0.0)

    while remaining:
        nearest = min(
            remaining,
            key=lambda t: hypot(
                t.target_x_mm - current[0],
                t.target_y_mm - current[1]
            )
        )
        ordered.append(nearest)
        current = (nearest.target_x_mm, nearest.target_y_mm)
        remaining.remove(nearest)

    return ordered
