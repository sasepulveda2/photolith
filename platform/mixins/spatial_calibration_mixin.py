
"""
Mixin: Herramienta de calibración de patrón (tamaño y exposición).
Integra la calibración directamente en la vista principal usando la barra lateral de Pattern Calib.
"""
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QApplication
from PyQt5.QtCore import Qt
import math
import json
import os
import cv2
from matplotlib.lines import Line2D
from matplotlib.widgets import Cursor

from constants import CONFIG_FILE

class SpatialCalibrationMixin:
    """Maneja la lógica de calibración espacial de la imagen (píxel a mm) y exposición en la vista principal."""

    def _init_spatial_calibration(self):
        """inicializa variables de estado de la calibracion de patron y exposicion."""
        self.mm_per_pixel = None
        self._pattern_calib_view_active = False
        
        # variables de dibujo de la linea de calibracion espacial
        self._spatial_line_start = None
        self._spatial_line_artist = None
        self._spatial_pixel_distance = 0.0
        self._spatial_cursor = None
        self._spatial_cids = []
        
        # paneo temporal con rueda
        self._pan_start_x = None
        self._pan_start_y = None
        self._pan_start_xlim = None
        self._pan_start_ylim = None

        # imagen de calibracion propia si el usuario la carga
        self._calib_custom_image = None
        
        # variables para la matriz de exposicion dinamica
        from PyQt5.QtCore import QTimer
        self._exp_timer = QTimer()
        self._exp_timer.timeout.connect(self._exposure_tick)
        self._exp_ui_timer = QTimer()
        self._exp_ui_timer.timeout.connect(self._update_exp_time_ui)
        self._exp_start_time = 0.0
        self._exp_matrix = None
        self._exp_current_stripe = 0
        self._exp_total_stripes = 0
        self._exp_step_ms = 0
        self._exp_direction = "Horizontal"
        self._exp_mode = "Decremento"
        
        # cargar escala guardada si existe
        self._load_spatial_scale()

    def toggle_pattern_calibration_view(self):
        """Activa o desactiva el modo de vista de Calibración de Patrón."""
        self._pattern_calib_view_active = not self._pattern_calib_view_active
        
        if self._pattern_calib_view_active:
            self._activate_pattern_calib_view()
        else:
            self._deactivate_pattern_calib_view()

    def _activate_pattern_calib_view(self):
        """Desactiva otras vistas y muestra la barra de calibración de patrón."""
        if getattr(self, "grid_view_active", False):
            self.toggle_grid_view()
        if getattr(self, "calibration_view_active", False):
            self.toggle_calibration_view()
        if getattr(self, "_ruler_scale_view_active", False):
            self.toggle_ruler_scale_view()
        if getattr(self, "_motors_view_active", False):
            self.toggle_motors_view()

        # Ocultar sidebar normal
        if hasattr(self, "_main_sidebar"):
            self._main_sidebar.setVisible(False)
            
        # Mostrar panel de calibración de patrón
        if hasattr(self, "pattern_calib_sidebar_widget"):
            self.pattern_calib_sidebar_widget.setVisible(True)

        # Actualizar botón
        if hasattr(self, "pattern_calib_button"):
            self.pattern_calib_button.setText("Salir calibración")

        self.figure.clear()
        self.ax = self.figure.add_subplot(111)

        # Conectar eventos de matplotlib al canvas principal
        self._spatial_cids = [
            self.canvas.mpl_connect("button_press_event", self._spatial_on_mouse_press),
            self.canvas.mpl_connect("button_release_event", self._spatial_on_mouse_release),
            self.canvas.mpl_connect("motion_notify_event", self._spatial_on_mouse_move),
            self.canvas.mpl_connect("scroll_event", self._spatial_on_mouse_scroll),
        ]
        
        # Configurar cursor cruzado
        self._spatial_cursor = Cursor(self.ax, useblit=True, color='cyan', linewidth=1)



        # Renderizamos el contenido inicial (Tamaño Espacial = 0)
        self._update_pattern_calib_canvas(self.pattern_calib_stacked.currentIndex())
        self.log_to_console("Modo Calibración de Patrón activado.", "INFO")

    def _update_pattern_calib_canvas(self, index):
        """Actualiza el lienzo dependiendo si estamos en Tamaño (0) o Exposición (1)."""
        if not hasattr(self, "ax") or self.ax is None:
            return
            
        self.ax.clear()
        
        if index == 0:
            # Vista de Tamaño Espacial
            img_to_show = self._calib_custom_image
            if img_to_show is None:
                img_to_show = getattr(self, "pattern", getattr(self, "image_on_grid", None))
                
            if img_to_show is not None:
                self.ax.imshow(img_to_show, cmap='gray')
                self.ax.axis('off')
            else:
                self.ax.set_facecolor("black")
                self.ax.text(0.5, 0.5, "Cargue un patrón para calibrar", 
                             transform=self.ax.transAxes, ha="center", va="center", color="#888888")
                self.ax.axis('off')
                
            # Habilitamos el cursor cruzado
            if self._spatial_cursor:
                self._spatial_cursor.set_active(True)
                
        elif index == 1:
            # Vista de Exposición
            self.ax.set_facecolor("#1E1E1E")
            self.ax.text(0.5, 0.5, "Controles de exposición", 
                         transform=self.ax.transAxes, ha="center", va="center", color="#888888")
            self.ax.axis('off')
            if self._spatial_cursor:
                self._spatial_cursor.set_active(False)
        elif index == 2:
            # Vista de Test CD
            self.ax.set_facecolor("#1E1E1E")
            self.ax.text(0.5, 0.5, "Presiona Previsualizar para ver el Patrón CD aquí", 
                         transform=self.ax.transAxes, ha="center", va="center", color="#888888")
            self.ax.axis('off')
            if self._spatial_cursor:
                self._spatial_cursor.set_active(False)
                
        self.canvas.draw_idle()

    def _deactivate_pattern_calib_view(self):
        """Regresa a la vista principal normal."""
        # Ocultar panel, mostrar sidebar normal
        if hasattr(self, "pattern_calib_sidebar_widget"):
            self.pattern_calib_sidebar_widget.setVisible(False)
        if hasattr(self, "_main_sidebar"):
            self._main_sidebar.setVisible(True)

        if hasattr(self, "pattern_calib_button"):
            self.pattern_calib_button.setText("Calibración de Patrón")

        # Desconectar eventos y limpiar cursor
        for cid in self._spatial_cids:
            self.canvas.mpl_disconnect(cid)
        self._spatial_cids.clear()
        
        if self._spatial_cursor:
            # Cursor no tiene un método .remove() o similar fácil, pero deshabilitamos sus eventos
            self._spatial_cursor.disconnect_events()
            self._spatial_cursor = None

        if self._spatial_line_artist:
            try:
                self._spatial_line_artist.remove()
            except Exception:
                pass
            self._spatial_line_artist = None

        self._spatial_line_start = None
        self._spatial_pixel_distance = 0.0

        # Restaurar la imagen principal original
        if getattr(self, "pattern", None) is not None:
            self.simulate_optics()
        else:
            if hasattr(self, "canvas") and hasattr(self, "ax"):
                self.ax.clear()
                self.ax.set_facecolor("#121212")
                self.ax.axis('off')
                self.canvas.draw_idle()



        self.log_to_console("Modo Calibración de Patrón desactivado.", "INFO")

    # ═══════════════════════════════════════════════════════════════════════
    # LOGICA DE CALIBRACIÓN ESPACIAL
    # ═══════════════════════════════════════════════════════════════════════

    def load_calibration_pattern(self):
        """Permite cargar una imagen específica para usar en la calibración."""
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Patrón de Calibración", "", "Imágenes (*.png *.jpg *.jpeg *.bmp *.tiff);;Todos los archivos (*)", options=options
        )
        if file_path:
            img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                # Normalizar si se desea o simplemente usar la gris
                self._calib_custom_image = img / 255.0 if img.max() > 1 else img
                self._spatial_line_start = None
                self._spatial_pixel_distance = 0.0
                if hasattr(self, "input_mm_calib"):
                    self.input_mm_calib.clear()
                
                self.ax.clear()
                self.ax.imshow(self._calib_custom_image, cmap='gray')
                self.ax.axis('off')
                self.canvas.draw_idle()
                
                # Restauramos cursor xq ax.clear() lo borra
                self._spatial_cursor = Cursor(self.ax, useblit=True, color='cyan', linewidth=1)
                self.log_to_console("Imagen de calibración cargada.", "SUCCESS")
            else:
                QMessageBox.warning(self, "Error", "No se pudo cargar la imagen.")

    def _spatial_on_mouse_scroll(self, event):
        if getattr(self, "pattern_calib_stacked", None) is not None and self.pattern_calib_stacked.currentIndex() != 0:
            return
        if getattr(self, "btn_toggle_motor_calib", None) and self.btn_toggle_motor_calib.isChecked():
            return
        if event.inaxes != self.ax:
            return
            
        base_scale = 1.1
        if event.button == 'up':
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            scale_factor = base_scale
        else:
            scale_factor = 1
            
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        
        xdata = event.xdata
        ydata = event.ydata
        
        new_xlim = [xdata - (xdata - xlim[0]) * scale_factor,
                    xdata + (xlim[1] - xdata) * scale_factor]
        new_ylim = [ydata - (ydata - ylim[0]) * scale_factor,
                    ydata + (ylim[1] - ydata) * scale_factor]
                    
        self.ax.set_xlim(new_xlim)
        self.ax.set_ylim(new_ylim)
        self.canvas.draw_idle()

    def _spatial_on_mouse_press(self, event):
        if getattr(self, "pattern_calib_stacked", None) is not None and self.pattern_calib_stacked.currentIndex() != 0:
            return
        if getattr(self, "btn_toggle_motor_calib", None) and self.btn_toggle_motor_calib.isChecked():
            return
        if event.button == 1 and event.inaxes == self.ax:
            self._spatial_line_start = (event.xdata, event.ydata)
            if self._spatial_line_artist:
                try:
                    self._spatial_line_artist.remove()
                except Exception:
                    pass
                
            self._spatial_line_artist = Line2D(
                [event.xdata, event.xdata], 
                [event.ydata, event.ydata], 
                color='red', linewidth=2, marker='+'
            )
            self.ax.add_line(self._spatial_line_artist)
            self.canvas.draw_idle()
            
        elif event.button == 2 and event.inaxes == self.ax:
            # Paneo central
            self._pan_start_x = event.x
            self._pan_start_y = event.y
            self._pan_start_xlim = self.ax.get_xlim()
            self._pan_start_ylim = self.ax.get_ylim()
            QApplication.setOverrideCursor(Qt.ClosedHandCursor)

    def _spatial_on_mouse_move(self, event):
        if getattr(self, "pattern_calib_stacked", None) is not None and self.pattern_calib_stacked.currentIndex() != 0:
            return
        if getattr(self, "btn_toggle_motor_calib", None) and self.btn_toggle_motor_calib.isChecked():
            return
        if self._pan_start_x is not None and self._pan_start_y is not None:
            # Efectuar paneo
            x0, y0 = self.ax.transData.inverted().transform((self._pan_start_x, self._pan_start_y))
            x1, y1 = self.ax.transData.inverted().transform((event.x, event.y))
            
            shift_x = x1 - x0
            shift_y = y1 - y0
            
            self.ax.set_xlim(self._pan_start_xlim[0] - shift_x, self._pan_start_xlim[1] - shift_x)
            self.ax.set_ylim(self._pan_start_ylim[0] - shift_y, self._pan_start_ylim[1] - shift_y)
            self.canvas.draw_idle()
            return

        if self._spatial_line_start and self._spatial_line_artist and event.inaxes == self.ax:
            x1, y1 = self._spatial_line_start
            x2, y2 = event.xdata, event.ydata
            
            # Snap a 90 grados con Shift
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.ShiftModifier:
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx > dy:
                    y2 = y1
                else:
                    x2 = x1
                    
            self._spatial_line_artist.set_data([x1, x2], [y1, y2])
            self.canvas.draw_idle()
            
            # Actualizar label en tiempo real
            dist = math.sqrt((event.xdata - x1)**2 + (event.ydata - y1)**2)
            if hasattr(self, "lbl_pixels_calib"):
                self.lbl_pixels_calib.setText(f"Distancia en Píxeles: {dist:.2f}")

    def _spatial_on_mouse_release(self, event):
        if getattr(self, "pattern_calib_stacked", None) is not None and self.pattern_calib_stacked.currentIndex() != 0:
            return
        if getattr(self, "btn_toggle_motor_calib", None) and self.btn_toggle_motor_calib.isChecked():
            return
        if event.button == 2:
            self._pan_start_x = None
            self._pan_start_y = None
            self._pan_start_xlim = None
            self._pan_start_ylim = None
            QApplication.restoreOverrideCursor()
            return

        if event.button == 1 and self._spatial_line_start:
            x1, y1 = self._spatial_line_start
            x2, y2 = event.xdata, event.ydata
            if x2 is None or y2 is None:
                return
                
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.ShiftModifier:
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx > dy:
                    y2 = y1
                else:
                    x2 = x1
            
            self._spatial_pixel_distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            if hasattr(self, "lbl_pixels_calib"):
                self.lbl_pixels_calib.setText(f"Distancia en Píxeles: {self._spatial_pixel_distance:.2f}")
                
            self._spatial_line_start = None
            self.calculate_spatial_scale()

    def calculate_spatial_scale(self):
        """Recalcula la escala según la línea dibujada y el input en mm."""
        if self._spatial_pixel_distance < 1.0 or not hasattr(self, "input_mm_calib"):
            return
            
        text = self.input_mm_calib.text().replace(',', '.')
        try:
            val_mm = float(text)
            if val_mm > 0:
                calc = val_mm / self._spatial_pixel_distance
                if hasattr(self, "lbl_result_calib"):
                    self.lbl_result_calib.setText(f"Escala: {calc:.5f} mm/px")
                return
        except ValueError:
            pass
            
        if hasattr(self, "lbl_result_calib"):
            self.lbl_result_calib.setText("Escala: -")

    def save_spatial_scale_from_ui(self):
        """Guarda permanentemente la escala calculada."""
        if self._spatial_pixel_distance < 1.0 or not hasattr(self, "input_mm_calib"):
            self.log_to_console("Debe dibujar una línea válida primero.", "WARNING")
            return
            
        text = self.input_mm_calib.text().replace(',', '.')
        try:
            val_mm = float(text)
            if val_mm > 0:
                self.mm_per_pixel = val_mm / self._spatial_pixel_distance
                self._save_spatial_scale()
                self.update_spatial_labels()
                self.log_to_console(f"Calibración guardada: {self.mm_per_pixel:.5f} mm/px", "SUCCESS")
                
                # Desactivar la vista automáticamente al guardar para mayor fluidez
                self.toggle_pattern_calibration_view()
                return
        except ValueError:
            pass
        self.log_to_console("Valor en milímetros inválido.", "WARNING")

    def update_spatial_labels(self):
        """Actualiza el panel derecho normal con el tamaño físico de la imagen si está calibrada."""
        if not hasattr(self, "pixel_scale_label") or not hasattr(self, "image_physical_size_label"):
            return
            
        if self.mm_per_pixel is None:
            self.pixel_scale_label.setText("Escala: No calibrada")
            self.image_physical_size_label.setText("Tamaño físico: -")
            return
            
        self.pixel_scale_label.setText(f"Escala: {self.mm_per_pixel:.5f} mm/px")
        
        if getattr(self, "image_on_grid", None) is not None:
            h, w = self.image_on_grid.shape[:2]
            width_mm = w * self.mm_per_pixel
            height_mm = h * self.mm_per_pixel
            self.image_physical_size_label.setText(f"Tamaño físico: {width_mm:.2f} x {height_mm:.2f} mm")
        else:
            self.image_physical_size_label.setText("Tamaño físico: -")

    def _save_spatial_scale(self):
        """Guarda la escala en config_file."""
        if self.mm_per_pixel is None:
            return
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        config['mm_per_pixel'] = self.mm_per_pixel
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error guardando calibración espacial: {e}")

    def _load_spatial_scale(self):
        """Carga la escala desde el archivo si existe."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    if 'mm_per_pixel' in config:
                        self.mm_per_pixel = float(config['mm_per_pixel'])
            except:
                pass

    def _save_exposure_params(self):
        """Guarda los parametros de matriz de exposicion en config_file."""
        if not hasattr(self, "input_exp_base"):
            return
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        config['exp_base_time'] = self.input_exp_base.value()
        config['exp_step_time'] = self.input_exp_step.value()
        config['exp_stripes'] = self.input_exp_stripes.value()
        config['exp_direction'] = self.combo_exp_dir.currentText()
        config['exp_mode'] = self.combo_exp_mode.currentText()
        if hasattr(self, "chk_exp_invert"):
            config['exp_invert'] = self.chk_exp_invert.isChecked()
            
        if hasattr(self, "input_grating_lines"):
            config['grating_lines'] = self.input_grating_lines.value()
            config['grating_width'] = self.input_grating_width.value()
            config['grating_spacing'] = self.input_grating_spacing.value()
            
        if hasattr(self, "input_cd_limit"):
            config['cd_limit'] = self.input_cd_limit.value()
            config['cd_spacing'] = self.input_cd_spacing.value()
            config['cd_orient'] = self.combo_cd_orient.currentText()
            if hasattr(self, "chk_cd_invert"):
                config['cd_invert'] = self.chk_cd_invert.isChecked()
            if hasattr(self, "input_cd_exp_time"):
                config['cd_exp_time'] = self.input_cd_exp_time.value()
                
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error guardando parametros de exposicion: {e}")
                

        # Actualizar dimensiones dinámicamente
        if hasattr(self, "_update_exposure_dimensions"):
            self._update_exposure_dimensions()
            
    def _update_exposure_dimensions(self):
        """Calcula y actualiza el texto de las dimensiones físicas de la franja."""
        if getattr(self, "pattern_calib_stacked", None) is None or self.pattern_calib_stacked.currentIndex() != 1:
            return
            
        try:
            self._exp_direction = self.combo_exp_dir.currentText()
            
            if "Líneas Múltiples" in self._exp_direction and hasattr(self, "input_grating_lines"):
                self._exp_total_stripes = int(self.input_grating_lines.value())
            else:
                self._exp_total_stripes = self.input_exp_stripes.value()
            
            if hasattr(self, "lbl_exp_dimensions"):
                if self._exp_direction in ["Horizontal", "Vertical"]:
                    if getattr(self.projection_window, "screen_geometry", None):
                        h = self.projection_window.screen_geometry.height()
                        w = self.projection_window.screen_geometry.width()
                    else:
                        h, w = 1080, 1920
                    
                    if self._exp_direction == "Horizontal":
                        px_per_block = w / max(1, self._exp_total_stripes)
                    else:
                        px_per_block = h / max(1, self._exp_total_stripes)
                        
                    mm_per_px = getattr(self, "mm_per_pixel", None)
                    if mm_per_px:
                        mm = px_per_block * mm_per_px
                        um = mm * 1000
                        self.lbl_exp_dimensions.setText(f"Dimensión por franja: {px_per_block:.1f} px | {mm:.2f} mm | {um:.1f} µm")
                    else:
                        self.lbl_exp_dimensions.setText(f"Dimensión por franja: {px_per_block:.1f} px (Calib. física pendiente)")
                else:
                    self.lbl_exp_dimensions.setText("Dimensión por franja: Variable (forma central)")
        except AttributeError:
            pass
            
    def _preview_exposure_matrix(self):
        """Genera una vista previa del primer bloque en el canvas y actualiza dimensiones."""
        if not hasattr(self, "ax") or getattr(self, "pattern_calib_stacked", None) is None:
            return
            
        if self.pattern_calib_stacked.currentIndex() != 1:
            return
            
        try:
            self._exp_total_stripes = self.input_exp_stripes.value()
            self._exp_direction = self.combo_exp_dir.currentText()
            self._exp_mode = self.combo_exp_mode.currentText()
            self._exp_invert_colors = self.chk_exp_invert.isChecked() if hasattr(self, "chk_exp_invert") else False
            
            self._exp_current_stripe = 0
            matrix = self._draw_current_stripe()
            
            # Invertir para enviar (simular proyector invertido)
            matrix_to_send = matrix.copy()
            if getattr(self, "invert_projection", False):
                matrix_to_send = 255 - matrix_to_send
                
            self.ax.clear()
            self.ax.imshow(matrix, cmap='gray')
            self.ax.axis('off')
            if hasattr(self, "canvas"):
                self.canvas.draw_idle()
                

        except AttributeError:
            pass
            


    # ═══════════════════════════════════════════════════════════════════════
    # LOGICA DE MATRIZ DE EXPOSICION DINAMICA
    # ═══════════════════════════════════════════════════════════════════════

    def start_exposure_matrix(self):
        """inicia la matriz de exposicion dinamica leyendo parametros y proyectando el fondo blanco."""
        if not getattr(self, "projector_active", False):
            if hasattr(self, "log_to_console"):
                self.log_to_console("error: el proyector no esta activo. enciéndelo primero con el botón 'Proyectar'.", "error")
            return

        proj = getattr(self, "projection_window", None)
        if not proj or not proj.screen_geometry:
            self.log_to_console("error: geometria de pantalla no detectada.", "error")
            return

        w = proj.screen_geometry.width()
        h = proj.screen_geometry.height()

        try:
            base_time_s = float(self.input_exp_base.value())
            step_time_s = float(self.input_exp_step.value())
            self._exp_direction = self.combo_exp_dir.currentText()
            self._exp_mode = self.combo_exp_mode.currentText()
            self._exp_invert_colors = self.chk_exp_invert.isChecked() if hasattr(self, "chk_exp_invert") else False
            
            if "Líneas Múltiples" in self._exp_direction and hasattr(self, "input_grating_lines"):
                self._exp_total_stripes = int(self.input_grating_lines.value())
            else:
                self._exp_total_stripes = int(self.input_exp_stripes.value())
        except ValueError:
            self.log_to_console("error: parametros de exposicion invalidos.", "error")
            return

        if self._exp_total_stripes <= 0 or base_time_s < 0 or step_time_s <= 0:
            self.log_to_console("error: parametros deben ser positivos.", "error")
            return

        self._exp_step_ms = int(step_time_s * 1000)
        
        self._exp_current_stripe = -1 if base_time_s > 0 else 0
        self._exp_matrix = self._draw_current_stripe()

        matrix_to_send = self._prepare_exp_matrix_to_send(self._exp_matrix)
            
        proj.update_segment(matrix_to_send)
        
        # Mostrar vista previa en el canvas (Optimizado)
        if hasattr(self, "ax"):
            if not hasattr(self, "_exp_image_artist") or self._exp_image_artist not in self.ax.images:
                self.ax.clear()
                self._exp_image_artist = self.ax.imshow(matrix_to_send, cmap='gray')
                self.ax.axis('off')
            else:
                self._exp_image_artist.set_data(matrix_to_send)
                # Opcionalmente, ajustar límites de contraste si cambian drásticamente
                self._exp_image_artist.set_clim(vmin=0, vmax=255)
            if hasattr(self, "canvas"):
                self.canvas.draw_idle()

        self._exp_current_stripe += 1

        if hasattr(self, "lbl_exp_status"):
            self.lbl_exp_status.setText("estado: tiempo base")

        import time
        self._exp_start_time = time.time()
        self._exp_ui_timer.start(100)
        # Si el tiempo base es 0, usar el intervalo de paso como intervalo inicial
        # Esto evita que QTimer con 0ms dispare inmediatamente y reduzca la duración
        # total a (franjas - 1) * paso cuando el usuario espera que sean N * paso.
        start_interval_ms = int(base_time_s * 1000) if base_time_s > 0 else self._exp_step_ms
        self._exp_timer.start(start_interval_ms)

    def _prepare_exp_matrix_to_send(self, exp_matrix):
        matrix_to_send = exp_matrix.copy()
        if getattr(self, "pattern", None) is not None:
            pattern_img = self._apply_effects_to_segment(self.pattern)
            import cv2
            import numpy as np
            
            # Ensure pattern_img matches matrix_to_send in size
            h, w = matrix_to_send.shape[:2]
            ph, pw = pattern_img.shape[:2]
            if (ph, pw) != (h, w):
                pattern_img = cv2.resize(pattern_img, (w, h), interpolation=cv2.INTER_NEAREST)
                
            # Ensure pattern_img is uint8 [0, 255]
            if pattern_img.dtype in (np.float32, np.float64):
                pattern_img = (pattern_img * 255.0 if pattern_img.max() <= 1.0 else pattern_img).astype(np.uint8)
            else:
                pattern_img = pattern_img.astype(np.uint8)
                
            matrix_to_send = cv2.bitwise_and(pattern_img, matrix_to_send)
        else:
            if getattr(self, "invert_projection", False):
                matrix_to_send = 255 - matrix_to_send
        return matrix_to_send

    def _update_exp_time_ui(self):
        """actualiza la etiqueta de tiempo transcurrido en tiempo real."""
        if hasattr(self, "lbl_exp_time"):
            import time
            elapsed = time.time() - self._exp_start_time
            self.lbl_exp_time.setText(f"Tiempo transcurrido: {elapsed:.1f} s")

    def _draw_current_stripe(self):
        """Genera y retorna la matriz de la franja actual."""
        import numpy as np
        import cv2
        import math
        
        if getattr(self, "projection_window", None) is None:
            return np.zeros((10, 10), dtype=np.uint8)
            
        if getattr(self.projection_window, "screen_geometry", None):
            h = self.projection_window.screen_geometry.height()
            w = self.projection_window.screen_geometry.width()
        else:
            h, w = 1080, 1920
        cx, cy = w // 2, h // 2
        
        matrix = np.zeros((h, w), dtype=np.uint8)
        
        if self._exp_current_stripe == -1:
            matrix[:, :] = 255
            if getattr(self, "_exp_invert_colors", False):
                matrix = 255 - matrix
            return matrix
        
        is_decrement = "Decremento" in self._exp_mode
        
        if is_decrement:
            f = (self._exp_total_stripes - self._exp_current_stripe) / self._exp_total_stripes
        else:
            f = (self._exp_current_stripe + 1) / self._exp_total_stripes

        if self._exp_direction == "Horizontal":
            end_x = int(w * f)
            matrix[:, 0:end_x] = 255
                
        elif self._exp_direction == "Vertical":
            end_y = int(h * f)
            matrix[0:end_y, :] = 255
                
        elif self._exp_direction == "Rectángulo Central":
            rw = int(cx * f)
            rh = int(cy * f)
            if rw > 0 and rh > 0:
                matrix[cy-rh:cy+rh, cx-rw:cx+rw] = 255
                
        elif self._exp_direction == "Círculo Central":
            max_r = min(cx, cy)
            r = int(max_r * f)
            if r > 0:
                cv2.circle(matrix, (cx, cy), r, 255, -1)
                
        elif self._exp_direction in ["Líneas Múltiples (Horizontal)", "Líneas Múltiples (Vertical)"]:
            try:
                g_lines = int(self.input_grating_lines.value())
                g_width = int(self.input_grating_width.value())
                g_spacing = int(self.input_grating_spacing.value())
            except Exception:
                g_lines, g_width, g_spacing = 10, 10, 10
                
            total_size = (g_lines * g_width) + ((g_lines - 1) * g_spacing)
            
            if "Horizontal" in self._exp_direction:
                # Líneas horizontales, el barrido expone líneas enteras
                start_y = cy - (total_size // 2)
                lines_to_show = int(math.ceil(g_lines * f))
                
                for i in range(lines_to_show):
                    y0 = start_y + i * (g_width + g_spacing)
                    y1 = y0 + g_width
                    if y1 > 0 and y0 < h:
                        matrix[max(0, y0):min(h, y1), :] = 255
                            
            else:
                # Líneas verticales, el barrido expone líneas enteras
                start_x = cx - (total_size // 2)
                lines_to_show = int(math.ceil(g_lines * f))
                
                for i in range(lines_to_show):
                    x0 = start_x + i * (g_width + g_spacing)
                    x1 = x0 + g_width
                    if x1 > 0 and x0 < w:
                        matrix[:, max(0, x0):min(w, x1)] = 255
                            
        elif self._exp_direction == "Triángulo Central":
            pts = np.array([
                [cx, 0],
                [0, h],
                [w, h]
            ], dtype=np.float32)
            center = np.array([cx, cy], dtype=np.float32)
            scaled_pts = center + (pts - center) * f
            cv2.fillPoly(matrix, [scaled_pts.astype(np.int32)], 255)
            
        if getattr(self, "_exp_invert_colors", False):
            matrix = 255 - matrix
            
        return matrix

    def _exposure_tick(self):
        """calcula franjas geometricas e invierte la matriz recursivamente."""
        if getattr(self, "projection_window", None) is None:
            self.stop_exposure_matrix()
            return

        # si ya se aplicaron todas las franjas y se ha esperado el ultimo step, apagar
        if self._exp_current_stripe >= self._exp_total_stripes:
            if hasattr(self, "lbl_exp_status"):
                self.lbl_exp_status.setText("estado: proceso completado")
            self._exp_timer.stop()
            self._exp_ui_timer.stop()
            self._exp_matrix = None
            
            if getattr(self, "projection_window", None) is not None:
                self.projection_window.show_black_screen()
                
            if hasattr(self, "ax"):
                import numpy as np
                if hasattr(self, "_exp_image_artist"):
                    if getattr(self.projection_window, "screen_geometry", None):
                        h = self.projection_window.screen_geometry.height()
                        w = self.projection_window.screen_geometry.width()
                    else:
                        h, w = 1080, 1920
                    self._exp_image_artist.set_data(np.zeros((h, w), dtype=np.uint8))
                if hasattr(self, "canvas"):
                    self.canvas.draw_idle()
            return

        if self._exp_timer.interval() != self._exp_step_ms:
            self._exp_timer.setInterval(self._exp_step_ms)

        self._exp_matrix = self._draw_current_stripe()

        matrix_to_send = self._prepare_exp_matrix_to_send(self._exp_matrix)
            
        self.projection_window.update_segment(matrix_to_send)
        
        # Mostrar vista previa en el canvas (Optimizado)
        if hasattr(self, "ax"):
            if not hasattr(self, "_exp_image_artist") or self._exp_image_artist not in self.ax.images:
                self.ax.clear()
                self._exp_image_artist = self.ax.imshow(matrix_to_send, cmap='gray')
                self.ax.axis('off')
            else:
                self._exp_image_artist.set_data(matrix_to_send)
                self._exp_image_artist.set_clim(vmin=0, vmax=255)
            if hasattr(self, "canvas"):
                self.canvas.draw_idle()
                
        self._exp_current_stripe += 1

        if hasattr(self, "lbl_exp_status"):
            self.lbl_exp_status.setText(f"estado: franja {self._exp_current_stripe}/{self._exp_total_stripes}")
        
        # reconfigurar temporizador para el intervalo iterativo
        self._exp_timer.setInterval(self._exp_step_ms)
        if not self._exp_timer.isActive():
            self._exp_timer.start()

    def stop_exposure_matrix(self):
        """interrumpe timer y apaga la pantalla de proyeccion."""
        self._exp_timer.stop()
        if hasattr(self, "_exp_ui_timer"):
            self._exp_ui_timer.stop()
        self._exp_matrix = None
        
        if hasattr(self, "lbl_exp_status"):
            self.lbl_exp_status.setText("estado: detenido")
            
        proj = getattr(self, "projection_window", None)
        if proj:
            proj.show_black_screen()
            
        if hasattr(self, "ax"):
            import numpy as np
            if hasattr(self, "_exp_image_artist"):
                if getattr(self.projection_window, "screen_geometry", None):
                    h = self.projection_window.screen_geometry.height()
                    w = self.projection_window.screen_geometry.width()
                else:
                    h, w = 1080, 1920
                self._exp_image_artist.set_data(np.zeros((h, w), dtype=np.uint8))
            if hasattr(self, "canvas"):
                self.canvas.draw_idle()

    # ═══════════════════════════════════════════════════════════════════════
    # LOGICA DE TEST DE DIMENSION CRITICA (CD)
    # ═══════════════════════════════════════════════════════════════════════

    def _generate_cd_matrix(self):
        """genera la matriz para el test cd leyendo la ui. devuelve (matrix, orientacion, limite, separacion) o None."""
        proj = getattr(self, "projection_window", None)
        if not proj:
            return None
            
        try:
            limite = self.input_cd_limit.value()
            separacion = self.input_cd_spacing.value()
            orientacion = self.combo_cd_orient.currentText()
            invertir_cd = self.chk_cd_invert.isChecked() if hasattr(self, "chk_cd_invert") else False
        except AttributeError:
            return None

        h, w = proj.screen_geometry.height(), proj.screen_geometry.width()
        import numpy as np
        matrix = np.zeros((h, w), dtype=np.uint8)

        # calcular tamano total de las lineas + los espacios
        # las lineas van de 1 a limite. la suma de 1 a N es N*(N+1)/2
        suma_grosores = (limite * (limite + 1)) // 2
        # la cantidad de espacios es limite - 1
        suma_espacios = separacion * (limite - 1)
        tamano_total = suma_grosores + suma_espacios

        # calcular punto de inicio para centrar todo el bloque
        if orientacion == "Horizontal":
            # lineas horizontales se dibujan en el eje y (altura)
            inicio = (h - tamano_total) // 2
        else:
            # lineas verticales se dibujan en el eje x (ancho)
            inicio = (w - tamano_total) // 2

        # bucle para iterar sobre los pixeles del limite
        for grosor_actual in range(1, limite + 1):
            if orientacion == "Horizontal":
                # validar que no nos salimos de la pantalla
                if inicio >= 0 and inicio + grosor_actual <= h:
                    matrix[inicio : inicio + grosor_actual, :] = 255
            else:
                # validar que no nos salimos de la pantalla
                if inicio >= 0 and inicio + grosor_actual <= w:
                    matrix[:, inicio : inicio + grosor_actual] = 255
            
            # mover el punto de inicio para la siguiente linea
            # sumamos el grosor que acabamos de pintar mas el espaciado
            inicio += grosor_actual + separacion

        # si se requiere, se invierten colores localmente
        if invertir_cd:
            matrix = 255 - matrix

        # si se requiere, se invierten colores de forma global
        if getattr(self, "invert_projection", False):
            matrix = 255 - matrix

        return matrix, orientacion, limite, separacion

    def preview_cd_test(self):
        """previsualiza el test cd en el panel principal (ax)."""
        res = self._generate_cd_matrix()
        if not res: return
        matrix, orient, lim, sep = res
        
        if hasattr(self, "ax") and self.ax is not None:
            self.ax.clear()
            self.ax.imshow(matrix, cmap='gray')
            self.ax.axis('off')
            if hasattr(self, "canvas"):
                self.canvas.draw()
        
        if hasattr(self, "log_to_console"):
            self.log_to_console(f"exito: previsualizando test cd en panel principal ({orient}, limite: {lim}px, sep: {sep}px).", "success")

    def expose_cd_test(self):
        """inicia la exposicion controlada por tiempo del test cd."""
        if not getattr(self, "projector_active", False):
            if hasattr(self, "log_to_console"):
                self.log_to_console("error: el proyector no esta activo. activalo primero.", "error")
            return
            
        res = self._generate_cd_matrix()
        if not res: return
        matrix, orient, lim, sep = res
        
        try:
            exp_time = self.input_cd_exp_time.value()
        except AttributeError:
            exp_time = 10.0
            
        self.projection_window.update_segment(matrix)
        
        # iniciar timer
        from PyQt5.QtCore import QTimer
        self._cd_timer = QTimer(self)
        self._cd_timer.setSingleShot(True)
        self._cd_timer.timeout.connect(self.stop_cd_exposure)
        self._cd_timer.start(int(exp_time * 1000))
        
        if hasattr(self, "log_to_console"):
            self.log_to_console(f"exito: iniciando test cd por {exp_time}s ({orient}, limite: {lim}px).", "success")

    def stop_cd_exposure(self):
        """detiene la exposicion del test cd y pone la pantalla en negro."""
        if hasattr(self, "_cd_timer") and self._cd_timer.isActive():
            self._cd_timer.stop()
            
        proj = getattr(self, "projection_window", None)
        if proj:
            proj.show_black_screen()
        if hasattr(self, "log_to_console"):
            self.log_to_console("estado: exposicion de test cd completada o detenida.", "info")

    def save_cd_image(self):
        """guarda el patron del test cd generado actualmente como imagen .png."""
        res = self._generate_cd_matrix()
        if not res: return
        matrix, orient, lim, sep = res
        
        from PyQt5.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getSaveFileName(self, "Guardar Patrón CD", f"patron_cd_{orient}_{lim}px.png", "Images (*.png)")
        if filename:
            import cv2
            cv2.imwrite(filename, matrix)
            if hasattr(self, "log_to_console"):
                self.log_to_console(f"exito: patron cd guardado en {filename}.", "success")

    # ═══════════════════════════════════════════════════════════════════════
    # LOGICA DE CALIBRACION CON MOTORES (SOLAPAMIENTO)
    # ═══════════════════════════════════════════════════════════════════════

    def render_motor_calib_pattern(self, preview_only=True):
        """genera y devuelve dos lineas separadas por distancia u (en pixeles)."""
        proj = getattr(self, "projection_window", None)
        if not proj: return None
        
        try:
            u_dist = self.input_motor_u.value()
            axis_text = self.combo_motor_axis.currentText()
            line_w = self.input_motor_line_width.value()
        except AttributeError:
            return None
            
        h, w = proj.screen_geometry.height(), proj.screen_geometry.width()
        import numpy as np
        matrix = np.zeros((h, w), dtype=np.uint8)
        
        # determinar centros
        cy, cx = h // 2, w // 2
        offset = u_dist // 2
        
        # mitad del grosor para distribuir uniformemente (grosor impar/par)
        w_start = -(line_w // 2)
        w_end = w_start + line_w
        
        # dibujar las lineas con el grosor indicado (siempre blancas sobre negro)
        if "X" in axis_text:
            # calibrar eje x = lineas verticales separadas horizontalmente
            for lw in range(w_start, w_end):
                if cx - offset + lw >= 0 and cx - offset + lw < w:
                    matrix[:, cx - offset + lw] = 255
                if cx + offset + lw >= 0 and cx + offset + lw < w:
                    matrix[:, cx + offset + lw] = 255
        else:
            # calibrar eje y = lineas horizontales separadas verticalmente
            for lw in range(w_start, w_end):
                if cy - offset + lw >= 0 and cy - offset + lw < h:
                    matrix[cy - offset + lw, :] = 255
                if cy + offset + lw >= 0 and cy + offset + lw < h:
                    matrix[cy + offset + lw, :] = 255
                
        # previsualizar en main ui
        if preview_only and hasattr(self, "ax") and self.ax is not None and self.pattern_calib_stacked.currentIndex() == 0:
            self.ax.clear()
            self.ax.imshow(matrix, cmap='gray')
            self.ax.axis('off')
            if hasattr(self, "canvas"):
                self.canvas.draw()
                
        return matrix

    def preview_motor_calib(self):
        """previsualiza en el proyector la matriz actual de motores."""
        if not getattr(self, "projector_active", False):
            if hasattr(self, "log_to_console"):
                self.log_to_console("error: el proyector no esta activo.", "error")
            return
            
        matrix = self.render_motor_calib_pattern(preview_only=False)
        if matrix is not None:
            self.projection_window.update_segment(matrix)
            if hasattr(self, "log_to_console"):
                self.log_to_console("exito: previsualizando lineas de motor.", "success")
                
    def expose_motor_calib(self):
        """inicia la exposicion cronometrada de las lineas de calibracion."""
        if not getattr(self, "projector_active", False):
            if hasattr(self, "log_to_console"):
                self.log_to_console("error: enciende el proyector primero.", "error")
            return
            
        matrix = self.render_motor_calib_pattern(preview_only=False)
        if matrix is None: return
        
        from PyQt5.QtCore import QTimer
        self.projection_window.update_segment(matrix)
        
        try:
            t = self.input_motor_exp_time.value()
        except:
            t = 10.0
            
        if hasattr(self, "log_to_console"):
            self.log_to_console(f"estado: iniciando exposicion de motor ({t}s).", "info")
            
        self._motor_timer = QTimer(self)
        self._motor_timer.setSingleShot(True)
        self._motor_timer.timeout.connect(self.stop_motor_exposure)
        self._motor_timer.start(int(t * 1000))

    def stop_motor_exposure(self):
        """detiene la exposicion del patron de motores."""
        if hasattr(self, "_motor_timer") and self._motor_timer.isActive():
            self._motor_timer.stop()
            
        proj = getattr(self, "projection_window", None)
        if proj:
            proj.show_black_screen()
        if hasattr(self, "log_to_console"):
            self.log_to_console("estado: exposicion de motores detenida.", "info")

    def move_motor_calib(self, direction):
        """mueve el motor fisico la distancia configurada."""
        if not hasattr(self, "motor_controller_instance") or not self.motor_controller_instance:
            if hasattr(self, "log_to_console"):
                self.log_to_console("error: los motores no estan conectados.", "error")
            return
            
        try:
            axis_text = self.combo_motor_axis.currentText()
            axis = "X" if "X" in axis_text else "Y"
        except AttributeError:
            return
            
        try:
            mm = self.input_motor_dist_mm.value()
        except:
            mm = 1.0
            
        # 80 pasos = 1 mm fisico. si direction es -1, vuelve
        steps = int(80 * mm) * direction
        
        try:
            self.motor_controller_instance.step_move(axis, steps)
            if hasattr(self, "log_to_console"):
                accion = "avanzando" if direction > 0 else "retrocediendo"
                self.log_to_console(f"motor: {accion} {axis} {mm} mm ({steps} pasos).", "info")
        except Exception as e:
            if hasattr(self, "log_to_console"):
                self.log_to_console(f"error al mover motor: {e}", "error")

    def save_motor_calib(self):
        """guarda la distancia u actual como el factor global de conversion px/mm."""
        try:
            u_dist = self.input_motor_u.value()
        except AttributeError:
            return
            
        import os, json
        from constants import CONFIG_FILE
        config = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
                
        config['motor_px_per_mm'] = u_dist
        config['motor_calib_axis'] = self.combo_motor_axis.currentText()
        config['motor_calib_dist_mm'] = self.input_motor_dist_mm.value()
        config['motor_exp_time'] = self.input_motor_exp_time.value()
        config['motor_calib_line_width'] = self.input_motor_line_width.value()
        
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            if hasattr(self, "log_to_console"):
                self.log_to_console(f"exito: factor de calibracion guardado ({u_dist} px/mm).", "success")
        except Exception as e:
            if hasattr(self, "log_to_console"):
                self.log_to_console(f"error al guardar factor: {e}", "error")
