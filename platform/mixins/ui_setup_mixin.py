"""
Mixin de configuración de interfaz de usuario.

Orquestador que compone todos los builders de secciones del sidebar.
Cada sección vive en su propio módulo bajo UI/sections/ para facilitar
la localización y modificación independiente de cada parte de la UI.

Jerarquía de construcción
─────────────────────────
_build_ui()                          ← orquestador principal
├── _init_ui_state()                 ← variables de estado ligadas a widgets
├── _build_toolbar()                 ← toolbar_canvas.py
├── _build_canvas()                  ← toolbar_canvas.py
├── _build_sidebar()                 ← scroll area con todas las secciones
│   ├── _build_stats_section()           data_panels.py      📊 DATA
│   ├── _build_binary_section()          data_panels.py      ⚫⚪ BINARIO
│   ├── _build_grid_stats_section()      data_panels.py      📏 ESTADÍSTICAS GRID
│   ├── _build_basler_section()          camera_panel.py     🎥 CÁMARA BASLER
│   ├── _build_image_coords_section()    grid_panels.py      🖼️ IMAGEN EN GRID
│   ├── _build_grid_config_section()     grid_panels.py      📏 CONFIGURACIÓN GRID
│   ├── _build_segmentation_section()    segmentation_panel.py ✂️ SEGMENTACIÓN
│   ├── _build_motors_section()          motors_panel.py     ⚙️ MOTORES
│   ├── _build_exposure_frequency_tabs() exposure_panel.py   tabs ⏱️/〜
│   ├── _build_exposure_section()        exposure_panel.py   ⏱️ EXPOSICIÓN
│   ├── _build_frequency_section()       exposure_panel.py   〜 FRECUENCIA
│   ├── _build_projection_section()      projection_panel.py 🎬 PROYECCIÓN
│   ├── _build_calibration_monitor()     calibration_panel.py 🔍 CALIBRACIÓN
│   ├── _build_file_tree()               file_console.py     📁 ARCHIVOS
│   └── _build_console_section()         file_console.py     📋 CONSOLA
└── _connect_screen_signals()        ← detección de monitor secundario
"""
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QScrollArea, QWidget,
)
from PyQt5.QtCore import Qt, QTimer

from UI.sections import (
    ToolbarCanvasBuilder,
    DataPanelsBuilder,
    CameraPanelBuilder,
    GridPanelsBuilder,
    SegmentationPanelBuilder,
    MotorsPanelBuilder,
    ExposurePanelBuilder,
    ProjectionPanelBuilder,
    CalibrationPanelBuilder,
    FileConsolePanelBuilder,
    RulerScalePanelBuilder,
    PatternCalibPanelBuilder,
)
from constants import (
    SIDEBAR_MIN_WIDTH, SIDEBAR_MAX_WIDTH, SIDEBAR_SPACING,
    SIDEBAR_SECTION_SPACING,
)


