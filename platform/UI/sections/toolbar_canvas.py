"""
Sección: Toolbar superior + Canvas matplotlib.

Métodos:
    _build_toolbar()  → barra de acciones, sliders de sigma/brillo
    _build_canvas()   → área de visualización y eventos de mouse
"""
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QComboBox, QWidget
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
from constants import (
    IMAGE_FORMATS, DARK_BG_PRIMARY,
    SIGMA_SLIDER_MIN, SIGMA_SLIDER_MAX,
    BRIGHTNESS_SLIDER_MIN, BRIGHTNESS_SLIDER_MAX,
)


class ToolbarCanvasBuilder:
    """Mixin: construye la barra superior y el canvas matplotlib."""

    def _build_toolbar(self) -> QHBoxLayout:
        """
        Construye la barra de controles superior.
        Contiene los botones principales de acción y los sliders de
        sigma (desenfoque óptico) y brillo de proyección.
        """
        layout = QHBoxLayout()

        # ── Botones de acción principal ───────────────────────────────────────
        self.load_button = QPushButton(" Cargar patrón")
        self.load_button.clicked.connect(self.load_pattern)

        self.toggle_view_button = QPushButton(" Vista grid")
        self.toggle_view_button.clicked.connect(self.toggle_grid_view)

        self.calibration_button = QPushButton(" Calibración óptica")
        self.calibration_button.clicked.connect(self.toggle_calibration_view)

        self.pattern_calib_button = QPushButton(" Calibración de patrón")
        self.pattern_calib_button.clicked.connect(self.toggle_pattern_calibration_view)
        self.pattern_calib_button.setToolTip("Pestaña para calibración de tamaño espacial y exposición")

        self.preferences_button = QPushButton(" Preferencias")
        from PyQt5.QtWidgets import QMenu
        self.preferences_menu = QMenu(self.preferences_button)
        self.preferences_button.setMenu(self.preferences_menu)
        self.preferences_menu.aboutToShow.connect(self.show_preferences_menu)

        self.motors_button = QPushButton(" Motores")
        self.motors_button.clicked.connect(self.toggle_motors_view)

        self.btn_proyecciones = QPushButton(" Proyecciones")
        self.btn_proyecciones.setCheckable(True)
        self.btn_proyecciones.clicked.connect(self.toggle_proyecciones_view)

        self.projector_button = QPushButton(" Proyectar")
        self.projector_button.clicked.connect(self.toggle_projector)

        self.ruler_scale_button = QPushButton(" Regla de escala")
        self.ruler_scale_button.clicked.connect(self.toggle_ruler_scale_view)
        self.ruler_scale_button.setToolTip(
            "Genera y proyecta líneas de escala calibradas con desplazamiento motorizado"
        )

        # ── Sigma (desenfoque óptico) — oculto hasta que hay imagen ──────────
        self.sigma_label = QLabel(f"Sigma (Desenfoque): {self.sigma:.1f}")
        self.sigma_slider = QSlider(Qt.Horizontal)
        self.sigma_slider.setMinimum(SIGMA_SLIDER_MIN)
        self.sigma_slider.setMaximum(SIGMA_SLIDER_MAX)
        self.sigma_slider.setValue(int(self.sigma))
        self.sigma_slider.valueChanged.connect(self.update_sigma)
        self.sigma_label.setVisible(False)
        self.sigma_slider.setVisible(False)

        # ── Brillo de proyección — oculto hasta que el proyector está activo ─
        self.brightness_label = QLabel(f"Brillo proyección: {self.brightness}%")
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setMinimum(BRIGHTNESS_SLIDER_MIN)
        self.brightness_slider.setMaximum(BRIGHTNESS_SLIDER_MAX)
        self.brightness_slider.setValue(self.brightness)
        self.brightness_slider.valueChanged.connect(self.update_brightness)
        self.brightness_slider.setVisible(False)
        self.brightness_label.setVisible(False)

        # ── Guardar imagen ────────────────────────────────────────────────────
        self.save_widget = QWidget()
        save_layout = QHBoxLayout(self.save_widget)
        save_layout.setContentsMargins(0, 0, 0, 0)
        save_layout.setSpacing(8)

        self.save_button = QPushButton(" Guardar imagen")
        self.save_button.clicked.connect(self.save_image)

        self.format_label = QLabel("Formato:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(IMAGE_FORMATS)

        save_layout.addWidget(self.save_button)
        save_layout.addWidget(self.format_label)
        save_layout.addWidget(self.format_combo)

        self.save_widget.setVisible(False)

        # ── Ensamblar ─────────────────────────────────────────────────────────
        for widget in (
            self.load_button, self.toggle_view_button, self.pattern_calib_button, self.calibration_button,
            self.ruler_scale_button, self.preferences_button, self.motors_button, self.btn_proyecciones, self.projector_button,
        ):
            layout.addWidget(widget)
            
        # El expansor absorbe el espacio extra, anclando los botones a la izquierda 
        # y evitando que se muevan cuando aparecen/desaparecen los controles de la derecha.
        layout.addStretch()

        for widget in (
            self.sigma_label, self.sigma_slider,
            self.brightness_label, self.brightness_slider,
            self.save_widget,
        ):
            layout.addWidget(widget)

        return layout

    def _build_canvas(self) -> None:
        """
        Crea el área de visualización matplotlib y conecta los eventos de mouse.
        Guarda en self: figure, canvas, toolbar y canvas_with_toolbar.
        """
        self.figure = Figure(facecolor=DARK_BG_PRIMARY)
        self.canvas = FigureCanvas(self.figure)

        # Eventos de interacción con el canvas
        self.canvas.mpl_connect("button_press_event",   self.on_mouse_press)
        self.canvas.mpl_connect("button_release_event", self.on_mouse_release)
        self.canvas.mpl_connect("motion_notify_event",  self.on_mouse_move)
        self.canvas.mpl_connect("scroll_event",         self.on_mouse_scroll)

        # Toolbar de navegación (visible sólo en modo grid)
        self.canvas_with_toolbar = QVBoxLayout()
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.customize_toolbar()
        self.toolbar.setVisible(False)
        self.canvas_with_toolbar.addWidget(self.toolbar)
        self.canvas_with_toolbar.addWidget(self.canvas)
