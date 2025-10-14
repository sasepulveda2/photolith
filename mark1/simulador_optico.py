import sys
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QSlider
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class LithographySimulator(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Simulador de Litografía Computacional")
        self.setGeometry(100, 100, 1000, 600)

        # Inicialización de datos
        self.pattern = None
        self.sigma = 2.0

        # Layout principal
        main_layout = QVBoxLayout()
        control_layout = QHBoxLayout()
        view_layout = QHBoxLayout()

        # Botones y sliders
        self.load_button = QPushButton("Cargar patrón")
        self.load_button.clicked.connect(self.load_pattern)

        self.sigma_label = QLabel(f"Sigma (PSF): {self.sigma:.1f}")
        self.sigma_slider = QSlider(Qt.Horizontal)
        self.sigma_slider.setMinimum(1)
        self.sigma_slider.setMaximum(30)
        self.sigma_slider.setValue(int(self.sigma))
        self.sigma_slider.valueChanged.connect(self.update_sigma)

        control_layout.addWidget(self.load_button)
        control_layout.addWidget(self.sigma_label)
        control_layout.addWidget(self.sigma_slider)

        # Gráficos
        self.figure = Figure()
        self.canvas = FigureCanvas(self.figure)
        view_layout.addWidget(self.canvas)

        # Unimos todo
        main_layout.addLayout(control_layout)
        main_layout.addLayout(view_layout)
        self.setLayout(main_layout)

    def load_pattern(self):
        """Carga una imagen de patrón"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar imagen", "", "Imágenes (*.png *.jpg *.bmp)")
        if file_path:
            image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            self.pattern = image / 255.0  # Normalizar
            self.simulate_optics()

    def update_sigma(self):
        """Actualiza el valor de sigma del filtro"""
        self.sigma = self.sigma_slider.value()
        self.sigma_label.setText(f"Sigma (PSF): {self.sigma:.1f}")
        if self.pattern is not None:
            self.simulate_optics()

    def simulate_optics(self):
        """Simula el desenfoque óptico (PSF gaussiana)"""
        simulated = gaussian_filter(self.pattern, sigma=self.sigma)
        intensity_percentage = (simulated / simulated.max()) * 100
        self.plot_results(self.pattern, simulated, intensity_percentage)

    def plot_results(self, pattern, simulated, intensity_percentage):
        """Muestra los resultados en la interfaz"""
        self.figure.clear()
        ax1 = self.figure.add_subplot(1, 2, 1)
        ax2 = self.figure.add_subplot(1, 2, 2)

        ax1.imshow(pattern, cmap='gray')
        ax1.set_title("Patrón de entrada")

        im = ax2.imshow(simulated, cmap='hot')
        ax2.set_title("Mapa de intensidad simulada")

        self.figure.colorbar(im, ax=ax2, label="Intensidad (%)")

        self.canvas.draw()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = LithographySimulator()
    window.show()
    sys.exit(app.exec_())
