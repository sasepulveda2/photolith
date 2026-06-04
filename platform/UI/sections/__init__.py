"""
Re-exporta todos los mixins de secciones del sidebar.

Permite que UISetupMixin los importe con un solo import:
    from UI.sections import (
        ToolbarCanvasBuilder, DataPanelsBuilder, ...
    )
"""
from UI.sections.toolbar_canvas import ToolbarCanvasBuilder
from UI.sections.data_panels import DataPanelsBuilder
from UI.sections.camera_panel import CameraPanelBuilder
from UI.sections.grid_panels import GridPanelsBuilder
from UI.sections.segmentation_panel import SegmentationPanelBuilder
from UI.sections.motors_panel import MotorsPanelBuilder
from UI.sections.exposure_panel import ExposurePanelBuilder
from UI.sections.projection_panel import ProjectionPanelBuilder
from UI.sections.calibration_panel import CalibrationPanelBuilder
from UI.sections.file_console import FileConsolePanelBuilder
from UI.sections.ruler_scale_panel import RulerScalePanelBuilder

__all__ = [
    "ToolbarCanvasBuilder",
    "DataPanelsBuilder",
    "CameraPanelBuilder",
    "GridPanelsBuilder",
    "SegmentationPanelBuilder",
    "MotorsPanelBuilder",
    "ExposurePanelBuilder",
    "ProjectionPanelBuilder",
    "CalibrationPanelBuilder",
    "FileConsolePanelBuilder",
    "RulerScalePanelBuilder",
]
