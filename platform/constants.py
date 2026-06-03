"""
Constantes globales del Simulador de Litografía.

Centraliza colores, rutas, valores por defecto y configuración
para evitar strings/números mágicos dispersos en el código.
"""

# ─── Rutas y Archivos ────────────────────────────────────────────────
CACHE_DIR = "cache_photolith"
CONFIG_FILE = "file_structure.json"
GRID_CONFIG_FILE = "grid_config.json"
CALIBRATION_MATRIX_FILE = "calibration_matrix.npy"
CALIBRATION_CONFIG_FILE = "calibration_config.json"
APP_ICON = "icono.ico"

# ─── Ventana Principal ───────────────────────────────────────────────
WINDOW_TITLE = "Controlador Litografía Uandes"
WINDOW_MAX_WIDTH = 1400
WINDOW_MAX_HEIGHT = 900
WINDOW_WIDTH_RATIO = 0.9
WINDOW_HEIGHT_RATIO = 0.85

# ─── Colores del Tema Oscuro ─────────────────────────────────────────
DARK_BG_PRIMARY = "#121212"
DARK_BG_SECONDARY = "#1E1E1E"
DARK_BG_TERTIARY = "#2C2C2C"
DARK_BG_ELEVATED = "#2E2E2E"
DARK_BORDER = "#3E3E3E"
DARK_TEXT_PRIMARY = "#E0E0E0"
DARK_TEXT_SECONDARY = "#B0B0B0"
DARK_TEXT_MUTED = "#888888"

# ─── Colores del Tema Claro ──────────────────────────────────────────
LIGHT_BG_PRIMARY = "#FFFFFF"
LIGHT_BG_SECONDARY = "#F5F5F5"
LIGHT_BG_TERTIARY = "#E0E0E0"
LIGHT_BORDER = "#CCCCCC"
LIGHT_TEXT_PRIMARY = "#000000"
LIGHT_TEXT_SECONDARY = "#333333"

# ─── Colores de Acento ───────────────────────────────────────────────
ACCENT_TEAL = "#03DAC6"
ACCENT_TEAL_DARK = "#00BFA5"
ACCENT_TEAL_MUTED = "#00796B"
ACCENT_ORANGE = "#FF8C00"
ACCENT_RED = "#FF4444"
ACCENT_GREEN = "#4CAF50"

# ─── Configuración por Defecto del Grid ──────────────────────────────
DEFAULT_GRID_CONFIG = {
    "width": 10,
    "height": 10,
    "cell_size": 1,
    "pixels_per_cell": 100,
    "unit": "mm",
    "color": "#00FF00",
    "pixel_grid_color": "#FF00FF",
    "show_pixel_grid": False,
    "apply_effects_to_grid": False,
    "binary_mode_enabled": False,
    "binary_threshold": 50.0,
    "invert_projection": False,
}

# ─── Configuración por Defecto de Calibración / Basler ───────────────
DEFAULT_BASLER_EXPOSURE = 10000.0
DEFAULT_BASLER_GAIN = 0.0
DEFAULT_BASLER_WIDTH = 640
DEFAULT_BASLER_HEIGHT = 750
DEFAULT_BASLER_GAMMA = 1.0
DEFAULT_BASLER_BLACK_LEVEL = 0

DEFAULT_CALIBRATION_THRESHOLD = 50.0
DEFAULT_ATTENUATION_STRENGTH = 100.0
DEFAULT_ATTENUATION_METHOD = "normalized"

# ─── Configuración de Exposición ─────────────────────────────────────
DEFAULT_SIGMA = 1.0
DEFAULT_BRIGHTNESS = 100
DEFAULT_BINARY_THRESHOLD = 50.0
DEFAULT_DOWNSCALE_FACTOR = 1.0

# ─── Formatos de Imagen Soportados ───────────────────────────────────
IMAGE_FORMATS = ["PNG", "JPG", "BMP", "TIFF"]
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")

