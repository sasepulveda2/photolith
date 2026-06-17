"""
Simulador de Litografia Uandes V1.1

Clase principal LithographySimulator que compone funcionalidad
a traves de mixins tematicos. Este archivo contiene unicamente
la definicion de clase, inicializacion de estado y el punto de
composicion de los mixins.

Mixins:
    - UISetupMixin:            Construccion de la interfaz grafica
    - CalibrationUIMixin:      Interfaz de calibracion
    - CameraMixin:             Control de camaras USB y Basler
    - IntensityAnalysisMixin:  Analisis de brillo y uniformidad
    - AttenuationMixin:        Matrices de compensacion
    - GridMixin:               Generacion/display del grid litografico
    - ProjectionMixin:         Exposicion, frecuencia y secuencias
    - ImageProcessingMixin:    Simulacion optica y procesamiento de imagen
    - FileManagementMixin:     Cache, arbol de archivos y persistencia
    - PreferencesMixin:        Dialogos de configuracion
    - ThemeMixin:              Temas visual, consola y eventos de ventana
"""
import os

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon

from constants import (
    CACHE_DIR, WINDOW_TITLE, WINDOW_MAX_WIDTH, WINDOW_MAX_HEIGHT,
    WINDOW_WIDTH_RATIO, WINDOW_HEIGHT_RATIO, APP_ICON,
    DEFAULT_SIGMA, DEFAULT_BRIGHTNESS, DEFAULT_BINARY_THRESHOLD,
    DEFAULT_DOWNSCALE_FACTOR, DEFAULT_BASLER_EXPOSURE, DEFAULT_BASLER_GAIN,
    DEFAULT_BASLER_WIDTH, DEFAULT_BASLER_HEIGHT, DEFAULT_BASLER_GAMMA,
    DEFAULT_BASLER_BLACK_LEVEL, DEFAULT_CALIBRATION_THRESHOLD,
    DEFAULT_ATTENUATION_STRENGTH, DEFAULT_ATTENUATION_METHOD,
)
from mixins import (
    CalibrationUIMixin,
    CameraMixin,
    IntensityAnalysisMixin,
    AttenuationMixin,
    GridMixin,
    ProjectionMixin,
    ImageProcessingMixin,
    FileManagementMixin,
    PreferencesMixin,
    ThemeMixin,
    UISetupMixin,
    SpatialCalibrationMixin,
    RulerScaleMixin,
)