class UISetupMixin(
    ToolbarCanvasBuilder,
    DataPanelsBuilder,
    CameraPanelBuilder,
    GridPanelsBuilder,
    SegmentationPanelBuilder,
    MotorsPanelBuilder,
    ExposurePanelBuilder,
    ProjectionPanelBuilder,
    CalibrationPanelBuilder,
    FileConsolePanelBuilder,
    RulerScalePanelBuilder,
    PatternCalibPanelBuilder,
):
    """
    Mixin: construye la interfaz gráfica completa del simulador.

    Hereda de 10 builders especializados (UI/sections/) que aportan
    los métodos _build_*() de cada sección. Este archivo solo contiene
    el orquestador (_build_ui), el estado inicial (_init_ui_state),
    el ensamblaje del sidebar y la conexión de señales de pantalla.
    """

    # ═════════════════════════════════════════════════════════════════════════
    # PUNTO DE ENTRADA
    # ═════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        """
        Ensambla toda la UI llamando a los constructores de cada sección.
        Debe llamarse desde __init__() después de _init_state().
        """
        self._init_ui_state()

        control_layout  = self._build_toolbar()
        self._build_canvas()
        sidebar = self._build_sidebar()
        self._main_sidebar = sidebar
        self._build_ruler_scale_section()
        self._build_pattern_calib_section()
        console_section = self._build_console_section()

        self._connect_screen_signals()

        canvas_layout = QHBoxLayout()
        canvas_layout.addLayout(self.canvas_with_toolbar, stretch=3)
        canvas_layout.addWidget(sidebar, stretch=1)
        canvas_layout.addWidget(self.ruler_panel_widget, stretch=1)
        canvas_layout.addWidget(self.pattern_calib_sidebar_widget, stretch=1)

        canvas_widget = QWidget()
        canvas_widget.setLayout(canvas_layout)

        from PyQt5.QtWidgets import QSplitter
        v_splitter = QSplitter(Qt.Vertical)
        v_splitter.addWidget(canvas_widget)
        v_splitter.addWidget(console_section)
        
        # Mejoras de fluidez y visuales
        v_splitter.setOpaqueResize(True)
        v_splitter.setCollapsible(1, False) # Impide que la consola colapse por completo
        v_splitter.setStyleSheet(
            "QSplitter::handle { background: #3B4252; height: 6px; margin: 2px 0px; border-radius: 3px; }"
            "QSplitter::handle:hover { background: #A6E3A1; }"
        )
        
        # Asignar prioridad de expansión al canvas (índice 0)
        v_splitter.setStretchFactor(0, 1)
        v_splitter.setStretchFactor(1, 0)
        # Darle poco espacio a la consola inicialmente
        v_splitter.setSizes([800, 150])

        main_layout = QVBoxLayout()
        main_layout.addLayout(control_layout)
        main_layout.addWidget(v_splitter)
        self.setLayout(main_layout)

        self.apply_theme()

    # ═════════════════════════════════════════════════════════════════════════
    # ESTADO INICIAL DE LA UI
    # ═════════════════════════════════════════════════════════════════════════

    def _init_ui_state(self) -> None:
        """
        Inicializa variables de estado que dependen de widgets de la UI.
        Se separan de _init_state() porque sólo tienen sentido una vez que
        la ventana existe.
        """
        # Panning del canvas matplotlib
        self.panning      = False
        self.pan_start_pos = None

        # Imagen posicionada sobre el grid
        self.image_on_grid   = None
        self.image_position  = [0.0, 0.0]   # [x, y] en píxeles del grid (float)
        self.drag_mode       = "fixed"       # "fixed" (chunks) | "free" (píxel)
        self.dragging_image  = False
        self.drag_start_pos  = None

        # Grabación y reproducción de movimientos del stage
        self.recording          = False
        self.recorded_positions = []
        self.playback_active    = False
        self.playback_index     = 0
        self.playback_timer     = QTimer()
        self.playback_timer.timeout.connect(self.playback_step)

    # ═════════════════════════════════════════════════════════════════════════
    # PANEL LATERAL (SIDEBAR)
    # ═════════════════════════════════════════════════════════════════════════

    def _build_sidebar(self) -> QScrollArea:
        """
        Ensambla el panel lateral derecho llamando a cada constructor de sección
        en el orden en que deben aparecer visualmente, y los envuelve en un
        QScrollArea de ancho fijo.
        """
        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(SIDEBAR_SPACING)

        self._build_stats_section()            # 📊 DATA
        self._build_binary_section()           # ⚫⚪ BINARIO
        self.check_second_monitor()            # detecta monitor secundario al inicio
        self._build_grid_stats_section()       # 📏 ESTADÍSTICAS GRID
        self._build_basler_section()           # 🎥 CÁMARA BASLER
        self._build_image_coords_section()     # 🖼️ IMAGEN EN GRID
        self._build_grid_config_section()      # 📏 CONFIGURACIÓN GRID
        self._build_segmentation_section()     # ✂️ SEGMENTACIÓN DE IMAGEN
        self._build_motors_section()           # ⚙️ CONTROL DE MOTORES
        self.info_layout.addSpacing(SIDEBAR_SECTION_SPACING)
        self._build_exposure_frequency_tabs()  # ⏱️/〜 Tabs
        self._build_exposure_section()         # ⏱️ EXPOSICIÓN
        self._build_frequency_section()        # 〜 FRECUENCIA
        self._build_projection_section()       # 🎬 CONTROL DE PROYECCIÓN
        self._build_calibration_monitor()      # 🔍 MONITOREO DE CALIBRACIÓN
        self.info_layout.addSpacing(SIDEBAR_SECTION_SPACING)
        self._build_file_tree()                # 📁 ARCHIVOS

        info_widget = QWidget()
        info_widget.setLayout(self.info_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidget(info_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setMinimumWidth(SIDEBAR_MIN_WIDTH)
        scroll_area.setMaximumWidth(SIDEBAR_MAX_WIDTH)

        return scroll_area

    # ═════════════════════════════════════════════════════════════════════════
    # SEÑALES DE PANTALLA
    # ═════════════════════════════════════════════════════════════════════════

    def _connect_screen_signals(self) -> None:
        """
        Conecta las señales de Qt para detectar cambios de monitor en caliente
        (monitor secundario conectado, desconectado o con geometría cambiada)
        y realiza la detección inicial del estado de la pantalla.
        """
        app = QApplication.instance()
        app.screenAdded.connect(self.on_screen_changed)
        app.screenRemoved.connect(self.on_screen_changed)
        for screen in app.screens():
            screen.geometryChanged.connect(self.on_screen_changed)

        # Estado inicial
        self.on_screen_changed()
