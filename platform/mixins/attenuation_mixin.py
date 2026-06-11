"""
Mixin de matrices de atenuacion.

Generacion, previsualizacion, persistencia y aplicacion de matrices
de compensacion de uniformidad para correccion del proyector.
"""
from PyQt5.QtWidgets import QLabel
from matplotlib.backends.backend_qtagg import FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QVBoxLayout
from PyQt5.QtWidgets import QDialog
import cv2
import numpy as np

from PyQt5.QtWidgets import QMessageBox, QFileDialog


class AttenuationMixin:
    """Generacion y gestion de matrices de atenuacion."""

    def save_calibration_data(self, *args):
        """Guarda los datos de calibración en archivos."""
        try:
            import json
            import os

            cache_dir = "cache_photolith"
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)

            if self.attenuation_matrix is not None:
                np.save(
                    os.path.join(cache_dir, "calibration_matrix.npy"),
                    self.attenuation_matrix,
                )
            config = {
                "strength": self.attenuation_strength,
                "method_index": self.attenuation_method_combo.currentIndex(),
                "enabled": self.apply_attenuation_to_grid,
                "threshold": self.calibration_threshold,
                "flip_x": self.calibration_flip_x,
                "flip_y": self.calibration_flip_y,
            }

            with open(os.path.join(cache_dir, "calibration_config.json"), "w") as f:
                json.dump(config, f)

            self.log_to_console("Datos de calibración guardados correctamente", "INFO")

        except Exception as e:
            self.log_to_console(f"Error al guardar calibración: {str(e)}", "ERROR")



    def load_calibration_data(self):
        """Carga los datos de calibración guardados."""
        try:
            import json
            import os

            cache_dir = "cache_photolith"
            matrix_path = os.path.join(cache_dir, "calibration_matrix.npy")
            config_path = os.path.join(cache_dir, "calibration_config.json")

            if os.path.exists(matrix_path):
                self.attenuation_matrix = np.load(matrix_path)
                if hasattr(self, "system_console"):
                    self.log_to_console("Matriz de calibración cargada", "INFO")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)

                if "strength" in config:
                    self.attenuation_strength = config["strength"]
                    if hasattr(self, "attenuation_strength_slider"):
                        self.attenuation_strength_slider.setValue(
                            int(self.attenuation_strength)
                        )
                        self.attenuation_strength_label.setText(
                            f"{self.attenuation_strength}%"
                        )

                if "method_index" in config:
                    if hasattr(self, "attenuation_method_combo"):
                        self.attenuation_method_combo.setCurrentIndex(
                            config["method_index"]
                        )

                if "enabled" in config:
                    self.apply_attenuation_to_grid = config["enabled"]
                    if hasattr(self, "apply_attenuation_check"):
                        self.apply_attenuation_check.setChecked(
                            self.apply_attenuation_to_grid
                        )
                    # Actualizar label de estado
                    if hasattr(self, "calibration_status_label"):
                        self.calibration_status_label.setText(
                            f"Calibración: {'  Activa' if self.apply_attenuation_to_grid else 'Inactiva'}"
                        )

                if "threshold" in config:
                    self.calibration_threshold = config["threshold"]
                    if hasattr(self, "calib_threshold_slider"):
                        self.calib_threshold_slider.setValue(
                            int(self.calibration_threshold)
                        )
                        self.calib_threshold_input.setText(
                            f"{self.calibration_threshold:.1f}"
                        )

                if "flip_x" in config:
                    self.calibration_flip_x = config["flip_x"]
                    if hasattr(self, "calib_flip_x_checkbox"):
                        self.calib_flip_x_checkbox.setChecked(self.calibration_flip_x)

                if "flip_y" in config:
                    self.calibration_flip_y = config["flip_y"]
                    if hasattr(self, "calib_flip_y_checkbox"):
                        self.calib_flip_y_checkbox.setChecked(self.calibration_flip_y)

                if hasattr(self, "system_console"):
                    self.log_to_console("Configuración de calibración cargada", "INFO")

        except Exception as e:
            if hasattr(self, "system_console"):
                self.log_to_console(f"Error al cargar calibración: {str(e)}", "ERROR")
            else:
                print(f"Error al cargar calibración: {str(e)}")



    def toggle_calibration_flip_x(self, state):
        """Activa/desactiva el flip horizontal de la matriz de calibración."""
        self.calibration_flip_x = bool(state)
        self.save_calibration_data()
        self.log_to_console(
            f"🔄 Flip X de calibración: {'  Activo' if self.calibration_flip_x else '✗ Inactivo'}",
            "INFO",
        )
        if hasattr(self, "update_calibration_preview"):
            self.update_calibration_preview()



    def toggle_calibration_flip_y(self, state):
        """Activa/desactiva el flip vertical de la matriz de calibración."""
        self.calibration_flip_y = bool(state)
        self.save_calibration_data()
        self.log_to_console(
            f"🔄 Flip Y de calibración: {'  Activo' if self.calibration_flip_y else '✗ Inactivo'}",
            "INFO",
        )
        if hasattr(self, "update_calibration_preview"):
            self.update_calibration_preview()



    def get_calibration_matrix_with_flips(self):
        """
        Obtiene la matriz de calibración con los flips aplicados según la configuración.

        Returns:
            numpy.ndarray: Matriz de calibración con flips aplicados, o None si no hay matriz
        """
        if self.attenuation_matrix is None:
            return None

        matrix = self.attenuation_matrix.copy()

        # Aplicar flip horizontal (eje X) si está activo
        if self.calibration_flip_x:
            matrix = np.fliplr(matrix)  # Flip left-right

        # Aplicar flip vertical (eje Y) si está activo
        if self.calibration_flip_y:
            matrix = np.flipud(matrix)  # Flip up-down

        return matrix



    def update_calibration_monitor(self):
        """
        Actualiza el monitor de calibración en tiempo real con el estado actual
        de todos los efectos y parámetros de calibración.
        """
        try:
            # ═══════════════════════════════════════════════════════════════════
            # ESTADO DE CALIBRACIÓN
            # ═══════════════════════════════════════════════════════════════════
            if (
                hasattr(self, "attenuation_matrix")
                and self.attenuation_matrix is not None
            ):
                matrix_shape = self.attenuation_matrix.shape
                self.calib_status_label.setText(
                    f"✅ Calibración cargada ({matrix_shape[1]}×{matrix_shape[0]} px)"
                )
                self.calib_status_label.setStyleSheet(
                    "font-size: 10px; color: #51CF66;"
                )
            else:
                self.calib_status_label.setText("❌ Sin calibración cargada")
                self.calib_status_label.setStyleSheet(
                    "font-size: 10px; color: #FF6B6B;"
                )

            # Estado de aplicación
            if (
                hasattr(self, "apply_attenuation_to_grid")
                and self.apply_attenuation_to_grid
            ):
                self.calib_apply_status_label.setText("✅ Aplicación: ACTIVA")
                self.calib_apply_status_label.setStyleSheet(
                    "font-size: 10px; color: #51CF66;"
                )
            else:
                self.calib_apply_status_label.setText("⚪ Aplicación: Inactiva")
                self.calib_apply_status_label.setStyleSheet(
                    "font-size: 10px; color: #888888;"
                )

            # ═══════════════════════════════════════════════════════════════════
            # PARÁMETROS DE ATENUACIÓN
            # ═══════════════════════════════════════════════════════════════════
            if hasattr(self, "calibration_threshold"):
                self.atten_threshold_label.setText(
                    f"  Threshold: {self.calibration_threshold:.1f}%"
                )
            else:
                self.atten_threshold_label.setText("  Threshold: No configurado")

            if (
                hasattr(self, "attenuation_matrix")
                and self.attenuation_matrix is not None
            ):
                min_val = self.attenuation_matrix.min()
                max_val = self.attenuation_matrix.max()
                self.atten_min_label.setText(f"  Valor mínimo: {min_val:.3f}")
                self.atten_max_label.setText(f"  Valor máximo: {max_val:.3f}")
            else:
                self.atten_min_label.setText("  Valor mínimo: -")
                self.atten_max_label.setText("  Valor máximo: -")

            # ═══════════════════════════════════════════════════════════════════
            # EFECTOS ACTIVOS
            # ═══════════════════════════════════════════════════════════════════
            if hasattr(self, "sigma"):
                if self.sigma > 0:
                    self.effect_sigma_label.setText(
                        f"  Sigma (Blur): ✅ {self.sigma:.2f}"
                    )
                    self.effect_sigma_label.setStyleSheet(
                        "font-size: 10px; color: #51CF66;"
                    )
                else:
                    self.effect_sigma_label.setText(f"  Sigma (Blur): ⚪ Desactivado")
                    self.effect_sigma_label.setStyleSheet(
                        "font-size: 10px; color: #888888;"
                    )

            if hasattr(self, "downscale_factor"):
                if self.downscale_factor != 1.0:
                    self.effect_downscale_label.setText(
                        f"  Downscaling: ✅ {self.downscale_factor:.2f}x"
                    )
                    self.effect_downscale_label.setStyleSheet(
                        "font-size: 10px; color: #51CF66;"
                    )
                else:
                    self.effect_downscale_label.setText(
                        f"  Downscaling: ⚪ Sin reducción"
                    )
                    self.effect_downscale_label.setStyleSheet(
                        "font-size: 10px; color: #888888;"
                    )

            if hasattr(self, "brightness"):
                if self.brightness != 100:
                    self.effect_brightness_label.setText(
                        f"  Brillo: ✅ {self.brightness}%"
                    )
                    self.effect_brightness_label.setStyleSheet(
                        "font-size: 10px; color: #51CF66;"
                    )
                else:
                    self.effect_brightness_label.setText(
                        f"  Brillo: ⚪ 100% (sin ajuste)"
                    )
                    self.effect_brightness_label.setStyleSheet(
                        "font-size: 10px; color: #888888;"
                    )

            if hasattr(self, "binary_mode_enabled"):
                if self.binary_mode_enabled:
                    threshold = (
                        self.binary_threshold
                        if hasattr(self, "binary_threshold")
                        else 50
                    )
                    self.effect_binary_label.setText(
                        f"Modo Binario: Activo (Th: {threshold:.0f})"
                    )
                    self.effect_binary_label.setStyleSheet(
                        "font-size: 10px; color: #51CF66;"
                    )
                else:
                    self.effect_binary_label.setText(f"Modo Binario: Desactivado")
                    self.effect_binary_label.setStyleSheet(
                        "font-size: 10px; color: #888888;"
                    )

            if hasattr(self, "invert_projection"):
                if self.invert_projection:
                    self.effect_invert_label.setText(f"Inversión: Activa")
                    self.effect_invert_label.setStyleSheet(
                        "font-size: 10px; color: #51CF66;"
                    )
                else:
                    self.effect_invert_label.setText(f"Inversión: Desactivada")
                    self.effect_invert_label.setStyleSheet(
                        "font-size: 10px; color: #888888;"
                    )

            self.log_to_console(" Monitor de calibración actualizado", "INFO")

        except Exception as e:
            self.log_to_console(f" Error al actualizar monitor: {str(e)}", "ERROR")



    def update_calibration_preview(self, show_mode="split"):
        """
        Actualiza el preview de calibración mostrando antes/después.

        Args:
            show_mode: 'before', 'after', o 'split' (lado a lado)
        """
        try:
            if not hasattr(self, "calib_preview_figure"):
                return

            # Actualizar valor del slider
            if hasattr(self, "calib_preview_strength_slider"):
                strength = self.calib_preview_strength_slider.value()
                self.calib_preview_strength_value.setText(f"{strength}%")
            else:
                strength = 100

            self.calib_preview_figure.clear()

            # Verificar si hay imagen y calibración disponible
            if self.pattern is None:
                ax = self.calib_preview_figure.add_subplot(111)
                ax.text(
                    0.5,
                    0.5,
                    "Cargue una imagen\npara ver preview",
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="gray",
                )
                ax.axis("off")
                self.calib_preview_canvas.draw()
                return

            if (
                not hasattr(self, "attenuation_matrix")
                or self.attenuation_matrix is None
            ):
                ax = self.calib_preview_figure.add_subplot(111)
                ax.text(
                    0.5,
                    0.5,
                    "Genere una matriz\nde calibración",
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="gray",
                )
                ax.axis("off")
                self.calib_preview_canvas.draw()
                return

            # Obtener región central de la imagen para preview (más rápido)
            h, w = self.pattern.shape[:2]
            center_h, center_w = h // 2, w // 2
            size = min(200, h // 2, w // 2)

            y1, y2 = center_h - size, center_h + size
            x1, x2 = center_w - size, center_w + size

            sample = self.pattern[y1:y2, x1:x2].copy()

            # Obtener matriz con flips aplicados
            calibration_matrix = self.get_calibration_matrix_with_flips()

            # Aplicar calibración con la intensidad del slider
            if sample.shape[:2] == calibration_matrix.shape[:2]:
                # Tamaños coinciden - aplicar directamente
                calibrated = sample.copy()
            else:
                # Redimensionar matriz al tamaño de la muestra
                import cv2

                matrix_resized = cv2.resize(
                    calibration_matrix[y1:y2, x1:x2],
                    (sample.shape[1], sample.shape[0]),
                    interpolation=cv2.INTER_LINEAR,
                )
                calibrated = sample.copy()

            # Aplicar calibración con strength ajustable
            strength_factor = strength / 100.0
            if sample.shape[:2] == calibration_matrix.shape[:2]:
                matrix_to_use = calibration_matrix[y1:y2, x1:x2]
            else:
                matrix_to_use = matrix_resized

            adjusted_matrix = 1.0 + (matrix_to_use - 1.0) * strength_factor
            calibrated = np.clip(sample * adjusted_matrix, 0, 1.0)

            # Mostrar según el modo
            if show_mode == "before":
                ax = self.calib_preview_figure.add_subplot(111)
                ax.imshow(sample, cmap="gray", vmin=0, vmax=1)
                ax.set_title("Original (Sin Calibración)", fontsize=9)
                ax.axis("off")
            elif show_mode == "after":
                ax = self.calib_preview_figure.add_subplot(111)
                ax.imshow(calibrated, cmap="gray", vmin=0, vmax=1)
                ax.set_title(f"Calibrado ({strength}%)", fontsize=9)
                ax.axis("off")
            else:  # split
                ax1 = self.calib_preview_figure.add_subplot(121)
                ax1.imshow(sample, cmap="gray", vmin=0, vmax=1)
                ax1.set_title("Original", fontsize=8)
                ax1.axis("off")

                ax2 = self.calib_preview_figure.add_subplot(122)
                ax2.imshow(calibrated, cmap="gray", vmin=0, vmax=1)
                ax2.set_title(f"Calibrado {strength}%", fontsize=8)
                ax2.axis("off")

            self.calib_preview_figure.tight_layout(pad=0.5)
            self.calib_preview_canvas.draw()

        except Exception as e:
            self.log_to_console(
                f" Error en preview de calibración: {str(e)}", "ERROR"
            )
            import traceback

            traceback.print_exc()



    def generate_attenuation_matrix(self):
        """Genera la matriz de compensación basada en el análisis de intensidad."""
        if self.calibration_grayscale is None:
            QMessageBox.warning(
                self, "Advertencia", "No hay imagen disponible para generar matriz"
            )
            return

        # Convertir a intensidades normalizadas (0-1)
        intensity = self.calibration_grayscale.astype(float) / 255.0

        # Obtener método seleccionado
        method_text = self.attenuation_method_combo.currentText()

        if "Inversión Normalizada" in method_text:
            # Método recomendado: inversión con normalización
            # Zonas oscuras reciben más corrección, zonas claras menos
            max_intensity = np.max(intensity)
            if max_intensity > 0:
                self.attenuation_matrix = max_intensity / (
                    intensity + 0.01
                )  # +0.01 para evitar división por 0
                # Normalizar al rango [1, max_correction]
                self.attenuation_matrix = np.clip(self.attenuation_matrix, 1.0, 5.0)
            else:
                self.attenuation_matrix = np.ones_like(intensity)

        elif "Inversión Simple" in method_text:
            # Inversión directa
            self.attenuation_matrix = 1.0 / (intensity + 0.01)
            self.attenuation_matrix = np.clip(self.attenuation_matrix, 0.5, 2.0)

        elif "Ecualizador Adaptativo" in method_text:
            # Ecualización basada en desviación del promedio
            mean_intensity = np.mean(intensity)
            deviation = mean_intensity - intensity
            self.attenuation_matrix = 1.0 + (deviation * 2.0)
            self.attenuation_matrix = np.clip(self.attenuation_matrix, 0.5, 2.0)

        else:  # "Compensación Proporcional"
            # Corrección proporcional a la desviación
            target_intensity = np.percentile(
                intensity, 95
            )  # Usar percentil 95 como referencia
            self.attenuation_matrix = target_intensity / (intensity + 0.01)
            self.attenuation_matrix = np.clip(self.attenuation_matrix, 0.8, 1.5)

        # Habilitar controles
        self.apply_attenuation_check.setEnabled(True)
        self.preview_attenuation_button.setEnabled(True)
        self.save_attenuation_button.setEnabled(True)

        # Actualizar visualización
        self.update_attenuation_preview()

        # Actualizar estado
        matrix_min = np.min(self.attenuation_matrix)
        matrix_max = np.max(self.attenuation_matrix)
        self.matrix_status_label.setText(
            f"Estado:   Matriz generada ({self.attenuation_matrix.shape[0]}×{self.attenuation_matrix.shape[1]})"
        )
        self.matrix_range_label.setText(f"Rango: {matrix_min:.2f} - {matrix_max:.2f}")

        # Guardar calibración automáticamente
        self.save_calibration_data()

        # Actualizar monitor de calibración y preview
        if hasattr(self, "update_calibration_monitor"):
            self.update_calibration_monitor()
        if hasattr(self, "update_calibration_preview"):
            self.update_calibration_preview(show_mode="split")

        QMessageBox.information(
            self,
            "Éxito",
            f"Matriz de atenuación generada exitosamente.\n\n"
            f"Dimensiones: {self.attenuation_matrix.shape[0]}×{self.attenuation_matrix.shape[1]}\n"
            f"Rango de corrección: {matrix_min:.2f}x - {matrix_max:.2f}x",
        )



    def update_attenuation_preview(self):
        """Actualiza la visualización de la matriz de atenuación."""
        if self.attenuation_matrix is None:
            return

        # Obtener intensidad de corrección
        strength = self.attenuation_strength_slider.value()
        self.attenuation_strength_label.setText(f"{strength}%")
        self.attenuation_strength = float(strength)

        # Obtener matriz con flips aplicados
        calibration_matrix = self.get_calibration_matrix_with_flips()

        # Aplicar intensidad (interpolar entre sin corrección [1.0] y corrección completa)
        strength_factor = strength / 100.0
        adjusted_matrix = 1.0 + (calibration_matrix - 1.0) * strength_factor

        # Limpiar figura completa para evitar colorbar duplicados
        self.attenuation_figure.clear()
        self.attenuation_ax = self.attenuation_figure.add_subplot(111)

        im = self.attenuation_ax.imshow(
            adjusted_matrix, cmap="viridis", interpolation="bilinear"
        )

        # Colorbar (solo una vez)
        cbar = self.attenuation_figure.colorbar(
            im, ax=self.attenuation_ax, orientation="vertical", pad=0.02
        )
        cbar.set_label(
            "Factor de Corrección (×)",
            rotation=270,
            labelpad=20,
            color="#E0E0E0" if self.dark_mode else "#000000",
        )
        cbar.ax.tick_params(colors="#E0E0E0" if self.dark_mode else "#000000")

        self.attenuation_ax.set_title(
            "Matriz de Compensación de Uniformidad",
            color="#E0E0E0" if self.dark_mode else "#000000",
            fontsize=12,
            pad=10,
        )
        self.attenuation_ax.axis("off")

        self.attenuation_figure.tight_layout()
        self.attenuation_canvas.draw()



    def preview_attenuation_effect(self):
        """Previsualiza el efecto de la matriz de atenuación aplicada."""
        if self.attenuation_matrix is None or self.calibration_image is None:
            QMessageBox.warning(
                self,
                "Advertencia",
                "Necesita generar la matriz y tener una imagen cargada",
            )
            return

        # Convertir imagen a escala de grises si es necesario
        if len(self.calibration_image.shape) == 3:
            gray = cv2.cvtColor(self.calibration_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = self.calibration_image.copy()

        # Obtener matriz con flips aplicados
        calibration_matrix = self.get_calibration_matrix_with_flips()

        # Redimensionar matriz si es necesario
        if calibration_matrix.shape != gray.shape:
            from scipy.ndimage import zoom

            zoom_factors = (
                gray.shape[0] / calibration_matrix.shape[0],
                gray.shape[1] / calibration_matrix.shape[1],
            )
            attenuation_resized = zoom(calibration_matrix, zoom_factors, order=1)
        else:
            attenuation_resized = calibration_matrix

        # Aplicar matriz con intensidad ajustada
        strength_factor = self.attenuation_strength / 100.0
        adjusted_matrix = 1.0 + (attenuation_resized - 1.0) * strength_factor

        # Aplicar corrección
        corrected = gray.astype(float) * adjusted_matrix
        corrected = np.clip(corrected, 0, 255).astype(np.uint8)

        # Crear ventana de comparación
        comparison_dialog = QDialog(self)
        comparison_dialog.setWindowTitle("Comparación: Original vs Corregida")
        comparison_dialog.resize(1000, 500)

        layout = QVBoxLayout(comparison_dialog)

        # Canvas de comparación
        fig = Figure(facecolor="#121212" if self.dark_mode else "#FFFFFF")
        canvas = FigureCanvas(fig)

        # Subplot 1: Original
        ax1 = fig.add_subplot(1, 2, 1)
        ax1.imshow(gray, cmap="gray", vmin=0, vmax=255)
        ax1.set_title("Original", color="#E0E0E0" if self.dark_mode else "#000000")
        ax1.axis("off")

        # Subplot 2: Corregida
        ax2 = fig.add_subplot(1, 2, 2)
        ax2.imshow(corrected, cmap="gray", vmin=0, vmax=255)
        ax2.set_title(
            "Con Matriz de Atenuación", color="#E0E0E0" if self.dark_mode else "#000000"
        )
        ax2.axis("off")

        fig.tight_layout()
        canvas.draw()

        layout.addWidget(canvas)

        # Estadísticas
        stats_label = QLabel()
        orig_mean = np.mean(gray)
        corr_mean = np.mean(corrected)
        orig_std = np.std(gray)
        corr_std = np.std(corrected)

        stats_text = (
            f"<b>Estadísticas:</b><br>"
            f"Original - Media: {orig_mean:.1f}, Desv.Est: {orig_std:.1f}<br>"
            f"Corregida - Media: {corr_mean:.1f}, Desv.Est: {corr_std:.1f}<br>"
            f"<b>Mejora en uniformidad: {((orig_std - corr_std) / orig_std * 100):.1f}%</b>"
        )
        stats_label.setText(stats_text)
        layout.addWidget(stats_label)

        comparison_dialog.exec_()



    def toggle_attenuation_application(self, state):
        """Activa/desactiva la aplicación de la matriz al grid de proyección."""
        self.apply_attenuation_to_grid = bool(state)

        # Actualizar label de estado
        if hasattr(self, "calibration_status_label"):
            self.calibration_status_label.setText(
                f"Calibración: {'  Activa' if self.apply_attenuation_to_grid else 'Inactiva'}"
            )

        # Guardar estado
        self.save_calibration_data()

        if self.apply_attenuation_to_grid and self.attenuation_matrix is not None:
            QMessageBox.information(
                self,
                "Información",
                "La matriz de atenuación se aplicará automáticamente\n"
                "al grid de proyección para compensar la uniformidad.",
            )

        # Actualizar grid si está activo
        if (
            self.grid_view_active
            and hasattr(self, "grid_generated")
            and self.grid_generated
        ):
            self.display_grid()

        # Actualizar monitor de calibración y preview
        if hasattr(self, "update_calibration_monitor"):
            self.update_calibration_monitor()
        if hasattr(self, "update_calibration_preview"):
            self.update_calibration_preview(show_mode="split")



    def save_attenuation_matrix(self):
        """Guarda la matriz de atenuación en un archivo."""
        if self.attenuation_matrix is None:
            QMessageBox.warning(self, "Advertencia", "No hay matriz para guardar")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Matriz de Atenuación",
            "attenuation_matrix.npy",
            "NumPy Array (*.npy);;CSV File (*.csv)",
        )

        if file_path:
            try:
                if file_path.endswith(".npy"):
                    np.save(file_path, self.attenuation_matrix)
                else:
                    np.savetxt(
                        file_path, self.attenuation_matrix, delimiter=",", fmt="%.6f"
                    )

                QMessageBox.information(
                    self, "Éxito", f"Matriz guardada exitosamente en:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Error al guardar matriz:\n{str(e)}"
                )



    def load_attenuation_matrix(self):
        """Carga una matriz de atenuación desde un archivo."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Cargar Matriz de Atenuación",
            "",
            "NumPy Array (*.npy);;CSV File (*.csv);;All Files (*)",
        )

        if file_path:
            try:
                if file_path.endswith(".npy"):
                    self.attenuation_matrix = np.load(file_path)
                else:
                    self.attenuation_matrix = np.loadtxt(file_path, delimiter=",")

                # Habilitar controles
                self.apply_attenuation_check.setEnabled(True)
                self.preview_attenuation_button.setEnabled(True)
                self.save_attenuation_button.setEnabled(True)

                # Actualizar visualización
                self.update_attenuation_preview()

                # Actualizar estado
                matrix_min = np.min(self.attenuation_matrix)
                matrix_max = np.max(self.attenuation_matrix)
                self.matrix_status_label.setText(
                    f"Estado: Matriz cargada ({self.attenuation_matrix.shape[0]}×{self.attenuation_matrix.shape[1]})"
                )
                self.matrix_range_label.setText(
                    f"Rango: {matrix_min:.2f} - {matrix_max:.2f}"
                )

                QMessageBox.information(
                    self,
                    "Éxito",
                    f"Matriz cargada exitosamente.\n\n"
                    f"Dimensiones: {self.attenuation_matrix.shape[0]}×{self.attenuation_matrix.shape[1]}",
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Error al cargar matriz:\n{str(e)}"
                )


