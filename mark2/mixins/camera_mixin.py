"""
Mixin de control de camaras.

Gestiona camaras USB (OpenCV) y camaras industriales Basler (pypylon),
incluyendo captura de frames, ajuste de exposicion, ganancia, gamma
y nivel de negro.
"""
import cv2

try:
    from pypylon import pylon
    BASLER_AVAILABLE = True
except ImportError:
    BASLER_AVAILABLE = False
    pylon = None

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QTimer


class CameraMixin:
    """Control de camaras USB y Basler."""

    def refresh_available_cameras(self):
        """Detecta y lista las cámaras disponibles."""
        self.camera_combo.clear()

        # Intentar detectar cámaras (solo 0-2 para evitar errores)
        # Usar CAP_DSHOW en Windows para detección más rápida y silenciosa
        available_cameras = []

        # Suprimir temporalmente warnings de OpenCV durante detección
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for i in range(3):  # Reducido a 3 para evitar búsquedas innecesarias
                try:
                    # Usar DirectShow en Windows para evitar errores de obsensor
                    cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                    if cap.isOpened():
                        # Verificar que realmente puede leer frames
                        ret, _ = cap.read()
                        if ret:
                            available_cameras.append(i)
                    cap.release()
                except Exception:
                    pass  # Ignorar errores silenciosamente

        if available_cameras:
            for cam_id in available_cameras:
                self.camera_combo.addItem(f"Cámara {cam_id}", cam_id)
            self.log_to_console(
                f"{len(available_cameras)} cámara(s) detectada(s)", "SUCCESS"
            )
        else:
            self.camera_combo.addItem("No se detectaron cámaras", -1)
            self.log_to_console("No se detectaron cámaras conectadas", "INFO")



    def toggle_camera_capture(self):
        """Inicia o detiene la captura de cámara."""
        if self.calibration_camera is None:
            self.start_camera_capture()
        else:
            self.stop_camera_capture()



    def start_camera_capture(self):
        """Inicia la captura desde la cámara seleccionada."""
        camera_id = self.camera_combo.currentData()

        if camera_id == -1:
            QMessageBox.warning(self, "Error", "No hay cámaras disponibles")
            return

        # Usar DirectShow en Windows para evitar errores de obsensor
        try:
            self.calibration_camera = cv2.VideoCapture(camera_id, cv2.CAP_DSHOW)
        except Exception:
            self.calibration_camera = cv2.VideoCapture(camera_id)

        if not self.calibration_camera.isOpened():
            QMessageBox.warning(
                self, "Error", f"No se pudo abrir la cámara {camera_id}"
            )
            self.calibration_camera = None
            return

        # Cambiar botón
        self.start_camera_button.setText("⏹️ Detener Cámara")

        # Iniciar timer para actualizar frames
        if not hasattr(self, "camera_timer"):
            self.camera_timer = QTimer()
            self.camera_timer.timeout.connect(self.update_camera_frame)

        self.camera_timer.start(33)  # ~30 FPS



    def stop_camera_capture(self):
        """Detiene la captura de cámara."""
        if hasattr(self, "camera_timer"):
            self.camera_timer.stop()

        if self.calibration_camera is not None:
            self.calibration_camera.release()
            self.calibration_camera = None

        self.start_camera_button.setText("▶️ Iniciar Cámara")



    def update_camera_frame(self):
        """Actualiza el frame de la cámara en la vista previa."""
        if self.calibration_camera is None:
            return

        ret, frame = self.calibration_camera.read()

        if ret:
            # Convertir de BGR a RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Guardar como imagen de calibración actual
            self.calibration_image = frame_rgb

            # Generar versión en escala de grises
            self.calibration_grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Actualizar vista previa en pestaña 1
            self.calib_preview_ax.clear()
            self.calib_preview_ax.imshow(frame_rgb)
            self.calib_preview_ax.axis("off")
            self.calib_preview_canvas.draw_idle()

            # Actualizar vista de escala de grises en pestaña 2
            if hasattr(self, "gray_preview_ax"):
                self.update_grayscale_preview()

            # Habilitar botones de análisis
            if hasattr(self, "show_grayscale_button"):
                self.show_grayscale_button.setEnabled(True)
                self.mirror_preview_button.setEnabled(True)
                self.analyze_intensity_button.setEnabled(True)
                self.preview_threshold_button.setEnabled(True)
                self.generate_attenuation_button.setEnabled(True)

    # ═══════════════════════════════════════════════════════════════════════════
    # FUNCIONES DE CONTROL DE CÁMARA BASLER
    # ═══════════════════════════════════════════════════════════════════════════



    def toggle_basler_capture(self):
        """Inicia o detiene la captura de cámara Basler."""
        if self.basler_camera is None:
            self.start_basler_capture()
        else:
            self.stop_basler_capture()



    def start_basler_capture(self):
        """Inicia la captura desde la cámara Basler."""
        if not BASLER_AVAILABLE:
            QMessageBox.warning(self, "Error", "pypylon no está instalado")
            return

        try:
            # Buscar cámaras Basler disponibles
            tlFactory = pylon.TlFactory.GetInstance()
            devices = tlFactory.EnumerateDevices()

            if len(devices) == 0:
                QMessageBox.warning(
                    self, "Error", "No se encontraron cámaras Basler conectadas"
                )
                self.log_to_console("No se encontraron cámaras Basler", "WARNING")
                return

            # Conectar a la primera cámara
            self.basler_camera = pylon.InstantCamera(tlFactory.CreateFirstDevice())
            self.basler_camera.Open()

            # Log de conexión
            device_info = self.basler_camera.GetDeviceInfo()
            self.log_to_console(
                f"Cámara Basler conectada: {device_info.GetModelName()} (S/N: {device_info.GetSerialNumber()})",
                "SUCCESS",
            )

            # Configurar cámara
            self.apply_basler_settings()

            # Configurar convertidor de imagen
            self.basler_converter = pylon.ImageFormatConverter()
            self.basler_converter.OutputPixelFormat = pylon.PixelType_BGR8packed
            self.basler_converter.OutputBitAlignment = (
                pylon.OutputBitAlignment_MsbAligned
            )

            # Iniciar captura
            self.basler_camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

            # Crear timer para actualizar frames
            if not hasattr(self, "basler_timer"):
                self.basler_timer = QTimer()
                self.basler_timer.timeout.connect(self.update_basler_frame)

            self.basler_timer.start(33)  # ~30 FPS
            self.start_basler_button.setText("⏸️ Detener Cámara Basler")

            # Mostrar controles en sidebar si existen
            if hasattr(self, "basler_sidebar_section"):
                self.basler_sidebar_section.setVisible(True)

            self.log_to_console("Captura Basler iniciada", "INFO")

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo iniciar cámara Basler: {str(e)}"
            )
            self.log_to_console(f"Error al iniciar Basler: {str(e)}", "ERROR")
            if self.basler_camera is not None:
                try:
                    self.basler_camera.Close()
                except:
                    pass
                self.basler_camera = None



    def stop_basler_capture(self):
        """Detiene la captura de cámara Basler."""
        try:
            if hasattr(self, "basler_timer"):
                self.basler_timer.stop()

            if self.basler_camera is not None:
                if self.basler_camera.IsGrabbing():
                    self.basler_camera.StopGrabbing()
                self.basler_camera.Close()
                self.basler_camera = None
                self.log_to_console("Cámara Basler desconectada", "INFO")

            # Ocultar controles en sidebar si existen
            if hasattr(self, "basler_sidebar_section"):
                self.basler_sidebar_section.setVisible(False)

            self.start_basler_button.setText("▶️ Iniciar Cámara Basler")

        except Exception as e:
            self.log_to_console(f"Error al detener Basler: {str(e)}", "WARNING")



    def update_basler_frame(self):
        """Actualiza el frame de la cámara Basler en la vista previa."""
        if self.basler_camera is None or not self.basler_camera.IsGrabbing():
            return

        try:
            # Capturar imagen
            grabResult = self.basler_camera.RetrieveResult(
                100, pylon.TimeoutHandling_Return
            )

            if grabResult.GrabSucceeded():
                # Convertir imagen
                image = self.basler_converter.Convert(grabResult)
                frame = image.GetArray()

                # Convertir de BGR a RGB para visualización
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Guardar como imagen de calibración actual
                self.calibration_image = frame_rgb

                # Generar versión en escala de grises
                self.calibration_grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Actualizar vista previa en pestaña 1
                self.calib_preview_ax.clear()
                self.calib_preview_ax.imshow(frame_rgb)
                self.calib_preview_ax.axis("off")
                self.calib_preview_ax.set_title(
                    f"Basler - Exp: {self.basler_exposure/1000:.1f}ms | Gain: {self.basler_gain:.1f}dB",
                    fontsize=10,
                    color="#00FF00" if self.dark_mode else "#008800",
                )
                self.calib_preview_canvas.draw_idle()

                # Actualizar vista de escala de grises en pestaña 2
                if hasattr(self, "gray_preview_ax"):
                    self.update_grayscale_preview()

                # Habilitar botones de análisis
                if hasattr(self, "show_grayscale_button"):
                    self.show_grayscale_button.setEnabled(True)
                    self.mirror_preview_button.setEnabled(True)
                    self.analyze_intensity_button.setEnabled(True)
                    self.preview_threshold_button.setEnabled(True)
                    self.generate_attenuation_button.setEnabled(True)

            grabResult.Release()

        except Exception as e:
            self.log_to_console(f"Error en captura Basler: {str(e)}", "WARNING")



    def apply_basler_settings(self):
        """Aplica la configuración actual a la cámara Basler."""
        if self.basler_camera is None or not self.basler_camera.IsOpen():
            return

        try:
            # Configurar exposición
            try:
                self.basler_camera.ExposureTime.SetValue(self.basler_exposure)
                self.log_to_console(
                    f"Exposición Basler: {self.basler_exposure/1000:.1f}ms", "INFO"
                )
            except Exception as e:
                self.log_to_console(
                    f"No se pudo configurar exposición: {str(e)}", "WARNING"
                )

            # Configurar ganancia
            try:
                self.basler_camera.Gain.SetValue(self.basler_gain)
                self.log_to_console(
                    f"Ganancia Basler: {self.basler_gain:.1f}dB", "INFO"
                )
            except Exception as e:
                self.log_to_console(
                    f"No se pudo configurar ganancia: {str(e)}", "WARNING"
                )

            # Configurar gamma (si está disponible)
            try:
                if hasattr(self.basler_camera, "Gamma"):
                    self.basler_camera.Gamma.SetValue(self.basler_gamma)
                    self.log_to_console(
                        f"Gamma Basler: {self.basler_gamma:.2f}", "INFO"
                    )
            except Exception as e:
                pass

            # Configurar black level (si está disponible)
            try:
                if hasattr(self.basler_camera, "BlackLevel"):
                    self.basler_camera.BlackLevel.SetValue(self.basler_black_level)
                    self.log_to_console(
                        f"Black Level Basler: {self.basler_black_level}", "INFO"
                    )
            except Exception as e:
                pass

        except Exception as e:
            self.log_to_console(
                f"Error al aplicar configuración Basler: {str(e)}", "ERROR"
            )



    def reset_basler_settings(self):
        """Resetea los controles Basler a valores por defecto."""
        self.basler_exposure = 10000.0
        self.basler_gain = 0.0
        self.basler_gamma = 1.0
        self.basler_black_level = 0

        # Actualizar UI en calibración (si existen)
        if hasattr(self, "basler_exposure_slider"):
            self.basler_exposure_slider.setValue(10000)
            self.basler_exposure_input.setText("10000")
            self.basler_gain_slider.setValue(0)
            self.basler_gain_input.setText("0.0")
            self.basler_gamma_slider.setValue(10)
            self.basler_gamma_input.setText("1.0")
            self.basler_black_slider.setValue(0)
            self.basler_black_input.setText("0")

        # Actualizar UI en sidebar (si existen)
        if hasattr(self, "basler_sidebar_exposure_slider"):
            self.basler_sidebar_exposure_slider.setValue(10000)
            self.basler_sidebar_exposure_input.setText("10000")
            self.basler_sidebar_gain_slider.setValue(0)
            self.basler_sidebar_gain_input.setText("0.0")
            self.basler_sidebar_gamma_slider.setValue(10)
            self.basler_sidebar_gamma_input.setText("1.0")
            self.basler_sidebar_black_slider.setValue(0)
            self.basler_sidebar_black_input.setText("0")

        # Aplicar a cámara si está activa
        if self.basler_camera is not None:
            self.apply_basler_settings()

        self.log_to_console(
            "Configuración Basler reseteada a valores por defecto", "INFO"
        )



    def update_basler_exposure_from_slider(self):
        """Actualiza exposición desde el slider."""
        # Determinar qué slider se usó
        sender = self.sender()
        if (
            hasattr(self, "basler_exposure_slider")
            and sender == self.basler_exposure_slider
        ):
            self.basler_exposure = float(self.basler_exposure_slider.value())
            self.basler_exposure_input.setText(f"{int(self.basler_exposure)}")
            # Sincronizar con sidebar
            if hasattr(self, "basler_sidebar_exposure_slider"):
                self.basler_sidebar_exposure_slider.blockSignals(True)
                self.basler_sidebar_exposure_slider.setValue(int(self.basler_exposure))
                self.basler_sidebar_exposure_input.setText(
                    f"{int(self.basler_exposure)}"
                )
                self.basler_sidebar_exposure_slider.blockSignals(False)
        elif (
            hasattr(self, "basler_sidebar_exposure_slider")
            and sender == self.basler_sidebar_exposure_slider
        ):
            self.basler_exposure = float(self.basler_sidebar_exposure_slider.value())
            self.basler_sidebar_exposure_input.setText(f"{int(self.basler_exposure)}")
            # Sincronizar con calibración
            if hasattr(self, "basler_exposure_slider"):
                self.basler_exposure_slider.blockSignals(True)
                self.basler_exposure_slider.setValue(int(self.basler_exposure))
                self.basler_exposure_input.setText(f"{int(self.basler_exposure)}")
                self.basler_exposure_slider.blockSignals(False)

        if self.basler_camera is not None and self.basler_camera.IsGrabbing():
            try:
                self.basler_camera.ExposureTime.SetValue(self.basler_exposure)
            except:
                pass



    def update_basler_exposure_from_input(self):
        """Actualiza exposición desde el campo de texto."""
        sender = self.sender()
        try:
            if (
                hasattr(self, "basler_exposure_input")
                and sender == self.basler_exposure_input
            ):
                value = float(self.basler_exposure_input.text())
                value = max(100, min(1000000, value))
                self.basler_exposure = value
                self.basler_exposure_slider.setValue(int(value))
                # Sincronizar con sidebar
                if hasattr(self, "basler_sidebar_exposure_slider"):
                    self.basler_sidebar_exposure_slider.blockSignals(True)
                    self.basler_sidebar_exposure_slider.setValue(int(value))
                    self.basler_sidebar_exposure_input.setText(f"{int(value)}")
                    self.basler_sidebar_exposure_slider.blockSignals(False)
            elif (
                hasattr(self, "basler_sidebar_exposure_input")
                and sender == self.basler_sidebar_exposure_input
            ):
                value = float(self.basler_sidebar_exposure_input.text())
                value = max(100, min(1000000, value))
                self.basler_exposure = value
                self.basler_sidebar_exposure_slider.setValue(int(value))
                # Sincronizar con calibración
                if hasattr(self, "basler_exposure_slider"):
                    self.basler_exposure_slider.blockSignals(True)
                    self.basler_exposure_slider.setValue(int(value))
                    self.basler_exposure_input.setText(f"{int(value)}")
                    self.basler_exposure_slider.blockSignals(False)

            if self.basler_camera is not None and self.basler_camera.IsGrabbing():
                self.basler_camera.ExposureTime.SetValue(self.basler_exposure)
        except ValueError:
            if (
                hasattr(self, "basler_exposure_input")
                and sender == self.basler_exposure_input
            ):
                self.basler_exposure_input.setText(f"{int(self.basler_exposure)}")
            elif (
                hasattr(self, "basler_sidebar_exposure_input")
                and sender == self.basler_sidebar_exposure_input
            ):
                self.basler_sidebar_exposure_input.setText(
                    f"{int(self.basler_exposure)}"
                )



    def update_basler_gain_from_slider(self):
        """Actualiza ganancia desde el slider."""
        sender = self.sender()
        if hasattr(self, "basler_gain_slider") and sender == self.basler_gain_slider:
            self.basler_gain = float(self.basler_gain_slider.value()) / 10.0
            self.basler_gain_input.setText(f"{self.basler_gain:.1f}")
            # Sincronizar con sidebar
            if hasattr(self, "basler_sidebar_gain_slider"):
                self.basler_sidebar_gain_slider.blockSignals(True)
                self.basler_sidebar_gain_slider.setValue(int(self.basler_gain * 10))
                self.basler_sidebar_gain_input.setText(f"{self.basler_gain:.1f}")
                self.basler_sidebar_gain_slider.blockSignals(False)
        elif (
            hasattr(self, "basler_sidebar_gain_slider")
            and sender == self.basler_sidebar_gain_slider
        ):
            self.basler_gain = float(self.basler_sidebar_gain_slider.value()) / 10.0
            self.basler_sidebar_gain_input.setText(f"{self.basler_gain:.1f}")
            # Sincronizar con calibración
            if hasattr(self, "basler_gain_slider"):
                self.basler_gain_slider.blockSignals(True)
                self.basler_gain_slider.setValue(int(self.basler_gain * 10))
                self.basler_gain_input.setText(f"{self.basler_gain:.1f}")
                self.basler_gain_slider.blockSignals(False)

        if self.basler_camera is not None and self.basler_camera.IsGrabbing():
            try:
                self.basler_camera.Gain.SetValue(self.basler_gain)
            except:
                pass



    def update_basler_gain_from_input(self):
        """Actualiza ganancia desde el campo de texto."""
        sender = self.sender()
        try:
            if hasattr(self, "basler_gain_input") and sender == self.basler_gain_input:
                value = float(self.basler_gain_input.text())
                value = max(0, min(24.0, value))
                self.basler_gain = value
                self.basler_gain_slider.setValue(int(value * 10))
                # Sincronizar con sidebar
                if hasattr(self, "basler_sidebar_gain_slider"):
                    self.basler_sidebar_gain_slider.blockSignals(True)
                    self.basler_sidebar_gain_slider.setValue(int(value * 10))
                    self.basler_sidebar_gain_input.setText(f"{value:.1f}")
                    self.basler_sidebar_gain_slider.blockSignals(False)
            elif (
                hasattr(self, "basler_sidebar_gain_input")
                and sender == self.basler_sidebar_gain_input
            ):
                value = float(self.basler_sidebar_gain_input.text())
                value = max(0, min(24.0, value))
                self.basler_gain = value
                self.basler_sidebar_gain_slider.setValue(int(value * 10))
                # Sincronizar con calibración
                if hasattr(self, "basler_gain_slider"):
                    self.basler_gain_slider.blockSignals(True)
                    self.basler_gain_slider.setValue(int(value * 10))
                    self.basler_gain_input.setText(f"{value:.1f}")
                    self.basler_gain_slider.blockSignals(False)

            if self.basler_camera is not None and self.basler_camera.IsGrabbing():
                self.basler_camera.Gain.SetValue(self.basler_gain)
        except ValueError:
            if hasattr(self, "basler_gain_input") and sender == self.basler_gain_input:
                self.basler_gain_input.setText(f"{self.basler_gain:.1f}")
            elif (
                hasattr(self, "basler_sidebar_gain_input")
                and sender == self.basler_sidebar_gain_input
            ):
                self.basler_sidebar_gain_input.setText(f"{self.basler_gain:.1f}")



    def update_basler_gamma_from_slider(self):
        """Actualiza gamma desde el slider."""
        sender = self.sender()
        if hasattr(self, "basler_gamma_slider") and sender == self.basler_gamma_slider:
            self.basler_gamma = float(self.basler_gamma_slider.value()) / 10.0
            self.basler_gamma_input.setText(f"{self.basler_gamma:.1f}")
            # Sincronizar con sidebar
            if hasattr(self, "basler_sidebar_gamma_slider"):
                self.basler_sidebar_gamma_slider.blockSignals(True)
                self.basler_sidebar_gamma_slider.setValue(int(self.basler_gamma * 10))
                self.basler_sidebar_gamma_input.setText(f"{self.basler_gamma:.1f}")
                self.basler_sidebar_gamma_slider.blockSignals(False)
        elif (
            hasattr(self, "basler_sidebar_gamma_slider")
            and sender == self.basler_sidebar_gamma_slider
        ):
            self.basler_gamma = float(self.basler_sidebar_gamma_slider.value()) / 10.0
            self.basler_sidebar_gamma_input.setText(f"{self.basler_gamma:.1f}")
            # Sincronizar con calibración
            if hasattr(self, "basler_gamma_slider"):
                self.basler_gamma_slider.blockSignals(True)
                self.basler_gamma_slider.setValue(int(self.basler_gamma * 10))
                self.basler_gamma_input.setText(f"{self.basler_gamma:.1f}")
                self.basler_gamma_slider.blockSignals(False)

        if self.basler_camera is not None and self.basler_camera.IsGrabbing():
            try:
                if hasattr(self.basler_camera, "Gamma"):
                    self.basler_camera.Gamma.SetValue(self.basler_gamma)
            except:
                pass



    def update_basler_gamma_from_input(self):
        """Actualiza gamma desde el campo de texto."""
        sender = self.sender()
        try:
            if (
                hasattr(self, "basler_gamma_input")
                and sender == self.basler_gamma_input
            ):
                value = float(self.basler_gamma_input.text())
                value = max(0.1, min(4.0, value))
                self.basler_gamma = value
                self.basler_gamma_slider.setValue(int(value * 10))
                # Sincronizar con sidebar
                if hasattr(self, "basler_sidebar_gamma_slider"):
                    self.basler_sidebar_gamma_slider.blockSignals(True)
                    self.basler_sidebar_gamma_slider.setValue(int(value * 10))
                    self.basler_sidebar_gamma_input.setText(f"{value:.1f}")
                    self.basler_sidebar_gamma_slider.blockSignals(False)
            elif (
                hasattr(self, "basler_sidebar_gamma_input")
                and sender == self.basler_sidebar_gamma_input
            ):
                value = float(self.basler_sidebar_gamma_input.text())
                value = max(0.1, min(4.0, value))
                self.basler_gamma = value
                self.basler_sidebar_gamma_slider.setValue(int(value * 10))
                # Sincronizar con calibración
                if hasattr(self, "basler_gamma_slider"):
                    self.basler_gamma_slider.blockSignals(True)
                    self.basler_gamma_slider.setValue(int(value * 10))
                    self.basler_gamma_input.setText(f"{value:.1f}")
                    self.basler_gamma_slider.blockSignals(False)

            if self.basler_camera is not None and self.basler_camera.IsGrabbing():
                if hasattr(self.basler_camera, "Gamma"):
                    self.basler_camera.Gamma.SetValue(self.basler_gamma)
        except ValueError:
            if (
                hasattr(self, "basler_gamma_input")
                and sender == self.basler_gamma_input
            ):
                self.basler_gamma_input.setText(f"{self.basler_gamma:.1f}")
            elif (
                hasattr(self, "basler_sidebar_gamma_input")
                and sender == self.basler_sidebar_gamma_input
            ):
                self.basler_sidebar_gamma_input.setText(f"{self.basler_gamma:.1f}")



    def update_basler_black_from_slider(self):
        """Actualiza black level desde el slider."""
        sender = self.sender()
        if hasattr(self, "basler_black_slider") and sender == self.basler_black_slider:
            self.basler_black_level = self.basler_black_slider.value()
            self.basler_black_input.setText(f"{self.basler_black_level}")
            # Sincronizar con sidebar
            if hasattr(self, "basler_sidebar_black_slider"):
                self.basler_sidebar_black_slider.blockSignals(True)
                self.basler_sidebar_black_slider.setValue(self.basler_black_level)
                self.basler_sidebar_black_input.setText(f"{self.basler_black_level}")
                self.basler_sidebar_black_slider.blockSignals(False)
        elif (
            hasattr(self, "basler_sidebar_black_slider")
            and sender == self.basler_sidebar_black_slider
        ):
            self.basler_black_level = self.basler_sidebar_black_slider.value()
            self.basler_sidebar_black_input.setText(f"{self.basler_black_level}")
            # Sincronizar con calibración
            if hasattr(self, "basler_black_slider"):
                self.basler_black_slider.blockSignals(True)
                self.basler_black_slider.setValue(self.basler_black_level)
                self.basler_black_input.setText(f"{self.basler_black_level}")
                self.basler_black_slider.blockSignals(False)

        if self.basler_camera is not None and self.basler_camera.IsGrabbing():
            try:
                if hasattr(self.basler_camera, "BlackLevel"):
                    self.basler_camera.BlackLevel.SetValue(self.basler_black_level)
            except:
                pass



    def update_basler_black_from_input(self):
        """Actualiza black level desde el campo de texto."""
        sender = self.sender()
        try:
            if (
                hasattr(self, "basler_black_input")
                and sender == self.basler_black_input
            ):
                value = int(self.basler_black_input.text())
                value = max(0, min(255, value))
                self.basler_black_level = value
                self.basler_black_slider.setValue(value)
                # Sincronizar con sidebar
                if hasattr(self, "basler_sidebar_black_slider"):
                    self.basler_sidebar_black_slider.blockSignals(True)
                    self.basler_sidebar_black_slider.setValue(value)
                    self.basler_sidebar_black_input.setText(f"{value}")
                    self.basler_sidebar_black_slider.blockSignals(False)
            elif (
                hasattr(self, "basler_sidebar_black_input")
                and sender == self.basler_sidebar_black_input
            ):
                value = int(self.basler_sidebar_black_input.text())
                value = max(0, min(255, value))
                self.basler_black_level = value
                self.basler_sidebar_black_slider.setValue(value)
                # Sincronizar con calibración
                if hasattr(self, "basler_black_slider"):
                    self.basler_black_slider.blockSignals(True)
                    self.basler_black_slider.setValue(value)
                    self.basler_black_input.setText(f"{value}")
                    self.basler_black_slider.blockSignals(False)

            if self.basler_camera is not None and self.basler_camera.IsGrabbing():
                if hasattr(self.basler_camera, "BlackLevel"):
                    self.basler_camera.BlackLevel.SetValue(self.basler_black_level)
        except ValueError:
            if (
                hasattr(self, "basler_black_input")
                and sender == self.basler_black_input
            ):
                self.basler_black_input.setText(f"{self.basler_black_level}")
            elif (
                hasattr(self, "basler_sidebar_black_input")
                and sender == self.basler_sidebar_black_input
            ):
                self.basler_sidebar_black_input.setText(f"{self.basler_black_level}")