# ─── Colores Preset para Configuración de Grid ──────────────────────
PRESET_COLORS = [
    ("#00FF00", "Verde"),
    ("#FF0000", "Rojo"),
    ("#0000FF", "Azul"),
    ("#FFFF00", "Amarillo"),
    ("#FF00FF", "Magenta"),
    ("#00FFFF", "Cian"),
    ("#FFFFFF", "Blanco"),
]

# ─── Límites del Pixel Grid ──────────────────────────────────────────
MAX_PIXEL_GRID_LINES = 1000

# ─── Windows API ─────────────────────────────────────────────────────
DWMWA_USE_IMMERSIVE_DARK_MODE = 20

# ═════════════════════════════════════════════════════════════════════════
# UI LAYOUT — Dimensiones fijas de widgets
# ═════════════════════════════════════════════════════════════════════════

SIDEBAR_MIN_WIDTH = 420
SIDEBAR_MAX_WIDTH = 550
SIDEBAR_SPACING = 12
SIDEBAR_SECTION_SPACING = 20

SECTION_CONTENT_MARGINS = (12, 12, 12, 12)
SECTION_CONTENT_SPACING = 8
SECTION_CONTENT_SPACING_WIDE = 10
SECTION_CONTENT_SPACING_EXTRA = 12

CONSOLE_MAX_HEIGHT = 150
CONSOLE_CONTENT_MARGINS = (5, 5, 5, 5)

FILE_TREE_ICON_SIZE = 56
FILE_TREE_MIN_WIDTH = 280
FILE_TREE_MIN_HEIGHT = 400

INPUT_FIELD_MAX_WIDTH = 80
INPUT_FIELD_NARROW_MAX_WIDTH = 50
INPUT_FIELD_CAMERA_MAX_WIDTH = 70

BUTTON_MIN_HEIGHT_STANDARD = 32
BUTTON_MIN_HEIGHT_LARGE = 35
BUTTON_MIN_HEIGHT_XLARGE = 40

# ═════════════════════════════════════════════════════════════════════════
# UI LAYOUT — Motor Pad
# ═════════════════════════════════════════════════════════════════════════

MOTOR_PAD_BUTTON_SIZE = 45
MOTOR_PAD_SPACING = 10
MOTOR_STEPS_RANGE = (1, 10_000)
MOTOR_STEPS_DEFAULT = 1
MOTOR_INTERVAL_RANGE = (10, 2_000)
MOTOR_INTERVAL_DEFAULT = 100

# ═════════════════════════════════════════════════════════════════════════
# UI LAYOUT — Calibration Preview
# ═════════════════════════════════════════════════════════════════════════

CALIB_PREVIEW_FIGSIZE = (3, 2)
CALIB_PREVIEW_DPI = 80
CALIB_PREVIEW_MIN_HEIGHT = 150
CALIB_PREVIEW_MAX_HEIGHT = 200
CALIB_PREVIEW_STRENGTH_DEFAULT = 100
CALIB_PREVIEW_STRENGTH_MIN_WIDTH = 35

# ═════════════════════════════════════════════════════════════════════════
# UI RANGES — Basler Camera Sliders
# ═════════════════════════════════════════════════════════════════════════

BASLER_EXPOSURE_SLIDER_MIN = 100
BASLER_EXPOSURE_SLIDER_MAX = 1_000_000
BASLER_EXPOSURE_SLIDER_DEFAULT = 10_000
BASLER_GAIN_SLIDER_MIN = 0
BASLER_GAIN_SLIDER_MAX = 240  # ×10 → represents 0.0–24.0 dB
BASLER_GAIN_SLIDER_DEFAULT = 0
BASLER_GAMMA_SLIDER_MIN = 10
BASLER_GAMMA_SLIDER_MAX = 40   # ×10 → represents 1.0–4.0
BASLER_GAMMA_SLIDER_DEFAULT = 10
BASLER_BLACK_SLIDER_MIN = 0
BASLER_BLACK_SLIDER_MAX = 255
BASLER_BLACK_SLIDER_DEFAULT = 0

