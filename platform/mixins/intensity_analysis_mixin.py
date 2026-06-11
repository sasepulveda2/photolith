"""
Mixin de analisis de intensidad.

Carga de imagenes de calibracion, analisis de brillo por zonas/pixeles,
estadisticas de uniformidad y previsualizacion de umbrales binarios.
"""
from matplotlib.backends.backend_qtagg import FigureCanvas
import os

import cv2
from matplotlib.figure import Figure
import numpy as np

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QVBoxLayout


class IntensityAnalysisMixin:
    """Analisis de intensidad y uniformidad de brillo."""

    def load_calibration_image(self):
        """Carga una imagen estática para calibración."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Cargar Imagen de Calibración",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)",
        )

        if file_path:
            try:
                # Cargar imagen
                img = cv2.imread(file_path)
                if img is None:
                    raise Exception("No se pudo leer la imagen")

                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                self.calibration_image = img_rgb

                # Generar versión en escala de grises
                self.calibration_grayscale = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                # Actualizar status
                self.calib_image_status.setText(f"     {os.path.basename(file_path)}")
                self.calib_image_status.setStyleSheet(
                    "font-size: 11px; color: #00CC00; margin-left: 40px;"
                )

                # Mostrar en vista previa pestaña 1
                self.calib_preview_ax.clear()
                self.calib_preview_ax.imshow(img_rgb)
                self.calib_preview_ax.axis("off")
                self.calib_preview_canvas.draw()

                # Actualizar vista de escala de grises en pestaña 2
                if hasattr(self, "gray_preview_ax"):
                    self.update_grayscale_preview()

                # Habilitar botones de análisis
                if hasattr(self, "show_grayscale_button"):
                    self.show_grayscale_button.setEnabled(True)
                    self.analyze_intensity_button.setEnabled(True)
                    self.preview_threshold_button.setEnabled(True)
                    self.generate_attenuation_button.setEnabled(True)

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error al cargar imagen:\n{str(e)}")



    def toggle_mirror_preview(self):
        """Alterna el modo espejo en la vista previa."""
        self.update_grayscale_preview()



    def update_grayscale_preview(self):
        """Actualiza la vista previa en escala de grises."""
        if self.calibration_grayscale is None:
            return

        # Aplicar espejo si está activo
        display_image = self.calibration_grayscale.copy()
        if (
            hasattr(self, "mirror_preview_button")
            and self.mirror_preview_button.isChecked()
        ):
            display_image = cv2.flip(display_image, 1)

        self.gray_preview_ax.clear()
        self.gray_preview_ax.imshow(display_image, cmap="gray", vmin=0, vmax=255)
        self.gray_preview_ax.set_title(
            "Vista en Escala de Grises",
            color="#E0E0E0" if self.dark_mode else "#000000",
            fontsize=11,
        )
        self.gray_preview_ax.axis("off")
        self.gray_preview_canvas.draw()



    def show_grayscale_fullscreen(self):
        """Muestra la imagen en escala de grises en pantalla completa."""
        if self.calibration_grayscale is None:
            QMessageBox.warning(
                self, "Advertencia", "No hay imagen disponible para mostrar"
            )
            return

        # Crear ventana de proyección para escala de grises
        from PyQt5.QtWidgets import QDialog
        from PyQt5.QtCore import Qt

        fullscreen_dialog = QDialog(self)
        fullscreen_dialog.setWindowTitle(
            "Visualización en Escala de Grises - Calibración"
        )
        fullscreen_dialog.setWindowFlags(
            Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint
        )

        layout = QVBoxLayout(fullscreen_dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        # Canvas para mostrar escala de grises
        fig = Figure(facecolor="black")
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor("black")

        # Mostrar imagen en escala de grises
        ax.imshow(self.calibration_grayscale, cmap="gray", vmin=0, vmax=255)
        ax.axis("off")
        fig.tight_layout(pad=0)
        canvas.draw()

        layout.addWidget(canvas)

        # Mostrar en pantalla completa o maximizado
        fullscreen_dialog.showMaximized()
        fullscreen_dialog.exec_()



    def analyze_brightness_zones(self):
        """Analiza las zonas de brillo de la imagen."""
        if self.calibration_grayscale is None:
            QMessageBox.warning(
                self, "Advertencia", "No hay imagen disponible para analizar"
            )
            return

        # Obtener configuración de zonas
        zone_text = self.zone_grid_combo.currentText()

        if "Píxel a Píxel" in zone_text:
            self.analyze_pixel_by_pixel()
        else:
            # Extraer dimensiones del grid (ej: "4x4" de "4x4 (16 zonas)")
            grid_size = zone_text.split()[0]  # "4x4"
            rows, cols = map(int, grid_size.split("x"))
            self.analyze_zone_grid(rows, cols)



    def analyze_zone_grid(self, rows, cols):
        """Analiza la imagen dividida en una cuadrícula de zonas."""
        gray = self.calibration_grayscale
        h, w = gray.shape

        zone_h = h // rows
        zone_w = w // cols

        # Matriz para almacenar intensidades promedio de cada zona
        intensity_matrix = np.zeros((rows, cols))

        for i in range(rows):
            for j in range(cols):
                y_start = i * zone_h
                y_end = (i + 1) * zone_h if i < rows - 1 else h
                x_start = j * zone_w
                x_end = (j + 1) * zone_w if j < cols - 1 else w

                zone = gray[y_start:y_end, x_start:x_end]
                intensity_matrix[i, j] = np.mean(zone)

        # Convertir a porcentajes (0-100%)
        intensity_percentages = (intensity_matrix / 255.0) * 100.0

        # Guardar datos
        self.calibration_intensity_data = {
            "type": "grid",
            "rows": rows,
            "cols": cols,
            "intensities": intensity_percentages,
            "raw_matrix": intensity_matrix,
        }

        # Actualizar visualización
        self.update_intensity_analysis()

        # Calcular y mostrar estadísticas
        self.update_brightness_statistics(intensity_percentages)



    def analyze_pixel_by_pixel(self):
        """Analiza cada píxel individualmente."""
        gray = self.calibration_grayscale

        # Convertir a porcentajes
        intensity_percentages = (gray.astype(float) / 255.0) * 100.0

        # Guardar datos
        self.calibration_intensity_data = {
            "type": "pixel",
            "intensities": intensity_percentages,
            "raw_matrix": gray,
        }

        # Actualizar visualización
        self.update_intensity_analysis()

        # Calcular y mostrar estadísticas
        self.update_brightness_statistics(intensity_percentages)



    def update_intensity_analysis(self):
        """Actualiza la visualización del análisis de intensidad."""
        if self.calibration_intensity_data is None:
            return

        data = self.calibration_intensity_data
        intensities = data["intensities"]

        self.intensity_map_figure.clear()
        self.intensity_map_ax = self.intensity_map_figure.add_subplot(111)

        show_heatmap = self.show_heatmap_check.isChecked()
        show_percentages = self.show_percentages_check.isChecked()

        if show_heatmap:
            im = self.intensity_map_ax.imshow(
                intensities,
                cmap="hot",
                vmin=0,
                vmax=100,
                interpolation="nearest" if data["type"] == "grid" else "bilinear",
            )
            cbar = self.intensity_map_figure.colorbar(
                im, ax=self.intensity_map_ax, orientation="vertical", pad=0.02
            )
            cbar.set_label(
                "Intensidad (%)",
                rotation=270,
                labelpad=20,
                color="#E0E0E0" if self.dark_mode else "#000000",
            )
            cbar.ax.tick_params(colors="#E0E0E0" if self.dark_mode else "#000000")
        else:
            self.intensity_map_ax.imshow(intensities, cmap="gray", vmin=0, vmax=100)

        if show_percentages and data["type"] == "grid":
            rows, cols = data["rows"], data["cols"]

            for i in range(rows):
                for j in range(cols):
                    value = intensities[i, j]

                    text_color = "black" if value > 50 else "white"

                    self.intensity_map_ax.text(
                        j,
                        i,
                        f"{value:.1f}%",
                        ha="center",
                        va="center",
                        color=text_color,
                        fontsize=8,
                        weight="bold",
                    )

        self.intensity_map_ax.set_title(
            "Mapa de Intensidad de Brillo",
            color="#E0E0E0" if self.dark_mode else "#000000",
            fontsize=12,
            pad=10,
        )
        self.intensity_map_ax.axis("off")

        self.intensity_map_figure.tight_layout()
        self.intensity_map_canvas.draw()



    def update_brightness_statistics(self, intensities):
        """Actualiza las estadísticas de brillo y uniformidad."""
        avg = np.mean(intensities)
        min_val = np.min(intensities)
        max_val = np.max(intensities)
        std = np.std(intensities)

        # Actualizar labels
        self.brightness_avg_label.setText(f"Promedio: {avg:.1f}%")
        self.brightness_min_label.setText(f"Mínimo: {min_val:.1f}%")
        self.brightness_max_label.setText(f"Máximo: {max_val:.1f}%")
        self.brightness_std_label.setText(f"Desv. Est.: {std:.1f}%")

        # Calcular uniformidad (100% - coeficiente de variación)
        # Uniformidad alta = desviación baja
        if avg > 0:
            cv = (std / avg) * 100  # Coeficiente de variación
            uniformity = max(0, 100 - cv)
        else:
            uniformity = 0

        self.uniformity_indicator.setText(f"{uniformity:.1f}%")

        # Colorear según uniformidad
        if uniformity >= 90:
            color = "#00FF00"
            status = "  Excelente"
        elif uniformity >= 75:
            color = "#88FF00"
            status = "  Buena"
        elif uniformity >= 60:
            color = "#FFFF00"
            status = "⚠ Aceptable"
        elif uniformity >= 40:
            color = "#FF8800"
            status = "⚠ Baja"
        else:
            color = "#FF0000"
            status = "✗ Muy Baja"

        self.uniformity_indicator.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {color};"
        )
        self.uniformity_status.setText(status)
        self.uniformity_status.setStyleSheet(f"font-size: 11px; color: {color};")



    def update_calibration_threshold_from_slider(self):
        """Actualiza el umbral de calibración desde el slider."""
        self.calibration_threshold = float(self.calib_threshold_slider.value())
        self.calib_threshold_input.setText(f"{self.calibration_threshold:.1f}")



    def update_calibration_threshold_from_input(self):
        """Actualiza el umbral de calibración desde el input."""
        try:
            value = float(self.calib_threshold_input.text())
            if 0 <= value <= 100:
                self.calibration_threshold = value
                self.calib_threshold_slider.setValue(int(round(value)))
            else:
                self.calib_threshold_input.setText(f"{self.calibration_threshold:.1f}")
        except ValueError:
            self.calib_threshold_input.setText(f"{self.calibration_threshold:.1f}")



    def preview_threshold_conversion(self):
        """Previsualiza la conversión binaria con el umbral actual."""
        if self.calibration_grayscale is None:
            QMessageBox.warning(self, "Advertencia", "No hay imagen disponible")
            return

        # Convertir a porcentajes
        intensity_percent = (self.calibration_grayscale.astype(float) / 255.0) * 100.0

        # Aplicar umbral
        binary_image = np.where(
            intensity_percent >= self.calibration_threshold, 255, 0
        ).astype(np.uint8)

        # Calcular estadísticas
        total_pixels = binary_image.size
        white_pixels = np.sum(binary_image == 255)
        black_pixels = np.sum(binary_image == 0)

        white_percent = (white_pixels / total_pixels) * 100
        black_percent = (black_pixels / total_pixels) * 100

        # Actualizar labels
        self.threshold_white_label.setText(f"Píxeles Blancos: {white_percent:.1f}%")
        self.threshold_black_label.setText(f"Píxeles Negros: {black_percent:.1f}%")

        # Visualizar
        self.threshold_preview_ax.clear()
        self.threshold_preview_ax.imshow(binary_image, cmap="gray", vmin=0, vmax=255)
        self.threshold_preview_ax.set_title(
            f"Conversión Binaria (Umbral: {self.calibration_threshold:.1f}%)",
            color="#E0E0E0" if self.dark_mode else "#000000",
            fontsize=11,
        )
        self.threshold_preview_ax.axis("off")
        self.threshold_preview_canvas.draw()


