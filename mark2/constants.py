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
WINDOW_TITLE = "Simulador Litografía Uandes V1.1"
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
