import numpy as np
import cv2
from scipy.ndimage import convolve
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter

# -----------------------------
# 1. Cargar patrón de entrada
# -----------------------------
# Cargar una imagen binaria (blanco = 1, negro = 0)
pattern = cv2.imread('patron.png', cv2.IMREAD_GRAYSCALE)
pattern = pattern / 255.0  # Normalizar entre 0 y 1

# -----------------------------
# 2. Definir PSF (Gaussiana)
# -----------------------------
# Simula la difracción/desenfoque del sistema óptico
psf_sigma = 2.0  # Ajusta según resolución del sistema
simulated_intensity = gaussian_filter(pattern, sigma=psf_sigma)

# -----------------------------
# 3. Análisis de intensidad por píxel
# -----------------------------
intensity_percentage = (simulated_intensity / simulated_intensity.max()) * 100

# -----------------------------
# 4. Visualización
# -----------------------------
plt.figure(figsize=(12, 6))

plt.subplot(1, 2, 1)
plt.title("Patrón de entrada")
plt.imshow(pattern, cmap='gray')
plt.colorbar(label='Intensidad normalizada')

plt.subplot(1, 2, 2)
plt.title("Mapa de intensidad simulado")
plt.imshow(simulated_intensity, cmap='hot')
plt.colorbar(label='Intensidad simulada')

plt.show()

# -----------------------------
# 5. Ejemplo de inspección de un píxel
# -----------------------------
x, y = 50, 50  # Coordenadas de ejemplo
print(f"Intensidad simulada en ({x},{y}): {simulated_intensity[y, x]:.3f}")
print(f"Porcentaje respecto al máximo: {intensity_percentage[y, x]:.2f}%")
