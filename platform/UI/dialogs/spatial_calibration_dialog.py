"""
diálogo dedicado para la calibración espacial de la óptica.
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt
import math

from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.widgets import Cursor
from PyQt5.QtWidgets import QApplication
from constants import DARK_BG_PRIMARY

class SpatialCalibrationDialog(QDialog):
    def __init__(self, parent, image_data=None):
        super().__init__(parent)
        self.setWindowTitle("Calibración Espacial de Tamaños")
        self.resize(800, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)
        
        self.image_data = image_data
        
        self.spatial_line_start = None
        self.spatial_line_artist = None
        self.pixel_distance = 0.0
        self.mm_per_pixel = None
        
        self._build_ui()
        self._plot_image()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # ── canvas ─────────────────────────────────────────────────────────
        self.figure = Figure(facecolor=DARK_BG_PRIMARY)
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.figure.tight_layout()
        
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        # eventos
        self.canvas.mpl_connect("button_press_event", self.on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event", self.on_mouse_move)
        
        # cursor cruz (crosshair)
        self.cursor = Cursor(self.ax, useblit=True, color='cyan', linewidth=1)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas, stretch=1)
        
        # ── panel inferior ──────────────────────────────────────────────────
        bottom_layout = QHBoxLayout()
        
        self.lbl_pixels = QLabel("Distancia (px): 0.00")
        bottom_layout.addWidget(self.lbl_pixels)
        
        bottom_layout.addWidget(QLabel("Medida real (mm):"))
        self.input_mm = QLineEdit()
        self.input_mm.setPlaceholderText("Ej. 10.5")
        self.input_mm.textChanged.connect(self.calculate_scale)
        self.input_mm.setMaximumWidth(100)
        bottom_layout.addWidget(self.input_mm)
        
        self.lbl_result = QLabel("Escala: -")
        self.lbl_result.setStyleSheet("font-weight: bold; color: #00BFA5;")
        bottom_layout.addWidget(self.lbl_result)
        
        bottom_layout.addStretch()
        
        self.btn_save = QPushButton("💾 Guardar Calibración")
        self.btn_save.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_save)
        
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(bottom_layout)
        
    def _plot_image(self):
        if self.image_data is not None:
            self.ax.imshow(self.image_data, cmap='gray')
            self.ax.axis('off')
            self.canvas.draw()
            
    def on_mouse_press(self, event):
        # solo procesar si no está en modo pan o zoom
        if self.toolbar.mode != "":
            return
            
        if event.button == 1 and event.inaxes == self.ax:
            self.spatial_line_start = (event.xdata, event.ydata)
            if self.spatial_line_artist:
                self.spatial_line_artist.remove()
                
            self.spatial_line_artist = Line2D(
                [event.xdata, event.xdata], 
                [event.ydata, event.ydata], 
                color='red', linewidth=2, marker='+'
            )
            self.ax.add_line(self.spatial_line_artist)
            self.canvas.draw_idle()

    def on_mouse_move(self, event):
        if self.toolbar.mode != "":
            return
            
        if self.spatial_line_start and self.spatial_line_artist and event.inaxes == self.ax:
            x1, y1 = self.spatial_line_start
            x2, y2 = event.xdata, event.ydata
            
            # Snapping a 90 grados con Shift
            modifiers = QApplication.keyboardModifiers()
            if modifiers & Qt.ShiftModifier:
                dx = abs(x2 - x1)
                dy = abs(y2 - y1)
                if dx > dy:
                    y2 = y1  # horizontal
                else:
                    x2 = x1  # vertical
                    
            self.spatial_line_artist.set_data([x1, x2], [y1, y2])
            self.canvas.draw_idle()
            
            # act distance
            dist = math.sqrt((event.xdata - x1)**2 + (event.ydata - y1)**2)
            self.lbl_pixels.setText(f"Distancia (px): {dist:.2f}")

    def on_mouse_release(self, event):
        if self.toolbar.mode != "":
            return
            
        if event.button == 1 and self.spatial_line_start:
            x1, y1 = self.spatial_line_start
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
            
            self.pixel_distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
            self.lbl_pixels.setText(f"Distancia (px): {self.pixel_distance:.2f}")
            self.spatial_line_start = None
            self.calculate_scale()

    def calculate_scale(self):
        if self.pixel_distance < 1.0:
            return
            
        text = self.input_mm.text().replace(',', '.')
        try:
            val_mm = float(text)
            if val_mm > 0:
                self.mm_per_pixel = val_mm / self.pixel_distance
                self.lbl_result.setText(f"Escala: {self.mm_per_pixel:.5f} mm/px")
                return
        except ValueError:
            pass
            
        self.mm_per_pixel = None
        self.lbl_result.setText("Escala: -")