# ═════════════════════════════════════════════════════════════════════════
# UI RANGES — Exposure & Frequency Controls
# ═════════════════════════════════════════════════════════════════════════

SIGMA_SLIDER_MIN = 1
SIGMA_SLIDER_MAX = 30
BRIGHTNESS_SLIDER_MIN = 0
BRIGHTNESS_SLIDER_MAX = 100
BINARY_THRESHOLD_SLIDER_MIN = 0
BINARY_THRESHOLD_SLIDER_MAX = 100

ROTATION_SLIDER_MIN = 0
ROTATION_SLIDER_MAX = 360
ROTATION_TICK_INTERVAL = 45

DOWNSCALE_SPIN_MIN = 0.1
DOWNSCALE_SPIN_MAX = 10.0
DOWNSCALE_SPIN_DEFAULT = 1.0
DOWNSCALE_SPIN_STEP = 0.1
DOWNSCALE_SPIN_DECIMALS = 2

EXPOSURE_TIME_SPIN_MIN = 0.001
EXPOSURE_TIME_SPIN_MAX = 60.0
EXPOSURE_TIME_SPIN_DEFAULT = 0.5
EXPOSURE_TIME_SPIN_STEP = 0.1
EXPOSURE_TIME_SPIN_DECIMALS = 3

MOVEMENT_TIME_SPIN_MIN = 0.0
MOVEMENT_TIME_SPIN_MAX = 60.0
MOVEMENT_TIME_SPIN_DEFAULT = 0.2
MOVEMENT_TIME_SPIN_STEP = 0.1
MOVEMENT_TIME_SPIN_DECIMALS = 3

PROGRESS_BAR_MAX_HEIGHT = 15

# ═════════════════════════════════════════════════════════════════════════
# UI RANGES — Segmentation
# ═════════════════════════════════════════════════════════════════════════

SEGMENTS_SPIN_MIN = 1
SEGMENTS_SPIN_MAX = 100
SEGMENTS_SPIN_DEFAULT = 4

# ═════════════════════════════════════════════════════════════════════════
# UI STYLES — Inline CSS extracted to constants
# ═════════════════════════════════════════════════════════════════════════

STYLE_BOLD_11PX = "font-weight: bold; font-size: 11px;"
STYLE_MUTED_10PX = "font-size: 10px; color: #888888;"
STYLE_BOLD_10PX = "font-weight: bold; font-size: 10px; margin-top: 5px;"
STYLE_SMALL_10PX = "font-size: 10px;"
STYLE_UNIT_10PX = "font-size: 10px;"
STYLE_BOLD_MARGIN_TOP = "font-weight: bold; margin-top: 10px;"
STYLE_BOLD = "font-weight: bold;"
STYLE_MARGIN_TOP_10 = "margin-top: 10px;"

STYLE_MOTOR_STATUS_DISCONNECTED = "color: #F44336; font-weight: bold;"
STYLE_MOTOR_PULSE_TITLE = "font-weight: bold; margin-top: 5px;"

STYLE_MOTOR_PAD_BUTTON = """
    QPushButton {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #03DAC6, stop:1 #018786);
        border: none; border-radius: 8px;
        color: #121212; font-weight: bold; font-size: 16px; padding: 0px;
    }
    QPushButton:hover {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #00E5CC, stop:1 #01A299);
    }
    QPushButton:pressed {
        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
            stop:0 #018786, stop:1 #016968);
    }
"""

# ═════════════════════════════════════════════════════════════════════════
# UI TEXTS — Segmentation mode labels
# ═════════════════════════════════════════════════════════════════════════

SEGMENTATION_MODES = [
    "Automático (usar grid)",
    "Manual (especificar)",
    "Por tamaño de campo",
    "Imagen Completa (sin slice)",
]

FREQUENCY_UNITS = ["Hz", "kHz", "MHz"]
GRID_UNITS = ["nm", "µm", "mm", "cm", "m"]
DRAG_MODES = ["Fixed (Chunks)", "Free (Píxel)"]

MOTOR_PAD_AUTOREPEAT_DELAY = 300
