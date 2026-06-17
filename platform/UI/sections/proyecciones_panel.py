"""
layout editor cam (hardware-aware).

entorno de composicion litografica que orquesta multiples proyecciones
y movimientos de motor. conoce los limites fisicos de la maquina,
la calibracion optica y el fov del proyector para generar trayectorias
de exposicion optimizadas
"""
import os
import cv2
import numpy as np
import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as mpatches
import matplotlib.transforms as mtransforms
import matplotlib.image as mpimg
from math import ceil

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QSplitter, QLineEdit, QFormLayout, QCheckBox, QFileDialog,
    QDoubleSpinBox, QSlider, QProgressBar, QListWidget, QListWidgetItem,
    QMessageBox, QScrollArea, QGroupBox, QSizePolicy, QDialog, QDialogButtonBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSlot

from UI.sections.cam_models import LayoutItem, MachineState
from UI.sections.cam_worker import CamWorker, compute_tiling, optimize_path


class ShapeDimensionDialog(QDialog):
    def __init__(self, parent=None, title="Dimensiones", is_circle=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        
        lay = QFormLayout(self)
        
        self.inp_w = QLineEdit("10.0")
        self.inp_h = QLineEdit("10.0")
        
        if is_circle:
            lay.addRow("Diametro X (mm):", self.inp_w)
            lay.addRow("Diametro Y (mm):", self.inp_h)
        else:
            lay.addRow("Ancho (mm):", self.inp_w)
            lay.addRow("Alto (mm):", self.inp_h)
            
        self.btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.        self.btn_box.accepted.connect(self.accept)
        self.btn_box.rejected.connect(self.reject)
        lay.addWidget(self.btn_box)

    def get_dimensions(self):
        try:
            w = float(self.inp_w.text().replace(',', '.'))
        except ValueError:
            w = 10.0
        try:
            h = float(self.inp_h.text().replace(',', '.'))
        except ValueError:
            h = 10.0
        return w, h




class ProyeccionesGUI(QWidget):
    def __init__(self, main_app=None, controller=None):
        super().__init__()
        self.main_app = main_app
        self.ctrl = controller

        # estado del layout
        self.items: list[LayoutItem] = []
        self.selected_item: LayoutItem | None = None
        self.task_queue = []

        # estado de interaccion del mouse
        self._dragging = False
        self._panning = False
        self._resizing = False
        self._drag_start = None
        self._item_start_pos = None
        self._item_start_size = None

        # tracking visual de proyeccion
        self._current_fov_pos = (0.0, 0.0)

        # worker asincrono
        self._worker: CamWorker | None = None

        # leer estado de la maquina
        self.machine = MachineState.from_app(main_app, controller)

        self._init_ui()

    # =========================================================================
    # interfaz de usuario
    # =========================================================================

    def _init_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)

        # --- zona izquierda: canvas matplotlib ---
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(4, 4, 4, 4)

        # barra superior
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        
        # barra de estado superior
        self.status_bar = QLabel("listo")
        top_bar.addWidget(self.status_bar)
        
        top_bar.addStretch()
        
        btn_home = QPushButton("Restaurar Vista")
        btn_home.clicked.connect(self._restore_view)
        top_bar.addWidget(btn_home)
        
        left_lay.addLayout(top_bar)

        # canvas matplotlib
        self.figure = Figure(facecolor="#121212")
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        left_lay.addWidget(self.canvas)

        # --- zona derecha: panel de control ---
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setMaximumWidth(420)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setSpacing(8)

        # seccion 1: datos del sistema
        rl.addWidget(self._build_system_data_section())

        # seccion 2: herramientas
        rl.addWidget(self._build_tools_section())

        # seccion 2.5: control directo proyector
        rl.addWidget(self._build_direct_projector_section())

        # seccion 3: propiedades del elemento
        rl.addWidget(self._build_properties_section())

        # seccion 4: tiling
        rl.addWidget(self._build_tiling_section())

        # seccion 5: ejecucion
        rl.addWidget(self._build_execution_section())

        rl.addStretch()
        right_scroll.setWidget(right)

        splitter.addWidget(left)
        splitter.addWidget(right_scroll)
        splitter.setSizes([720, 380])
        root.addWidget(splitter)

        # timer para el proyector
        from PyQt5.QtCore import QTimer
        self._fov_timer = QTimer(self)
        self._fov_timer.setSingleShot(True)
        self._fov_timer.timeout.connect(self._turn_off_projector)
        self._is_projecting = False

        # conectar eventos del canvas
        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
        self.canvas.mpl_connect("key_press_event", self._on_key_press)

        # dibujar entorno inicial
        self._draw_bed()

    # -- secciones del panel derecho --

    def _build_system_data_section(self):
        grp = QGroupBox("Datos del Sistema")
        lay = QVBoxLayout(grp)

        m = self.machine
        calib_txt = f"{m.mm_per_pixel:.5f} mm/px" if m.is_calibrated else "no calibrado"
        fov_txt = f"{m.fov_w_mm:.1f} x {m.fov_h_mm:.1f} mm ({m.fov_w_px}x{m.fov_h_px} px)" if m.is_calibrated else "desconocido"
        # dimensiones de la grilla editables
        grid_lay = QHBoxLayout()
        lbl_grid_x = QLabel("Grid X (mm):")
        self.inp_grid_x = QLineEdit(f"{m.bed_x_max_mm:.1f}")
        self.        self.inp_grid_x.editingFinished.connect(self._update_grid_dims)
        
        lbl_grid_y = QLabel("Grid Y (mm):")
        self.inp_grid_y = QLineEdit(f"{m.bed_y_max_mm:.1f}")
        self.        self.inp_grid_y.editingFinished.connect(self._update_grid_dims)
        
        grid_lay.addWidget(lbl_grid_x)
        grid_lay.addWidget(self.inp_grid_x)
        grid_lay.addWidget(lbl_grid_y)
        grid_lay.addWidget(self.inp_grid_y)
        lay.addLayout(grid_lay)

        grid_lay2 = QHBoxLayout()
        lbl_grid_spacing = QLabel("Espaciado Grilla (mm):")
        self.inp_grid_spacing = QLineEdit("5.0")
        self.        self.inp_grid_spacing.editingFinished.connect(self._redraw)
        grid_lay2.addWidget(lbl_grid_spacing)
        grid_lay2.addWidget(self.inp_grid_spacing)
        lay.addLayout(grid_lay2)

        for label_text in [
            f"Calibracion: {calib_txt}",
            f"FOV Proyector: {fov_txt}",
            f"Pasos Motor: 3200 steps = 0.5 mm ({int(3200/0.5)} steps/mm)",
            f"Conexion: {'conectado' if m.is_connected else 'desconectado'}",
        ]:
            lbl = QLabel(label_text)
            lbl.setWordWrap(True)
            lay.addWidget(lbl)

        return grp

    def _update_grid_dims(self):
        try:
            x_val = float(self.inp_grid_x.text().replace(',', '.'))
            y_val = float(self.inp_grid_y.text().replace(',', '.'))
            if x_val > 0 and y_val > 0:
                self.machine.bed_x_max_mm = x_val
                self.machine.bed_y_max_mm = y_val
                self._redraw()
        except ValueError:
            pass

    def _build_tools_section(self):
        grp = QGroupBox("Herramientas")
        lay = QVBoxLayout(grp)

        for text, slot in [
            ("Cargar Imagen", self._add_image),
            ("Ajustar a FOV", self._fit_to_fov),
            ("Duplicar Seleccionado", self._duplicate_selected),
            ("Eliminar Seleccionado", self._delete_selected),
        ]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            lay.addWidget(btn)

        shape_lay = QHBoxLayout()
        self.combo_shapes = QComboBox()
        self.combo_shapes.addItems(["Rectangulo", "Circulo", "Linea (mm)", "Linea (Pixeles)"])

        btn_add_shape = QPushButton("Anadir Figura")
        btn_add_shape.clicked.connect(self._add_selected_shape)
        
        shape_lay.addWidget(self.combo_shapes)
        shape_lay.addWidget(btn_add_shape)
        lay.addLayout(shape_lay)

        return grp

    def _build_direct_projector_section(self):
        grp = QGroupBox("Control Directo Proyector")
        lay = QVBoxLayout(grp)

        btn_proj_sel = QPushButton("Proyectar Seleccionado")
        btn_proj_sel.clicked.connect(self._project_selected_item)
        lay.addWidget(btn_proj_sel)

        self.btn_proj_fov = QPushButton("Alternar Proyector (Encender FOV / Apagar)")
        self.        self.btn_proj_fov.clicked.connect(self._toggle_projector)
        lay.addWidget(self.btn_proj_fov)

        return grp

    def _build_properties_section(self):
        grp = QGroupBox("Propiedades del Elemento")
        lay = QVBoxLayout(grp)

        self.lbl_name = QLabel("ningun elemento seleccionado")
        self.        lay.addWidget(self.lbl_name)

        form = QFormLayout()
        form.setContentsMargins(0, 6, 0, 0)
        form.setLabelAlignment(Qt.AlignRight)

        # todos los labels del form en color claro

        self.inp_x = QLineEdit()
        self.        self.inp_x.editingFinished.connect(self._apply_position_from_input)
        lbl_x = QLabel("X (mm):")
        form.addRow(lbl_x, self.inp_x)

        self.inp_y = QLineEdit()
        self.        self.inp_y.editingFinished.connect(self._apply_position_from_input)
        lbl_y = QLabel("Y (mm):")
        form.addRow(lbl_y, self.inp_y)

        self.inp_w = QLineEdit()
        self.        self.inp_w.editingFinished.connect(self._apply_size_from_input)
        lbl_w = QLabel("Ancho (mm):")
        form.addRow(lbl_w, self.inp_w)

        self.inp_h = QLineEdit()
        self.        self.inp_h.editingFinished.connect(self._apply_size_from_input)
        lbl_h = QLabel("Alto (mm):")
        form.addRow(lbl_h, self.inp_h)

        self.inp_px_w = QLineEdit()
        self.        self.inp_px_w.editingFinished.connect(self._apply_px_size_from_input)
        lbl_px_w = QLabel("Ancho (px):")
        form.addRow(lbl_px_w, self.inp_px_w)

        self.inp_px_h = QLineEdit()
        self.        self.inp_px_h.editingFinished.connect(self._apply_px_size_from_input)
        lbl_px_h = QLabel("Alto (px):")
        form.addRow(lbl_px_h, self.inp_px_h)

        lay.addLayout(form)
        
        self.chk_invert = QCheckBox("Invertir Colores")
        self.        self.chk_invert.toggled.connect(self._toggle_invert)
        self.chk_invert.setVisible(False)
        lay.addWidget(self.chk_invert)

        self.lbl_info = QLabel("")
        self.        self.lbl_info.setWordWrap(True)
        lay.addWidget(self.lbl_info)

        # rotacion
        rot_lay = QHBoxLayout()
        lbl_rot = QLabel("Rotacion:")
        self.slider_rot = QSlider(Qt.Horizontal)
        self.slider_rot.setRange(0, 360)
        self.slider_rot.setValue(0)
        self.        self.slider_rot.valueChanged.connect(self._on_rotation_changed)
        self.lbl_rot_val = QLabel("0 deg")
        self.        rot_lay.addWidget(lbl_rot)
        rot_lay.addWidget(self.slider_rot)
        rot_lay.addWidget(self.lbl_rot_val)
        lay.addLayout(rot_lay)

        # exposicion y delay
        form2 = QFormLayout()
        form2.setLabelAlignment(Qt.AlignRight)

        self.inp_exp = QDoubleSpinBox()
        self.inp_exp.setRange(0.1, 3600.0)
        self.inp_exp.setSingleStep(0.5)
        self.inp_exp.setValue(10.0)
        self.        lbl_exp = QLabel("Exposicion (s):")
        form2.addRow(lbl_exp, self.inp_exp)

        self.inp_delay = QDoubleSpinBox()
        self.inp_delay.setRange(0.0, 3600.0)
        self.inp_delay.setSingleStep(0.5)
        self.inp_delay.setValue(5.0)
        self.        lbl_delay = QLabel("Espera (s):")
        form2.addRow(lbl_delay, self.inp_delay)

        self.chk_lock = QCheckBox("Bloquear espera para todos")
        self.        self.chk_lock.setChecked(True)
        form2.addRow("", self.chk_lock)

        lay.addLayout(form2)
        return grp

    def _build_tiling_section(self):
        grp = QGroupBox("Auto-Tiling")
        lay = QVBoxLayout(grp)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.spin_overlap = QDoubleSpinBox()
        self.spin_overlap.setRange(0.0, 5.0)
        self.spin_overlap.setSingleStep(0.1)
        self.spin_overlap.setValue(0.0)
        self.spin_overlap.setSuffix(" mm")
        self.        lbl_ov = QLabel("Overlap:")
        form.addRow(lbl_ov, self.spin_overlap)
        lay.addLayout(form)

        self.lbl_tiling_info = QLabel("")
        self.        self.lbl_tiling_info.setWordWrap(True)
        lay.addWidget(self.lbl_tiling_info)

        return grp

    def _build_execution_section(self):
        grp = QGroupBox("Ejecucion")
        lay = QVBoxLayout(grp)
        lay.setSpacing(6)

        self.btn_generate = QPushButton("Generar Trayectoria")
        self.        self.btn_generate.clicked.connect(self._generate_trajectory)
        lay.addWidget(self.btn_generate)

        self.btn_simulate = QPushButton("Simular Recorrido")
        self.        self.btn_simulate.clicked.connect(self._simulate)
        self.btn_simulate.setEnabled(False)
        lay.addWidget(self.btn_simulate)

        self.btn_execute = QPushButton("Ejecutar en Maquina")
        self.        self.btn_execute.clicked.connect(self._execute)
        self.btn_execute.setEnabled(False)
        lay.addWidget(self.btn_execute)

        self.btn_home_motors = QPushButton("Ir al Origen")
        self.        self.btn_home_motors.clicked.connect(self._home_motors)
        lay.addWidget(self.btn_home_motors)

        self.btn_stop = QPushButton("Parar de Emergencia")
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white; font-weight: bold; border-radius: 6px; padding: 10px;")
        self.        self.btn_stop.clicked.connect(self._emergency_stop)
        self.btn_stop.setEnabled(False)
        lay.addWidget(self.btn_stop)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.        lay.addWidget(self.progress)

        self.lbl_exec_time = QLabel("Tiempo estimado: --")
        self.        lay.addWidget(self.lbl_exec_time)

        self.lbl_exec_status = QLabel("esperando...")
        self.        self.lbl_exec_status.setWordWrap(True)
        lay.addWidget(self.lbl_exec_status)

        self.task_list = QListWidget()
        self.task_list.setMaximumHeight(150)
        self.        lay.addWidget(self.task_list)

        return grp

    # =========================================================================
    # renderizado del canvas
    # =========================================================================

    def _draw_bed(self):
        """dibuja el espacio fisico (virtual bed) con la grilla y el fov."""
        self.ax.clear()
        self.ax.set_facecolor("#121212")

        m = self.machine
        
        # leer espaciado de grilla configurable
        spacing = 5.0
        try:
            if hasattr(self, "inp_grid_spacing"):
                s = float(self.inp_grid_spacing.text().replace(',', '.'))
                if s > 0:
                    spacing = s
        except ValueError:
            pass

        # grilla configurable
        for x in np.arange(0, m.bed_x_max_mm + spacing, spacing):
            self.ax.axvline(x=x, color="#333333", linewidth=0.8)
        for y in np.arange(0, m.bed_y_max_mm + spacing, spacing):
            self.ax.axhline(y=y, color="#333333", linewidth=0.8)

        # grilla subdividida fina (opcional)
        fine_spacing = spacing / 5.0
        if fine_spacing >= 1.0:
            for x in np.arange(0, m.bed_x_max_mm + fine_spacing, fine_spacing):
                self.ax.axvline(x=x, color="#1E1E1E", linewidth=0.4)
            for y in np.arange(0, m.bed_y_max_mm + fine_spacing, fine_spacing):
                self.ax.axhline(y=y, color="#1E1E1E", linewidth=0.4)

        # limite de motores (borde solido, gris claro sobrio)
        bed_rect = mpatches.Rectangle(
            (0, 0), m.bed_x_max_mm, m.bed_y_max_mm,
            linewidth=1.5, edgecolor="#555", facecolor="none", linestyle="-"
        )
        self.ax.add_patch(bed_rect)

        # fov del proyector (borde punteado rojo, muestra la posicion actual)
        if m.is_calibrated:
            fx, fy = self._current_fov_pos
            fov_rect = mpatches.Rectangle(
                (fx, fy), m.fov_w_mm, m.fov_h_mm,
                linewidth=1.5, edgecolor="#FF4444", facecolor="#FF4444",
                linestyle="--", alpha=0.25
            )
            self.ax.add_patch(fov_rect)
            self.ax.text(
                fx + m.fov_w_mm / 2, fy + m.fov_h_mm / 2,
                f"Proyeccion Actual\n{m.fov_w_mm:.1f}x{m.fov_h_mm:.1f} mm",
                ha="center", va="center", fontsize=8, color="#FF8888", alpha=0.8
            )

        # estetica
        self.ax.set_xlim(0, m.bed_x_max_mm)
        self.ax.set_ylim(m.bed_y_max_mm, 0)
        self.ax.set_aspect("equal")
        self._original_xlim = self.ax.get_xlim()
        self._original_ylim = self.ax.get_ylim()

        self.ax.set_xlabel("X (mm)", color="#E0E0E0", fontsize=11)
        self.ax.set_ylabel("Y (mm)", color="#E0E0E0", fontsize=11)
        self.ax.tick_params(colors="#E0E0E0", labelsize=9)
        for spine in self.ax.spines.values():
            spine.set_edgecolor("#555")

        self.canvas.draw()

    def _redraw(self):
        """redibuja el bed y todos los items con rotacion y gestos."""
        # guardar limites actuales del zoom
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        self._draw_bed()

        m = self.machine
        for item in self.items:
            is_sel = (item is self.selected_item)
            edge = "#5599CC" if is_sel else "#888"
            lw = 2 if is_sel else 0.8

            x, y, w, h = item.x_mm, item.y_mm, item.w_mm, item.h_mm
            cx, cy = x + w / 2, y + h / 2
            angle = item.rotation_deg

            # transformacion de rotacion centrada en el item
            rot = mtransforms.Affine2D().rotate_deg_around(cx, cy, -angle) + self.ax.transData

            if item.item_type == "image" and item.data is not None:
                self.ax.imshow(
                    item.data, extent=[x, x + w, y + h, y],
                    alpha=0.9, zorder=5,
                    transform=rot if angle != 0 else self.ax.transData
                )
                border = mpatches.Rectangle(
                    (x, y), w, h, lw=lw, edgecolor=edge,
                    facecolor="none", zorder=6, transform=rot
                )
                self.ax.add_patch(border)
            elif item.item_type == "circle":
                r = min(w, h) / 2
                circ = mpatches.Circle(
                    (cx, cy), r, lw=lw, edgecolor=edge,
                    facecolor="#FFFFFF", alpha=0.85, zorder=5
                )
                self.ax.add_patch(circ)
            else:
                rect = mpatches.Rectangle(
                    (x, y), w, h, lw=lw, edgecolor=edge,
                    facecolor="#FFFFFF", alpha=0.85, zorder=5,
                    transform=rot
                )
                self.ax.add_patch(rect)

            # indicador de tiling si excede el fov
            if m.is_calibrated and (w > m.fov_w_mm or h > m.fov_h_mm):
                overlap = self.spin_overlap.value()
                sx = max(0.1, m.fov_w_mm - overlap)
                sy = max(0.1, m.fov_h_mm - overlap)
                tx = max(1, int(ceil(w / sx)))
                ty = max(1, int(ceil(h / sy)))
                self.ax.text(
                    x + w, y, f"{tx}x{ty}",
                    ha="right", va="top", fontsize=7, color="#999",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="#1A1A1A", edgecolor="#333", alpha=0.8),
                    zorder=10
                )

            # handle de redimension (esquina inferior-derecha) si seleccionado
            if is_sel:
                handle_size = max(0.3, min(w, h) * 0.08)
                handle = mpatches.Rectangle(
                    (x + w - handle_size, y + h - handle_size),
                    handle_size, handle_size,
                    facecolor="#5599CC", edgecolor="none", zorder=12, alpha=0.8,
                    transform=rot
                )
                self.ax.add_patch(handle)

        # dibujar trayectoria si existe
        if self.task_queue:
            coords = [(t.target_x_mm, t.target_y_mm) for t in self.task_queue]
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            self.ax.plot(xs, ys, "o-", color="#666", markersize=2, linewidth=0.6, alpha=0.4, zorder=8)

        # restaurar zoom
        self.ax.set_xlim(xlim)
        self.ax.set_ylim(ylim)
        self.canvas.draw_idle()

    # =========================================================================
    # interaccion con el mouse
    # =========================================================================

    def _on_press(self, event):
        if event.inaxes != self.ax:
            return

        # boton central: pan
        if event.button == 2:
            self._panning = True
            self._drag_start = (event.xdata, event.ydata)
            self.canvas.setCursor(Qt.ClosedHandCursor)
            return

        # boton derecho: redimensionar item seleccionado
        if event.button == 3 and self.selected_item:
            self._resizing = True
            self._drag_start = (event.xdata, event.ydata)
            self._item_start_size = (self.selected_item.w_mm, self.selected_item.h_mm)
            self.canvas.setCursor(Qt.SizeFDiagCursor)
            return

        # boton izquierdo: seleccionar/arrastrar
        if event.button == 1:
            clicked = None
            for item in reversed(self.items):
                if item.contains_point(event.xdata, event.ydata):
                    clicked = item
                    break

            self.selected_item = clicked
            self._update_properties()
            self._redraw()

            if clicked:
                clicked.save_position()
                self._dragging = True
                self._drag_start = (event.xdata, event.ydata)
                self._item_start_pos = (clicked.x_mm, clicked.y_mm)

    def _on_motion(self, event):
        if event.inaxes != self.ax:
            return

        # actualizar barra de estado con coordenadas
        self.status_bar.setText(f"X: {event.xdata:.2f} mm  Y: {event.ydata:.2f} mm")

        # pan
        if self._panning and self._drag_start:
            dx = event.xdata - self._drag_start[0]
            dy = event.ydata - self._drag_start[1]
            xl = self.ax.get_xlim()
            yl = self.ax.get_ylim()
            self.ax.set_xlim(xl[0] - dx, xl[1] - dx)
            self.ax.set_ylim(yl[0] - dy, yl[1] - dy)
            self.canvas.draw_idle()
            return

        # redimension con boton derecho
        if self._resizing and self.selected_item and self._drag_start and self._item_start_size:
            dx = event.xdata - self._drag_start[0]
            dy = event.ydata - self._drag_start[1]
            new_w = max(0.5, self._item_start_size[0] + dx)
            new_h = max(0.5, self._item_start_size[1] + dy)
            self.selected_item.w_mm = new_w
            self.selected_item.h_mm = new_h
            m = self.machine
            if m.is_calibrated:
                self.selected_item.w_px = int(round(new_w / m.mm_per_pixel))
                self.selected_item.h_px = int(round(new_h / m.mm_per_pixel))
            self._update_properties()
            self._redraw()
            return

        # arrastre de item
        if self._dragging and self.selected_item and self._drag_start:
            dx = event.xdata - self._drag_start[0]
            dy = event.ydata - self._drag_start[1]
            
            target_x = max(0, self._item_start_pos[0] + dx)
            target_y = max(0, self._item_start_pos[1] + dy)
            
            # con shift el movimiento se ajusta a la grilla (Snap to Grid)
            from PyQt5.QtWidgets import QApplication
            from PyQt5.QtCore import Qt
            modifiers = QApplication.keyboardModifiers()
            if bool(modifiers & Qt.ShiftModifier):
                try:
                    s = float(self.inp_grid_spacing.text().replace(',', '.'))
                    if s > 0:
                        target_x = round(target_x / s) * s
                        target_y = round(target_y / s) * s
                except ValueError:
                    pass

            self.selected_item.x_mm = target_x
            self.selected_item.y_mm = target_y
            self._update_properties()
            self._redraw()

    def _on_release(self, event):
        if event.button == 2:
            self._panning = False
            self._drag_start = None
            self.canvas.setCursor(Qt.ArrowCursor)
            return

        if event.button == 3 and self._resizing:
            self._resizing = False
            self._drag_start = None
            self._item_start_size = None
            self.canvas.setCursor(Qt.ArrowCursor)
            self._invalidate_trajectory()
            return

        if event.button == 1 and self._dragging and self.selected_item:
            self._dragging = False
            self._drag_start = None

            # collision detection: revertir si excede el bed
            m = self.machine
            if self.selected_item.exceeds_bounds(m.bed_x_max_mm, m.bed_y_max_mm):
                self.selected_item.revert_position()
                self.status_bar.setText("item fuera de limites, posicion revertida")

            self._update_properties()
            self._redraw()
            self._invalidate_trajectory()

    def _invalidate_trajectory(self):
        """invalida la trayectoria cuando se modifica un item."""
        self.task_queue = []
        self.btn_simulate.setEnabled(False)
        self.btn_execute.setEnabled(False)

    def _on_scroll(self, event):
        if event.inaxes != self.ax:
            return

        # ctrl+scroll: rotar item seleccionado
        if event.key == "control" and self.selected_item:
            delta = 5 if event.button == "up" else -5
            self.selected_item.rotation_deg = (self.selected_item.rotation_deg + delta) % 360
            self._update_properties()
            self._redraw()
            self._invalidate_trajectory()
            return

        # shift+scroll: redimensionar item seleccionado
        if event.key == "shift" and self.selected_item:
            factor = 1.05 if event.button == "up" else (1 / 1.05)
            self.selected_item.w_mm *= factor
            self.selected_item.h_mm *= factor
            m = self.machine
            if m.is_calibrated:
                self.selected_item.w_px = int(round(self.selected_item.w_mm / m.mm_per_pixel))
                self.selected_item.h_px = int(round(self.selected_item.h_mm / m.mm_per_pixel))
            self._update_properties()
            self._redraw()
            self._invalidate_trajectory()
            return

        # scroll normal: zoom
        factor = 1.15 if event.button == "up" else (1 / 1.15)
        xl = self.ax.get_xlim()
        yl = self.ax.get_ylim()
        xr = xl[1] - xl[0]
        yr = yl[1] - yl[0]
        nxr = xr / factor
        nyr = yr / factor
        rx = (event.xdata - xl[0]) / xr
        ry = (event.ydata - yl[0]) / yr
        self.ax.set_xlim(event.xdata - nxr * rx, event.xdata + nxr * (1 - rx))
        self.ax.set_ylim(event.ydata - nyr * ry, event.ydata + nyr * (1 - ry))
        self.canvas.draw_idle()

    def _restore_view(self):
        if hasattr(self, "_original_xlim"):
            self.ax.set_xlim(self._original_xlim)
            self.ax.set_ylim(self._original_ylim)
            self.canvas.draw_idle()

    def _on_key_press(self, event):
        if event.key in ("delete", "backspace"):
            self._delete_selected()

    # =========================================================================
    # gestion de items
    # =========================================================================

    def _add_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Cargar Imagen", "", "Imagenes (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if not path:
            return

        try:
            img = mpimg.imread(path)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo cargar la imagen:\n{e}")
            return

        m = self.machine
        h_px, w_px = img.shape[:2]
        w_mm = w_px * m.mm_per_pixel
        h_mm = h_px * m.mm_per_pixel

        item = LayoutItem(
            item_type="image",
            name=os.path.basename(path),
            x_mm=1.0, y_mm=1.0,
            w_mm=w_mm, h_mm=h_mm,
            w_px=w_px, h_px=h_px,
            data=img,
            filepath=path,
        )
        self.items.append(item)
        self.selected_item = item
        self._update_properties()
        self._redraw()

        self._redraw()

    def _add_shape(self, shape_type: str):
        title = "Dimensiones del Rectangulo"
        is_circle = False
        if shape_type == "circle":
            title = "Dimensiones del Circulo"
            is_circle = True
        elif shape_type == "line":
            title = "Dimensiones de la Linea"

        dlg = ShapeDimensionDialog(self, title=title, is_circle=is_circle)
        if dlg.exec_() == QDialog.Accepted:
            w, h = dlg.get_dimensions()
            item = LayoutItem(
                item_type=shape_type,
                name=f"Figura ({shape_type})",
                x_mm=1.0, y_mm=1.0,
                w_mm=w, h_mm=h,
            )
            self.items.append(item)
            self.selected_item = item
            self._update_properties()
            self._redraw()

    def _fit_to_fov(self):
        m = self.machine
        if self.selected_item and m.is_calibrated:
            self.selected_item.w_mm = m.fov_w_mm
            self.selected_item.h_mm = m.fov_h_mm
            self.selected_item.w_px = int(round(m.fov_w_mm / m.mm_per_pixel))
            self.selected_item.h_px = int(round(m.fov_h_mm / m.mm_per_pixel))
            self._update_properties()
            self._redraw()
            self._invalidate_trajectory()

    def _toggle_projector(self):
        if self._is_projecting:
            self._turn_off_projector()
        else:
            self._project_white_fov()

    def _project_white_fov(self):
        m = self.machine
        if not m.is_calibrated:
            QMessageBox.warning(self, "Error", "Debe calibrar el sistema primero.")
            return
            
        if self.main_app and getattr(self.main_app, "projector_active", False) and getattr(self.main_app, "projection_window", None):
            white_img = np.ones((m.fov_h_px, m.fov_w_px), dtype=np.uint8) * 255
            self.main_app.projection_window.update_segment(white_img)
            self._is_projecting = True
            
            t = self.inp_exp.value()
                
            self.status_bar.setText(f"Proyectando FOV en blanco por {t}s")
            self._fov_timer.start(int(t * 1000))
        else:
            QMessageBox.warning(self, "Error", "El proyector no esta activo.")

    def _project_selected_item(self):
        m = self.machine
        if not m.is_calibrated:
            QMessageBox.warning(self, "Error", "Debe calibrar el sistema primero.")
            return
            
        if not self.selected_item:
            QMessageBox.warning(self, "Error", "Seleccione un elemento primero.")
            return

        if not (self.main_app and getattr(self.main_app, "projector_active", False) and getattr(self.main_app, "projection_window", None)):
            QMessageBox.warning(self, "Error", "El proyector no esta activo.")
            return

        item = self.selected_item
        proj_img = np.zeros((m.fov_h_px, m.fov_w_px), dtype=np.uint8)

        if item.item_type == "image" and item.data is not None:
            img = item.data.copy()
            if img.dtype != np.uint8:
                img = (img * 255).astype(np.uint8)
            if img.ndim == 3:
                if img.shape[2] == 4:
                    alpha = img[:, :, 3] / 255.0
                    gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
                    img = (gray * alpha).astype(np.uint8)
                elif img.shape[2] == 3:
                    img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            
            target_w_px = max(1, int(round(item.w_mm / m.mm_per_pixel)))
            target_h_px = max(1, int(round(item.h_mm / m.mm_per_pixel)))
            
            if img.shape[1] != target_w_px or img.shape[0] != target_h_px:
                interp = cv2.INTER_AREA if target_w_px < img.shape[1] else cv2.INTER_CUBIC
                img = cv2.resize(img, (target_w_px, target_h_px), interpolation=interp)
                
            if item.rotation_deg != 0:
                center = (target_w_px / 2.0, target_h_px / 2.0)
                M = cv2.getRotationMatrix2D(center, item.rotation_deg, 1.0)
                abs_cos = abs(M[0, 0]); abs_sin = abs(M[0, 1])
                bound_w = int(target_h_px * abs_sin + target_w_px * abs_cos)
                bound_h = int(target_h_px * abs_cos + target_w_px * abs_sin)
                M[0, 2] += bound_w / 2.0 - center[0]
                M[1, 2] += bound_h / 2.0 - center[1]
                img = cv2.warpAffine(img, M, (bound_w, bound_h), borderValue=0)
            
            # centrar en el fov
            y_off = max(0, (m.fov_h_px - img.shape[0]) // 2)
            x_off = max(0, (m.fov_w_px - img.shape[1]) // 2)
            crop_h = min(img.shape[0], m.fov_h_px)
            crop_w = min(img.shape[1], m.fov_w_px)
            proj_img[y_off:y_off+crop_h, x_off:x_off+crop_w] = img[:crop_h, :crop_w]
            
        elif item.item_type in ["rect", "circle", "line"]:
            target_w_px = max(1, int(round(item.w_mm / m.mm_per_pixel)))
            target_h_px = max(1, int(round(item.h_mm / m.mm_per_pixel)))
            y_off = max(0, (m.fov_h_px - target_h_px) // 2)
            x_off = max(0, (m.fov_w_px - target_w_px) // 2)
            if item.item_type == "rect":
                cv2.rectangle(proj_img, (x_off, y_off), (x_off+target_w_px, y_off+target_h_px), 255, -1)
            elif item.item_type == "circle":
                r = min(target_w_px, target_h_px) // 2
                cv2.circle(proj_img, (x_off+target_w_px//2, y_off+target_h_px//2), r, 255, -1)
            elif item.item_type == "line":
                cv2.line(proj_img, (x_off, y_off+target_h_px//2), (x_off+target_w_px, y_off+target_h_px//2), 255, item.h_px if item.h_px > 0 else 5)

        self.main_app.projection_window.update_segment(proj_img)
        self._is_projecting = True
        
        t = self.inp_exp.value()
            
        self.status_bar.setText(f"Proyectando '{item.name}' por {t}s")
        self._fov_timer.start(int(t * 1000))

    def _turn_off_projector(self):
        if self.main_app and getattr(self.main_app, "projector_active", False) and getattr(self.main_app, "projection_window", None):
            self.main_app.projection_window.show_black_screen()
        self._is_projecting = False
        self._fov_timer.stop()
        self.status_bar.setText("Proyeccion apagada")

    def _duplicate_selected(self):
        if not self.selected_item:
            return
        orig = self.selected_item
        import copy
        new_item = copy.copy(orig)
        new_item.uid = os.urandom(4).hex()
        new_item.x_mm += 2.0
        new_item.y_mm += 2.0
        # copy array if it's an image
        if new_item.data is not None:
            new_item.data = orig.data.copy()
            
        self.items.append(new_item)
        self.selected_item = new_item
        self._update_properties()
        self._redraw()
        self._invalidate_trajectory()

    def _add_selected_shape(self):
        shape = self.combo_shapes.currentText()
        if shape == "Rectangulo":
            self._add_shape("rect")
        elif shape == "Circulo":
            self._add_shape("circle")
        elif shape == "Linea (mm)":
            self._add_shape("line")
        elif shape == "Linea (Pixeles)":
            self._add_line_px()

    def _toggle_invert(self, checked):
        if self.selected_item and self.selected_item.item_type == "image" and self.selected_item.data is not None:
            self.selected_item.inverted = checked
            img = self.selected_item.data
            if img.ndim == 3 and img.shape[2] == 4:
                # invertir solo canales RGB, mantener alpha
                img[:, :, :3] = 255 - img[:, :, :3]
            else:
                img = 255 - img
            self.selected_item.data = img
            self._redraw()
            self._invalidate_trajectory()

    def _add_line_px(self):
        from PyQt5.QtWidgets import QInputDialog
        px, ok = QInputDialog.getInt(self, "Linea en Pixeles", "Grosor de la linea (px):", 10, 1, 10000)
        if ok:
            m = self.machine
            w_mm = min(10.0, m.bed_x_max_mm) if m.bed_x_max_mm > 0 else 10.0
            h_mm = (px * m.mm_per_pixel) if m.is_calibrated else (px * 0.01)
            
            item = LayoutItem(
                item_type="line",
                name=f"Linea ({px}px)",
                x_mm=1.0, y_mm=1.0,
                w_mm=w_mm, h_mm=h_mm,
                w_px=int(w_mm / m.mm_per_pixel) if m.is_calibrated else 0,
                h_px=px,
            )
            self.items.append(item)
            self.selected_item = item
            self._update_properties()
            self._redraw()

    def _delete_selected(self):
        if self.selected_item and self.selected_item in self.items:
            self.items.remove(self.selected_item)
            self.selected_item = None
            self._update_properties()
            self._redraw()

    # =========================================================================
    # panel de propiedades
    # =========================================================================

    def _update_properties(self):
        item = self.selected_item
        if not item:
            self.lbl_name.setText("ningun elemento seleccionado")
            self.lbl_info.setText("")
            for inp in [self.inp_x, self.inp_y, self.inp_w, self.inp_h, self.inp_px_w, self.inp_px_h]:
                inp.clear()
            self.slider_rot.setValue(0)
            self.lbl_rot_val.setText("0 deg")
            return

        self.lbl_name.setText(item.name)
        self.inp_x.setText(f"{item.x_mm:.2f}")
        self.inp_y.setText(f"{item.y_mm:.2f}")
        self.inp_w.setText(f"{item.w_mm:.2f}")
        self.inp_h.setText(f"{item.h_mm:.2f}")

        # tamanio en pixeles
        m = self.machine
        if m.is_calibrated:
            px_w = int(round(item.w_mm / m.mm_per_pixel))
            px_h = int(round(item.h_mm / m.mm_per_pixel))
        else:
            px_w = item.w_px
            px_h = item.h_px

        if item.item_type == "image":
            self.chk_invert.setVisible(True)
            self.chk_invert.blockSignals(True)
            self.chk_invert.setChecked(getattr(item, 'inverted', False))
            self.chk_invert.blockSignals(False)
        else:
            self.chk_invert.setVisible(False)

        # info de posicion y tiling
        lines = [f"Posicion: ({item.x_mm:.2f}, {item.y_mm:.2f}) mm"]
        if m.is_calibrated:
            exceeds_w = item.w_mm > m.fov_w_mm
            exceeds_h = item.h_mm > m.fov_h_mm
            if exceeds_w or exceeds_h:
                ov = self.spin_overlap.value()
                sx = max(0.1, m.fov_w_mm - ov)
                sy = max(0.1, m.fov_h_mm - ov)
                tx = max(1, int(ceil(item.w_mm / sx)))
                ty = max(1, int(ceil(item.h_mm / sy)))
                lines.append(f"Excede FOV -> Auto-tile: {tx}x{ty} = {tx*ty} tiles")
            else:
                lines.append("Cabe en un solo FOV (sin tiling)")

        self.lbl_info.setText("\n".join(lines))
        self.slider_rot.blockSignals(True)
        self.slider_rot.setValue(int(item.rotation_deg))
        self.slider_rot.blockSignals(False)
        self.lbl_rot_val.setText(f"{int(item.rotation_deg)} deg")

        self.inp_exp.setValue(item.exposure_s)
        self.inp_delay.setValue(item.delay_s)

    def _apply_position_from_input(self):
        if not self.selected_item:
            return
        try:
            x = float(self.inp_x.text())
            y = float(self.inp_y.text())
            self.selected_item.x_mm = max(0, x)
            self.selected_item.y_mm = max(0, y)
            self._redraw()
        except ValueError:
            pass

    def _apply_size_from_input(self):
        if not self.selected_item:
            return
        try:
            w = float(self.inp_w.text())
            h = float(self.inp_h.text())
            if w > 0 and h > 0:
                self.selected_item.w_mm = w
                self.selected_item.h_mm = h
                m = self.machine
                if m.is_calibrated:
                    self.selected_item.w_px = int(round(w / m.mm_per_pixel))
                    self.selected_item.h_px = int(round(h / m.mm_per_pixel))
                self._update_properties()
                self._redraw()
        except ValueError:
            pass

    def _apply_px_size_from_input(self):
        if not self.selected_item:
            return
        m = self.machine
        if not m.is_calibrated:
            return
        try:
            px_w = int(self.inp_px_w.text())
            px_h = int(self.inp_px_h.text())
            if px_w > 0 and px_h > 0:
                self.selected_item.w_mm = px_w * m.mm_per_pixel
                self.selected_item.h_mm = px_h * m.mm_per_pixel
                self.selected_item.w_px = px_w
                self.selected_item.h_px = px_h
                self._update_properties()
                self._redraw()
        except ValueError:
            pass

    def _on_rotation_changed(self, value):
        if not self.selected_item:
            return
        self.selected_item.rotation_deg = float(value)
        self.lbl_rot_val.setText(f"{value} deg")
        # aplicar rotacion a la imagen si corresponde
        if self.selected_item.item_type == "image" and self.selected_item.data is not None:
            self._redraw()

    # =========================================================================
    # generacion de trayectoria (auto-tiling + path planning)
    # =========================================================================

    def _format_time(self, seconds_total: float) -> str:
        if seconds_total < 60:
            return f"{seconds_total:.1f} seg"
        m = int(seconds_total // 60)
        s = int(seconds_total % 60)
        return f"{m} min {s} seg"

    def _generate_trajectory(self):
        if not self.items:
            QMessageBox.warning(self, "Layout Vacio", "no hay elementos en el layout.")
            return

        m = self.machine
        if not m.is_calibrated:
            QMessageBox.warning(self, "Sin Calibracion", "la calibracion optica es necesaria.")
            return

        # leer tiempos del panel
        try:
            global_exp = self.inp_exp.value()
            global_delay = self.inp_delay.value()
        except ValueError:
            global_exp, global_delay = 10.0, 5.0

        overlap = self.spin_overlap.value()
        all_tasks = []

        for item in self.items:
            # aplicar tiempos globales si el lock esta activado
            if self.chk_lock.isChecked():
                item.exposure_s = global_exp
                item.delay_s = global_delay

            # preparar la imagen para el tiling
            if item.item_type == "image" and item.data is not None:
                img = item.data.copy()
                # normalizar siempre a uint8 (0-255) antes de procesar
                if img.dtype != np.uint8:
                    # mpimg.imread carga pngs como float32 en rango [0, 1]
                    img = (img * 255).astype(np.uint8)

                # convertir a escala de grises
                if img.ndim == 3:
                    if img.shape[2] == 4:
                        # considerar el canal alpha: fondo negro para la transparencia
                        alpha = img[:, :, 3] / 255.0
                        gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
                        img = (gray * alpha).astype(np.uint8)
                    elif img.shape[2] == 3:
                        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

                # escalar a las dimensiones fisicas ajustadas por el usuario
                target_w_px = max(1, int(round(item.w_mm / m.mm_per_pixel)))
                target_h_px = max(1, int(round(item.h_mm / m.mm_per_pixel)))
                if img.shape[1] != target_w_px or img.shape[0] != target_h_px:
                    interp = cv2.INTER_AREA if target_w_px < img.shape[1] else cv2.INTER_CUBIC
                    img = cv2.resize(img, (target_w_px, target_h_px), interpolation=interp)

                # variables para el item temporal
                t_w_mm = item.w_mm
                t_h_mm = item.h_mm
                t_x_mm = item.x_mm
                t_y_mm = item.y_mm

                # aplicar rotacion
                if item.rotation_deg != 0:
                    # opencv rota antihorario con angulos positivos. Matplotlib usa
                    center = (target_w_px / 2.0, target_h_px / 2.0)
                    M = cv2.getRotationMatrix2D(center, item.rotation_deg, 1.0)
                    abs_cos = abs(M[0, 0])
                    abs_sin = abs(M[0, 1])
                    bound_w = int(target_h_px * abs_sin + target_w_px * abs_cos)
                    bound_h = int(target_h_px * abs_cos + target_w_px * abs_sin)
                    M[0, 2] += bound_w / 2.0 - center[0]
                    M[1, 2] += bound_h / 2.0 - center[1]
                    # rellenar con negro (0) para no exponer las esquinas vacias
                    img = cv2.warpAffine(img, M, (bound_w, bound_h), borderValue=0)
                    
                    # actualizar caja ortogonal para el tiling
                    t_w_mm = bound_w * m.mm_per_pixel
                    t_h_mm = bound_h * m.mm_per_pixel
                    cx = item.x_mm + item.w_mm / 2.0
                    cy = item.y_mm + item.h_mm / 2.0
                    t_x_mm = cx - t_w_mm / 2.0
                    t_y_mm = cy - t_h_mm / 2.0

                # crear un item temporal con la imagen procesada
                temp_item = LayoutItem(
                    uid=item.uid,
                    item_type=item.item_type,
                    name=item.name,
                    x_mm=t_x_mm, y_mm=t_y_mm,
                    w_mm=t_w_mm, h_mm=t_h_mm,
                    w_px=img.shape[1], h_px=img.shape[0],
                    data=img,
                    exposure_s=item.exposure_s,
                    delay_s=item.delay_s,
                )
                tasks = compute_tiling(temp_item, m.fov_w_mm, m.fov_h_mm, m.mm_per_pixel, overlap)
            else:
                tasks = compute_tiling(item, m.fov_w_mm, m.fov_h_mm, m.mm_per_pixel, overlap)

            all_tasks.extend(tasks)

        # optimizar trayectoria
        self.task_queue = optimize_path(all_tasks)

        # actualizar ui
        self.task_list.clear()
        for i, t in enumerate(self.task_queue):
            shape = t.image_data.shape if t.image_data is not None else "?"
            text = f"[{i+1}] ({t.target_x_mm:.1f}, {t.target_y_mm:.1f}) mm | {shape} | {t.exposure_s}s"
            self.task_list.addItem(QListWidgetItem(text))

        total_time = sum(t.exposure_s + t.delay_s for t in self.task_queue)
        time_str = self._format_time(total_time)
        self.lbl_tiling_info.setText(
            f"Total: {len(self.task_queue)} tareas\n"
            f"Tiempo estimado: {time_str}\n"
            f"Overlap: {overlap} mm"
        )
        self.lbl_exec_time.setText(f"Tiempo estimado total: {time_str}")
        self.lbl_exec_status.setText(f"trayectoria generada: {len(self.task_queue)} tareas")
        self.progress.setMaximum(len(self.task_queue))
        self.progress.setValue(0)

        self.btn_simulate.setEnabled(True)
        self.btn_execute.setEnabled(True)
        self._redraw()

    # =========================================================================
    # simulacion visual (sin motores)
    # =========================================================================

    def _simulate(self):
        """lanza el worker en modo simulacion (sin controlador real)."""
        if not self.task_queue:
            return
        self._launch_worker(controller=None)

    # =========================================================================
    # ejecucion real (con motores)
    # =========================================================================

    def _execute(self):
        """lanza el worker con el controlador de motores real."""
        if not self.task_queue:
            return

        if not self.ctrl or not hasattr(self.ctrl, "ser") or self.ctrl.ser is None:
            reply = QMessageBox.question(
                self, "Motores Desconectados",
                "los motores no estan conectados.\nejecutar en modo simulacion?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._simulate()
            return

        # activar proyector si no esta activo
        if self.main_app and not getattr(self.main_app, "projector_active", False):
            reply = QMessageBox.question(
                self, "Proyector Inactivo",
                "el proyector no esta activo. activarlo ahora?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes and hasattr(self.main_app, "toggle_projector"):
                self.main_app.toggle_projector()
                if not getattr(self.main_app, "projector_active", False):
                    return
            elif reply == QMessageBox.No:
                return

        self._launch_worker(controller=self.ctrl)

    def _launch_worker(self, controller):
        """crea y lanza el CamWorker en un hilo independiente."""
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "En Ejecucion", "ya hay una ejecucion en curso.")
            return

        self._worker = CamWorker(
            task_queue=self.task_queue,
            controller=controller,
            steps_per_mm=self.machine.steps_per_mm,
        )

        # conectar señales
        self._worker.sig_move_started.connect(self._on_move_started)
        self._worker.sig_stabilizing.connect(self._on_stabilizing)
        self._worker.sig_exposing.connect(self._on_exposing)
        self._worker.sig_project_image.connect(self._on_project_image)
        self._worker.sig_black_screen.connect(self._on_black_screen)
        self._worker.sig_task_done.connect(self._on_task_done)
        self._worker.sig_all_done.connect(self._on_all_done)
        self._worker.sig_error.connect(self._on_error)
        self._worker.sig_log.connect(self._on_log)

        # ui
        self.btn_generate.setEnabled(False)
        self.btn_simulate.setEnabled(False)
        self.btn_execute.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress.setValue(0)

        mode = "simulacion" if controller is None else "ejecucion real"
        self.lbl_exec_status.setText(f"iniciando {mode}...")

        self._worker.start()

    def _home_motors(self):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "En Ejecucion", "No se puede hacer homing mientras hay un proceso en ejecucion.")
            return
            
        if self.ctrl and hasattr(self.ctrl, "home_all"):
            self.ctrl.home_all()
            self.lbl_exec_status.setText("ejecutando homing (regresando al origen)...")
            self._current_fov_pos = (0.0, 0.0)
            self._redraw()
        else:
            QMessageBox.warning(self, "Motores Desconectados", "No hay un controlador de motores conectado.")

    def _emergency_stop(self):
        if self._worker and self._worker.isRunning():
            self._worker.abort()
            self.lbl_exec_status.setText("parada de emergencia solicitada")

        # parada de emergencia del controlador
        if self.ctrl and hasattr(self.ctrl, "emergency_stop"):
            self.ctrl.emergency_stop()

    # -- slots del worker --

    @pyqtSlot(int, float, float)
    def _on_move_started(self, idx, x, y):
        total = len(self.task_queue)
        self.lbl_exec_status.setText(f"[{idx+1}/{total}] moviendo a ({x:.2f}, {y:.2f}) mm")
        self._current_fov_pos = (x, y)
        self._redraw()

    @pyqtSlot(int, float)
    def _on_stabilizing(self, idx, delay):
        self.lbl_exec_status.setText(f"[{idx+1}] estabilizando ({delay:.1f}s)...")

    @pyqtSlot(int, float)
    def _on_exposing(self, idx, exp):
        self.lbl_exec_status.setText(f"[{idx+1}] exponiendo ({exp:.1f}s)...")

    @pyqtSlot(object)
    def _on_project_image(self, img_array):
        """envia la imagen al proyector real via la app principal."""
        if (self.main_app and
            getattr(self.main_app, "projector_active", False) and
            getattr(self.main_app, "projection_window", None)):
            self.main_app.projection_window.update_segment(img_array)

    @pyqtSlot()
    def _on_black_screen(self):
        if (self.main_app and
            getattr(self.main_app, "projection_window", None)):
            self.main_app.projection_window.show_black_screen()

    @pyqtSlot(int, int)
    def _on_task_done(self, idx, total):
        self.progress.setValue(idx + 1)
        # resaltar el task en la lista
        if idx < self.task_list.count():
            self.task_list.setCurrentRow(idx)

    @pyqtSlot(int, float)
    def _on_all_done(self, total, elapsed):
        self.lbl_exec_status.setText(
            f"completado: {total} tareas en {elapsed:.1f}s ({elapsed/60:.1f} min)"
        )
        self.btn_generate.setEnabled(True)
        self.btn_simulate.setEnabled(True)
        self.btn_execute.setEnabled(True)
        self.btn_stop.setEnabled(False)

    @pyqtSlot(str)
    def _on_error(self, msg):
        self.lbl_exec_status.setText(f"error: {msg}")
        self.btn_generate.setEnabled(True)
        self.btn_simulate.setEnabled(True)
        self.btn_execute.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.critical(self, "Error de Ejecucion", msg)

    @pyqtSlot(str, str)
    def _on_log(self, msg, level):
        self.status_bar.setText(msg)
