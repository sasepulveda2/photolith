import sys
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter
from scipy.signal import convolve2d
from scipy.special import j1
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFileDialog,
    QSlider,
    QComboBox,
    QMessageBox,
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class LithographySimulator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador Óptico de Maggi V1.0")
        self.setGeometry(100, 100, 1400, 700)

        self.pattern = None
        self.real_image = None
        self.sigma = 2.0
        self.psf_type = "Gaussiana"
        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()
        export_layout = QHBoxLayout()

        # botones y controles
        self.load_button = QPushButton("📂 Cargar patrón")
        self.load_button.clicked.connect(self.load_pattern)

        self.load_real_button = QPushButton("🖼️ Cargar imagen real")
        self.load_real_button.clicked.connect(self.load_real_image)

        self.sigma_label = QLabel(f"Sigma/Radio (PSF): {self.sigma:.1f}")
        self.sigma_slider = QSlider(Qt.Horizontal)
        self.sigma_slider.setMinimum(1)
        self.sigma_slider.setMaximum(30)
        self.sigma_slider.setValue(int(self.sigma))
        self.sigma_slider.valueChanged.connect(self.update_sigma)

        self.psf_selector = QComboBox()
        self.psf_selector.addItems(["Gaussiana"])
        self.psf_selector.currentTextChanged.connect(self.update_psf_type)

        self.fourier_button = QPushButton("⚡ Ver espectro de Fourier")
        self.fourier_button.clicked.connect(self.show_fourier)

        # botón de volver (invisible hasta que se abra Fourier)
        self.back_button = QPushButton("↩ Volver")
        self.back_button.clicked.connect(self.go_back)
        self.back_button.setVisible(False)

        self.export_button = QPushButton("💾 Exportar intensidad")
        self.export_button.clicked.connect(self.export_intensity)

        self.calibrate_button = QPushButton("📏 Comparar con imagen real")
        self.calibrate_button.clicked.connect(self.compare_with_real)

        # hasta aquí controles
        control_layout.addWidget(self.load_button)
        control_layout.addWidget(self.load_real_button)
        control_layout.addWidget(self.psf_selector)
        control_layout.addWidget(self.sigma_label)
        control_layout.addWidget(self.sigma_slider)
        control_layout.addWidget(self.fourier_button)
        control_layout.addWidget(self.back_button)

        export_layout.addWidget(self.export_button)
        export_layout.addWidget(self.calibrate_button)

        self.figure = Figure(facecolor="#121212")
        self.canvas = FigureCanvas(self.figure)

        self.info_layout = QVBoxLayout()
        self.resolution_label = QLabel("Resolución: -")
        self.min_label = QLabel("Intensidad mínima: -")
        self.avg_label = QLabel("Intensidad promedio: -")
        self.max_label = QLabel("Intensidad máxima: -")
        self.info_layout.addWidget(self.resolution_label)
        self.info_layout.addWidget(self.min_label)
        self.info_layout.addWidget(self.avg_label)
        self.info_layout.addWidget(self.max_label)
        self.info_layout.addStretch()

        canvas_layout = QHBoxLayout()
        canvas_layout.addWidget(self.canvas, stretch=3)
        canvas_layout.addLayout(self.info_layout, stretch=1)

        main_layout.addLayout(control_layout)
        main_layout.addLayout(canvas_layout)
        main_layout.addLayout(export_layout)
        self.setLayout(main_layout)

        # lo tengo que separar en archivos, de nuevo
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #f0f0f0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
            }

            QPushButton {
                background-color: #1E1E1E;
                border: 1px solid #2E2E2E;
                border-radius: 8px;
                padding: 8px 12px;
                color: #E0E0E0;
            }
            QPushButton:hover {
                background-color: #2C2C2C;
                border: 1px solid #3E3E3E;
            }
            QPushButton:pressed {
                background-color: #3A3A3A;
            }

            QComboBox {
                background-color: #1E1E1E;
                border-radius: 6px;
                padding: 4px 8px;
            }

            QLabel {
                color: #f0f0f0;
            }

            QSlider::groove:horizontal {
                background: #2E2E2E;
                height: 6px;
                border-radius: 3px;
            }

            QSlider::handle:horizontal {
                background: #03DAC6;
                width: 14px;
                border-radius: 7px;
                margin: -4px 0;
            }

            QSlider::handle:horizontal:hover {
                background: #00BFA5;
            }

            QMessageBox {
                background-color: #121212;
                color: white;
            }
        """)

    # funciones
    def load_pattern(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar patrón", "", "Imágenes (*.png *.jpg *.bmp)"
        )
        if file_path:
            image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            self.pattern = image / 255.0
            self.simulate_optics()

    def load_real_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar imagen real", "", "Imágenes (*.png *.jpg *.bmp)"
        )
        if file_path:
            image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            self.real_image = image / 255.0
            QMessageBox.information(
                self, "Imagen cargada", "Imagen real cargada correctamente."
            )

    def update_sigma(self):
        self.sigma = self.sigma_slider.value()
        self.sigma_label.setText(f"Sigma/Radio (PSF): {self.sigma:.1f}")
        if self.pattern is not None:
            self.simulate_optics()

    def update_psf_type(self, text):
        self.psf_type = text
        if self.pattern is not None:
            self.simulate_optics()

    def simulate_optics(self):
        self.back_button.setVisible(False)
        self.fourier_button.setVisible(True)

        if self.psf_type == "Gaussiana":
            psf_result = gaussian_filter(self.pattern, sigma=self.sigma)
        elif self.psf_type == "Airy (difracción)":
            psf = self._generate_airy_psf(self.pattern.shape, self.sigma)
            psf_result = convolve2d(self.pattern, psf, mode="same")
        elif self.psf_type == "Movimiento lineal":
            psf = self._generate_motion_psf(self.sigma)
            psf_result = convolve2d(self.pattern, psf, mode="same")
        else:
            psf_result = self.pattern

        intensity_percentage = (psf_result / psf_result.max()) * 100
        self.last_intensity = intensity_percentage
        self.plot_results(self.pattern, psf_result, intensity_percentage)
        self.update_info_panel(intensity_percentage)

    def _generate_airy_psf(self, shape, radius):
        y, x = np.indices(shape)
        cy, cx = np.array(shape) / 2
        r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        r = np.maximum(r, 1e-6)
        airy = (2 * j1(r / radius) / (r / radius)) ** 2
        airy /= airy.sum()
        return airy

    def _generate_motion_psf(self, length):
        length = max(1, int(round(length)))
        psf = np.zeros((length, length))
        psf[length // 2, :] = 1
        psf /= psf.sum()
        return psf

    def plot_results(self, pattern, simulated, intensity_percentage):
        self.figure.clear()

        ax1 = self.figure.add_subplot(1, 2, 1)
        ax2 = self.figure.add_subplot(1, 2, 2)

        for ax in [ax1, ax2]:
            ax.set_facecolor("#121212")
            ax.tick_params(colors="white")
            ax.xaxis.label.set_color("white")
            ax.yaxis.label.set_color("white")
        ax1.imshow(pattern, cmap="gray")
        ax1.set_title("Patrón de entrada", color="white")
        ax1.set_xlabel("X")
        ax1.set_ylabel("Y")
        im = ax2.imshow(intensity_percentage, cmap="inferno")
        ax2.set_title(f"Mapa de intensidad ({self.psf_type})", color="white")
        ax2.set_xlabel("X")
        ax2.set_ylabel("Y")
        cbar = self.figure.colorbar(im, ax=ax2, label="Intensidad (%)")
        cbar.ax.set_facecolor("#121212")
        cbar.ax.yaxis.set_tick_params(color="white")
        cbar.ax.yaxis.label.set_color("white")
        cbar.outline.set_edgecolor("white")

        self.canvas.draw()

    def show_fourier(self):
        if self.pattern is None:
            QMessageBox.warning(self, "error", "Primero carga un patrón.")
            return

        fft_image = np.fft.fftshift(np.fft.fft2(self.pattern))
        magnitude_spectrum = np.log(np.abs(fft_image) + 1e-6)

        self.figure.clear()
        ax = self.figure.add_subplot(1, 1, 1)
        ax.set_facecolor("#121212")
        im = ax.imshow(magnitude_spectrum, cmap="plasma")
        ax.set_title("Espectro de Fourier (magnitud)", color="white")
        ax.set_xlabel("U")
        ax.set_ylabel("V")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")

        cbar = self.figure.colorbar(im, ax=ax)
        cbar.ax.set_facecolor("#121212")
        cbar.ax.yaxis.set_tick_params(color="white")
        cbar.ax.yaxis.label.set_color("white")
        cbar.outline.set_edgecolor("white")

        self.canvas.draw()

        self.back_button.setVisible(True)
        self.fourier_button.setVisible(False)

    def go_back(self):

        self.back_button.setVisible(False)
        self.fourier_button.setVisible(True)
        if self.pattern is not None:
            self.simulate_optics()
        else:
            self.figure.clear()
            self.canvas.draw()

    def export_intensity(self):
        if not hasattr(self, "last_intensity"):
            QMessageBox.warning(self, "error", "Primero genera una simulación.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Guardar mapa de intensidad", "", "NumPy (*.npy);;CSV (*.csv)"
        )

        if file_path:
            if file_path.endswith(".npy"):
                np.save(file_path, self.last_intensity)
            elif file_path.endswith(".csv"):
                np.savetxt(file_path, self.last_intensity, delimiter=",")
            QMessageBox.information(
                self, "Exportado", f"Archivo guardado en:\n{file_path}"
            )

    def compare_with_real(self):
        if self.real_image is None or not hasattr(self, "last_intensity"):
            QMessageBox.warning(
                self, "error", "Carga una imagen real y genera una simulación primero."
            )
            return

        simulated_resized = cv2.resize(
            self.last_intensity, (self.real_image.shape[1], self.real_image.shape[0])
        )
        diff = simulated_resized - (self.real_image * 100)
        rms_error = np.sqrt(np.mean(diff**2))

        self.figure.clear()
        ax1 = self.figure.add_subplot(1, 3, 1)
        ax2 = self.figure.add_subplot(1, 3, 2)
        ax3 = self.figure.add_subplot(1, 3, 3)
        for ax in [ax1, ax2, ax3]:
            ax.set_facecolor("#121212")

        ax1.imshow(self.real_image, cmap="gray")
        ax1.set_title("Imagen real", color="white")

        ax2.imshow(simulated_resized, cmap="inferno")
        ax2.set_title("Simulación", color="white")

        ax3.imshow(np.abs(diff), cmap="coolwarm")
        ax3.set_title(f"Diferencia (RMS={rms_error:.2f})", color="white")

        self.canvas.draw()
        self.update_info_panel(simulated_resized)

    # panel de data
    def update_info_panel(self, intensity_map):
        if intensity_map is not None:
            h, w = intensity_map.shape
            self.resolution_label.setText(f"Resolución: {w} × {h}")
            self.min_label.setText(f"Intensidad mínima: {intensity_map.min():.2f}")
            self.avg_label.setText(f"Intensidad promedio: {intensity_map.mean():.2f}")
            self.max_label.setText(f"Intensidad máxima: {intensity_map.max():.2f}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LithographySimulator()
    window.show()
    sys.exit(app.exec_())