class LithographySimulator(
    UISetupMixin,
    CalibrationUIMixin,
    CameraMixin,
    IntensityAnalysisMixin,
    AttenuationMixin,
    GridMixin,
    ProjectionMixin,
    ImageProcessingMixin,
    FileManagementMixin,
    PreferencesMixin,
    ThemeMixin,
    SpatialCalibrationMixin,
    RulerScaleMixin,
    QWidget,
):
    """
    Controlador principal del simulador de litografia.

    Compone funcionalidad de 12 mixins especializados.
    El estado se inicializa en _init_state() y la interfaz
    se construye en _build_ui() (UISetupMixin).
    """

    def __init__(self):
        super().__init__()
        self._init_state()
        self._init_spatial_calibration()
        self._init_ruler_scale()
        self._build_ui()

    def _init_state(self):
        """Inicializa todas las variables de estado del simulador."""
        self.setWindowTitle(WINDOW_TITLE)

        from PyQt5.QtWidgets import QDesktopWidget
        screen = QDesktopWidget().availableGeometry()
        width = min(WINDOW_MAX_WIDTH, int(screen.width() * WINDOW_WIDTH_RATIO))
        height = min(WINDOW_MAX_HEIGHT, int(screen.height() * WINDOW_HEIGHT_RATIO))
        self.resize(width, height)
        self.setAcceptDrops(True)

        icon_path = os.path.join(os.path.dirname(__file__), APP_ICON)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.set_dark_titlebar()

        # ── Imagen y Optica ──────────────────────────────────────
        self.pattern = None
        self.sigma = DEFAULT_SIGMA
        self.brightness = DEFAULT_BRIGHTNESS
        self.invert_projection = False
        
        self.physical_segment_width = 10.0
        self.physical_segment_height = 10.0
        self.binary_threshold = DEFAULT_BINARY_THRESHOLD
        self.binary_mode_enabled = False
        self.downscale_factor = DEFAULT_DOWNSCALE_FACTOR

        # ── Cache y Rutas ────────────────────────────────────────
        self.cache_dir = CACHE_DIR
        self.config_file = os.path.join(self.cache_dir, "file_structure.json")
        self.grid_config_file = os.path.join(CACHE_DIR, "grid_config.json")
        self.calibration_file = os.path.join(CACHE_DIR, "calibration_matrix.npy")
        self.calibration_config_file = os.path.join(CACHE_DIR, "calibration_config.json")

        # ── Tema y UI ────────────────────────────────────────────
        self.dark_mode = True
        self.show_projection_image = True

        # ── Proyector ────────────────────────────────────────────
        self.projector_active = False
        self.projection_window = None
        self.has_second_monitor = self.check_second_monitor()
        self.scale_mode = "automatic"
        self.scale_percentage = 100
        self.current_scale_info = {
            "original": (0, 0),
            "scaled": (0, 0),
            "percentage": 0,
        }

        # ── Grid ─────────────────────────────────────────────────
        self.grid_view_active = False
        self.load_grid_config()
        self.apply_effects_to_grid = False
        self.panning = False
        self.pan_start_pos = None

        # ── Calibracion ──────────────────────────────────────────
        self.calibration_view_active = False
        self.calibration_source = "camera"
        self.calibration_camera = None
        self.basler_camera = None
        self.basler_converter = None
        self.calibration_image = None
        self.calibration_grayscale = None
        self.calibration_intensity_data = None
        self.current_zone_grid = "4x4"

        self.basler_exposure = DEFAULT_BASLER_EXPOSURE
        self.basler_gain = DEFAULT_BASLER_GAIN
        self.basler_width = DEFAULT_BASLER_WIDTH
        self.basler_height = DEFAULT_BASLER_HEIGHT
        self.basler_offset_x = 0
        self.basler_offset_y = 0
        self.basler_gamma = DEFAULT_BASLER_GAMMA
        self.basler_black_level = DEFAULT_BASLER_BLACK_LEVEL

        self.calibration_threshold = DEFAULT_CALIBRATION_THRESHOLD
        self.attenuation_matrix = None
        self.attenuation_strength = DEFAULT_ATTENUATION_STRENGTH
        self.attenuation_method = DEFAULT_ATTENUATION_METHOD
        self.apply_attenuation_to_grid = False
        self.calibration_flip_x = False
        self.calibration_flip_y = False

        self.load_calibration_data()

        # ── Exposicion ───────────────────────────────────────────
        self.exposure_timer = QTimer()
        self.exposure_timer.timeout.connect(self.stop_timed_exposure)
        self.exposure_active = False
        self.exposure_start_time = 0.0
        self.exposure_duration = 0.0
        self.exposure_cycles_completed = 0
        self.exposure_target_brightness = 0.0
        self.inter_cycle_delay = 0
        self.final_brightness_mode = "zero"

        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.setInterval(100)

        self.inter_cycle_timer = QTimer()
        self.inter_cycle_timer.setSingleShot(True)
        self.inter_cycle_timer.timeout.connect(self.resume_next_cycle)

        # ── Frecuencia ───────────────────────────────────────────
        self.frequency_mode = False
        self.frequency_timer = QTimer()
        self.frequency_timer.timeout.connect(self.stop_frequency_mode)
        self.frequency_start_time = 0.0
        self.frequency_duration = 0.0

        # ── Secuencias y Segmentacion ────────────────────────────
        self.current_projecting_segment = None
        self.sequence_running = False
        self.sequence_paused = False
        self.current_segment_index = 0
        self.total_segments = 0
        self.sequence_timer = None
        self.image_segments = []
        self.segments_x = 4
        self.segments_y = 4
        self.show_segments_overlay = False
        self.segmentation_mode = 0
        self.show_heatmap = False

        # ── Cache de Segmentacion ────────────────────────────────
        self._pattern_load_id = None
        self._last_segmentation_pattern_id = None
        self._last_segmentation_bounds = None
        self._last_segmentation_grid_config = None
        self._last_image_position = None

        # ── Transformaciones de Imagen ───────────────────────────
        self.image_rotation = 0
        self.image_mirror_h = False
        self.image_mirror_v = False

        # ── Sistema de Archivos ──────────────────────────────────
        self.init_cache_system()

        # ── Motores ──────────────────────────────────────────────
        self.motor_gui = None
        self.motor_controller_instance = None
        self.load_motor_sidebar_settings()

    def toggle_motors_view(self):
        """Muestra u oculta la vista principal de motores y sus preferencias."""
        if not hasattr(self, '_motors_view_active'):
            self._motors_view_active = False
            
        if not self._motors_view_active:
            # Al encender la vista, comprobar si está instanciada
            if self.motor_gui is None:
                # Importación lazy para no ralentizar el inicio
                from motors.main import load_settings, seleccionar_puerto_y_baud, save_settings, puerto_key
                from motors.motor_controller import CrealityController
                from motors.gui import MotorGUI, MotorPreferencesGUI
                from PyQt5.QtWidgets import QMessageBox

                if getattr(self, "motor_controller_instance", None) is None:
                    self.connect_motors_sidebar()

                controller = getattr(self, "motor_controller_instance", None)
                if controller is None:
                    # Si sigue siendo None, la conexión falló o el usuario canceló
                    return

                settings = load_settings()

                def guardar_posiciones(positions):
                    settings["positions"] = positions
                    save_settings(settings)

                def guardar_ultimo_movimiento(movement):
                    settings["last_movement"] = movement
                    save_settings(settings)

                def guardar_mapping(mapping):
                    settings["mapping"] = mapping
                    save_settings(settings)
                    
                def guardar_steps_360(steps):
                    settings["steps_360"] = steps
                    save_settings(settings)
                    
                def guardar_feedrates(feedrates):
                    settings["feedrates"] = feedrates
                    save_settings(settings)

                def guardar_max_feedrates(max_feedrates):
                    settings["max_feedrates"] = max_feedrates
                    save_settings(settings)

                def guardar_limites(limits):
                    settings["limits"] = limits
                    save_settings(settings)
                    
                def guardar_limits_enabled(enabled):
                    settings["limits_enabled"] = enabled
                    save_settings(settings)
                    
                def guardar_arrow_axis(axis):
                    settings["arrow_updown_axis"] = axis
                    save_settings(settings)
                    # Sincronizar con MotorGUI
                    if hasattr(self, "motor_gui"):
                        self.motor_gui.arrow_updown_axis = axis
                    
                def guardar_backlash_steps(steps):
                    settings["backlash_steps"] = steps
                    save_settings(settings)
                    
                def guardar_backlash_enabled(enabled):
                    settings["backlash_enabled"] = enabled
                    save_settings(settings)

                def guardar_keyboard_mode(mode):
                    settings["keyboard_mode"] = mode
                    save_settings(settings)
                    # Sincronizar con MotorGUI
                    if hasattr(self, "motor_gui"):
                        self.motor_gui.keyboard_mode = mode

                controller.on_positions_changed = guardar_posiciones
                controller.on_last_movement_changed = guardar_ultimo_movimiento
                controller.on_limits_changed = guardar_limites
                controller.on_limits_enabled_changed = guardar_limits_enabled
                
                # Apply backlash settings to controller
                controller.backlash = settings.get("backlash_steps", {"X": 0, "Y": 0, "Z": 0, "E": 0})
                controller.backlash_enabled = settings.get("backlash_enabled", True)

                # Instanciamos el MotorGUI en el centro
                self.motor_gui = MotorGUI(
                    controller, 
                    mapping=settings.get("mapping"), 
                    on_mapping_changed=guardar_mapping,
                    steps_360=settings.get("steps_360"),
                    on_steps_360_changed=guardar_steps_360,
                    feedrates=settings.get("feedrates"),
                    on_feedrates_changed=guardar_feedrates,
                    arrow_updown_axis=settings.get("arrow_updown_axis", "Y"),
                    keyboard_mode=settings.get("keyboard_mode", "set_movement")
                )
                from PyQt5.QtCore import Qt
                self.motor_gui.setMaximumWidth(900)
                self.motor_central_layout.addWidget(self.motor_gui, alignment=Qt.AlignCenter)
                
                # Instanciamos el MotorPreferencesGUI en el sidebar
                self.motor_prefs_gui = MotorPreferencesGUI(
                    controller,
                    mapping=settings.get("mapping"), 
                    on_mapping_changed=guardar_mapping,
                    steps_360=settings.get("steps_360"),
                    on_steps_360_changed=guardar_steps_360,
                    feedrates=settings.get("feedrates"),
                    on_feedrates_changed=guardar_feedrates,
                    max_feedrates=settings.get("max_feedrates"),
                    on_max_feedrates_changed=guardar_max_feedrates,
                    arrow_updown_axis=settings.get("arrow_updown_axis", "Y"),
                    on_arrow_axis_changed=guardar_arrow_axis,
                    backlash_steps=settings.get("backlash_steps", {"X": 0, "Y": 0, "Z": 0, "E": 0}),
                    on_backlash_steps_changed=guardar_backlash_steps,
                    backlash_enabled=settings.get("backlash_enabled", True),
                    on_backlash_enabled_changed=guardar_backlash_enabled,
                    keyboard_mode=settings.get("keyboard_mode", "set_movement"),
                    on_keyboard_mode_changed=guardar_keyboard_mode
                )
                self.motors_panel_layout.addWidget(self.motor_prefs_gui)

            # Activar Vista Motores
            self._motors_view_active = True
            if hasattr(self, "motors_button"):
                self.motors_button.setText("Volver al editor")

            # Desactivar otras vistas
            if getattr(self, "grid_view_active", False):
                self.toggle_grid_view()
            if getattr(self, "calibration_view_active", False):
                self.toggle_calibration_view()
            if getattr(self, "_ruler_scale_view_active", False):
                self.toggle_ruler_scale_view()
            if getattr(self, "_pattern_calib_view_active", False):
                self.toggle_pattern_calibration_view()
            if getattr(self, "_proyecciones_view_active", False):
                self.toggle_proyecciones_view()

            # Ocultar canvas normal y sidebar normal
            if hasattr(self, "canvas_container"):
                self.canvas_container.setVisible(False)
            if hasattr(self, "_main_sidebar"):
                self._main_sidebar.setVisible(False)
            if hasattr(self, "ruler_panel_widget"):
                self.ruler_panel_widget.setVisible(False)

            # Mostrar panels de motores
            if hasattr(self, "motor_central_widget"):
                self.motor_central_widget.setVisible(True)
            if hasattr(self, "motors_panel_widget"):
                self.motors_panel_widget.setVisible(True)

        else:
            # Desactivar Vista Motores
            self._motors_view_active = False
            if hasattr(self, "motors_button"):
                self.motors_button.setText("Motores")
            
            # Ocultar panels de motores
            if hasattr(self, "motor_central_widget"):
                self.motor_central_widget.setVisible(False)
            if hasattr(self, "motors_panel_widget"):
                self.motors_panel_widget.setVisible(False)
                
            # Mostrar canvas normal y sidebar normal
            if hasattr(self, "canvas_container"):
                self.canvas_container.setVisible(True)
            if hasattr(self, "_main_sidebar"):
                self._main_sidebar.setVisible(True)

    def toggle_proyecciones_view(self):
        """Muestra u oculta la vista de Proyecciones."""
        if not hasattr(self, "_proyecciones_view_active"):
            self._proyecciones_view_active = False

        if not getattr(self, "_proyecciones_view_active", False):
            # Activar Vista Proyecciones
            self._proyecciones_view_active = True
            if hasattr(self, "btn_proyecciones"):
                self.btn_proyecciones.setText(" Volver al editor")
                self.btn_proyecciones.setChecked(True)

            # Desactivar otras vistas
            if getattr(self, "_motors_view_active", False):
                self.toggle_motors_view()
            if getattr(self, "grid_view_active", False):
                self.toggle_grid_view()
            if getattr(self, "calibration_view_active", False):
                self.toggle_calibration_view()
            if getattr(self, "_ruler_scale_view_active", False):
                self.toggle_ruler_scale_view()
            if getattr(self, "_pattern_calib_view_active", False):
                self.toggle_pattern_calibration_view()

            # Ocultar canvas normal y sidebar normal
            if hasattr(self, "canvas_container"):
                self.canvas_container.setVisible(False)
            if hasattr(self, "_main_sidebar"):
                self._main_sidebar.setVisible(False)

            # Mostrar panel de proyecciones
            if not hasattr(self, "proyecciones_panel_widget"):
                from UI.sections.proyecciones_panel import ProyeccionesGUI
                self.proyecciones_panel_widget = ProyeccionesGUI(main_app=self, controller=getattr(self, "motor_controller_instance", None))
                if hasattr(self, "proyecciones_central_layout"):
                    self.proyecciones_central_layout.addWidget(self.proyecciones_panel_widget)
            
            if hasattr(self, "proyecciones_central_widget"):
                self.proyecciones_central_widget.setVisible(True)

        else:
            # Desactivar Vista Proyecciones
            self._proyecciones_view_active = False
            if hasattr(self, "btn_proyecciones"):
                self.btn_proyecciones.setText(" Proyecciones")
                self.btn_proyecciones.setChecked(False)
            
            # Ocultar panel de proyecciones
            if hasattr(self, "proyecciones_central_widget"):
                self.proyecciones_central_widget.setVisible(False)
                
            # Mostrar canvas normal y sidebar normal
            if hasattr(self, "canvas_container"):
                self.canvas_container.setVisible(True)
            if hasattr(self, "_main_sidebar"):
                self._main_sidebar.setVisible(True)

    # ═══════════════════════════════════════════════════════════════════════════
    # LÓGICA DE CONTROLADORES DE MOTOR (SIDEBAR INTEGRADA)
    # ═══════════════════════════════════════════════════════════════════════════
    def load_motor_sidebar_settings(self):
        """Carga la configuración de pasos e intervalo desde motor_settings.json."""
        try:
            from motors.main import load_settings
            settings = load_settings()
            self._motor_sidebar_steps = float(settings.get("sidebar_steps", 1.0))
            self._motor_sidebar_interval = int(settings.get("sidebar_interval", 100))
            self._motor_sidebar_unit = settings.get("sidebar_unit", "Steps")
        except ImportError:
            self._motor_sidebar_steps = 1.0
            self._motor_sidebar_interval = 100
            self._motor_sidebar_unit = "Steps"

        # Asignar a la UI si ya está construida
        if hasattr(self, 'motor_steps_spin'):
            self.motor_steps_spin.setValue(self._motor_sidebar_steps)
        if hasattr(self, 'motor_unit_combo'):
            self.motor_unit_combo.setCurrentText(self._motor_sidebar_unit)
        if hasattr(self, 'motor_interval_spin'):
            self.motor_interval_spin.setValue(self._motor_sidebar_interval)
            self.update_motor_autorepeat_settings(self._motor_sidebar_interval)

    def save_motor_sidebar_settings(self):
        """Guarda la configuración de pulsos en memoria."""
        if not hasattr(self, 'motor_steps_spin'):
            return
            
        steps = self.motor_steps_spin.value()
        interval = self.motor_interval_spin.value()
        
        self._motor_sidebar_steps = steps
        self._motor_sidebar_interval = interval
        
        try:
            from motors.main import load_settings, save_settings
            settings = load_settings()
            settings["sidebar_steps"] = float(steps)
            settings["sidebar_interval"] = int(interval)
            if hasattr(self, "motor_unit_combo"):
                settings["sidebar_unit"] = self.motor_unit_combo.currentText()
            save_settings(settings)
        except ImportError:
            pass

    def update_motor_autorepeat_settings(self, interval):
        """Actualiza el tiempo de autorepetencia de los botones fluidos."""
        if hasattr(self, 'motor_buttons'):
            for btn in self.motor_buttons:
                btn.setAutoRepeatInterval(interval)
        self.save_motor_sidebar_settings()

    def connect_motors_sidebar(self):
        """Intenta conectar el controlador directamente a la ventana principal."""
        self.motors_sidebar_status.setText("Conectando...")
        self.motors_sidebar_status.setStyleSheet("color: #FFC107; font-weight: bold;")
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()
        
        from motors.main import load_settings, seleccionar_puerto_y_baud, save_settings, puerto_key
        from motors.motor_controller import CrealityController
        from PyQt5.QtWidgets import QMessageBox
        
        settings = load_settings()
        puerto, baud = seleccionar_puerto_y_baud(settings)

        if not puerto:
            self.motors_sidebar_status.setText("Desconectado")
            self.motors_sidebar_status.setStyleSheet("color: #F44336; font-weight: bold;")
            return

        self.motor_controller_instance = CrealityController(
            puerto.device, 
            baud=baud,
            initial_positions=settings.get("positions", {}),
            mapping=settings.get("mapping")
        )
        self.motor_controller_instance.limits_enabled = settings.get("limits_enabled", False)
        self.motor_controller_instance.limits = settings.get("limits", {"X": None, "Y": None, "Z": None, "E": None})
        
        def save_limits(limits):
            settings["limits"] = limits
            save_settings(settings)
            
        def save_limits_enabled(enabled):
            settings["limits_enabled"] = enabled
            save_settings(settings)
            
        self.motor_controller_instance.on_limits_changed = save_limits
        self.motor_controller_instance.on_limits_enabled_changed = save_limits_enabled
        
        if not self.motor_controller_instance.connect():
            self.motors_sidebar_status.setText("Fallo Conexión")
            self.motors_sidebar_status.setStyleSheet("color: #F44336; font-weight: bold;")
            QMessageBox.critical(self, "Error de Conexión", f"No se pudo conectar a la placa en {puerto.device}.")
            self.motor_controller_instance = None
            return

        settings["port_identity"] = puerto_key(puerto)
        settings["baud"] = baud
        save_settings(settings)

        self.motors_sidebar_status.setText("Conectado (Listo)")
        self.motors_sidebar_status.setStyleSheet("color: #A0A0A0; font-weight: bold;")
        self.log_to_console(f" Hardware Motor conectado en {puerto.device}", "SUCCESS")

    def execute_sidebar_motor_move(self, axis, direction):
        """Ejecuta un movimiento utilizando la configuración de pasos fluida."""
        if self.motor_controller_instance is None:
            # Intentar conectar automáticamente la primera vez
            self.connect_motors_sidebar()
            if self.motor_controller_instance is None:
                return
                
        try:
            from motors.main import load_settings
            settings = load_settings()
            steps_360 = settings.get("steps_360", {"X": 3200, "Y": 3200, "Z": 640, "E": 3200})
        except ImportError:
            steps_360 = {"X": 3200, "Y": 3200, "Z": 640, "E": 3200}
            
        valor = self.motor_steps_spin.value()
        unidad = "Steps"
        if hasattr(self, "motor_unit_combo"):
            unidad = self.motor_unit_combo.currentText()
            
        steps_per_rev = steps_360.get(axis, 3200)
        steps_per_mm = 2 * steps_per_rev
        
        if unidad == "mm":
            steps_totales = int(round(valor * steps_per_mm)) * direction
        else:
            steps_totales = int(valor) * direction
        
        try:
            self.motor_controller_instance.step_move(axis, steps_totales, 1)
        except ValueError as ve:
            # Límite de seguridad alcanzado
            self.log_to_console(f"Motor {axis} bloqueado: {str(ve)}", "WARNING")
        except Exception:
            self.motors_sidebar_status.setText("Reconectando...")
            self.motors_sidebar_status.setStyleSheet("color: #FFC107; font-weight: bold;")
            
            if self.motor_controller_instance.reconnect():
                self.motors_sidebar_status.setText("Conectado (Listo)")
                self.motors_sidebar_status.setStyleSheet("color: #A0A0A0; font-weight: bold;")
                # Reintentar el comando
                self.motor_controller_instance.step_move(axis, steps_totales, 1)
            else:
                self.motors_sidebar_status.setText("Fallo Conexión")
                self.motors_sidebar_status.setStyleSheet("color: #F44336; font-weight: bold;")
                self.motor_controller_instance = None

    def emergency_stop_sidebar(self):
        """Dispara el botón de emergencia en el motor."""
        if hasattr(self, 'motor_controller_instance') and self.motor_controller_instance:
            self.motor_controller_instance.emergency_stop()
            self.log_to_console("PARADA DE EMERGENCIA ENVIADA A MOTORES", "ERROR")
