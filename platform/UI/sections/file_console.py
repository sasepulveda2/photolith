"""
Secciones: ARCHIVOS + CONSOLA DEL SISTEMA.

Métodos:
    _build_file_tree()         → árbol de navegación de archivos
    _build_console_section()   → consola de log en el pie de la ventana
"""
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QTextEdit, QTreeWidget, QLineEdit
)
from PyQt5.QtCore import Qt, QSize
from UI.collapsible_section import CollapsibleSection
from constants import (
    CONSOLE_MAX_HEIGHT, CONSOLE_CONTENT_MARGINS,
    FILE_TREE_ICON_SIZE, FILE_TREE_MIN_WIDTH, FILE_TREE_MIN_HEIGHT,
)


class FileConsolePanelBuilder:
    """Mixin: construye el árbol de archivos y la consola del sistema."""

    def _build_file_tree(self) -> None:
        """ ARCHIVOS — árbol de navegación de archivos del proyecto."""
        self.files_section = CollapsibleSection("Archivos", self, expanded=True, section_id="files")
        
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("")
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.file_tree.itemDoubleClicked.connect(self.load_from_tree)
        self.file_tree.setIconSize(QSize(FILE_TREE_ICON_SIZE, FILE_TREE_ICON_SIZE))
        self.file_tree.setMinimumWidth(FILE_TREE_MIN_WIDTH)
        self.file_tree.setMinimumHeight(FILE_TREE_MIN_HEIGHT)
        self.file_tree.setObjectName("fileTree")
        self.update_file_tree()

        layout.addWidget(self.file_tree)
        self.files_section.setContentWidget(container)
        self.info_layout.addWidget(self.files_section)

    def _build_console_section(self) -> QWidget:
        """ Consola del Sistema — log de mensajes en el pie de la ventana."""
        self.console_section = CollapsibleSection("Consola del sistema", self, expanded=False, section_id="system_console")
        
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(*CONSOLE_CONTENT_MARGINS)

        self.system_console = QTextEdit()
        self.system_console.setReadOnly(True)
        self.system_console.setMinimumHeight(0)
        self.system_console.setPlaceholderText(
            "Los mensajes del sistema aparecerán aquí..."
        )

        import shutil
        has_console = shutil.which("powershell") or shutil.which("cmd")

        self.console_input = QLineEdit()
        self.console_input.setPlaceholderText("Escriba un comando y presione Enter (ej. ping google.com, dir, clear)...")
        if hasattr(self, "execute_system_command"):
            self.console_input.returnPressed.connect(self.execute_system_command)
        else:
            # Fallback connection if method not added yet
            self.console_input.returnPressed.connect(lambda: self.log_to_console("Ejecución de comandos en preparación...", "WARNING"))

        clear_btn = QPushButton("Limpiar consola")
        clear_btn.clicked.connect(self.clear_console)

        # Input and clear button in a horizontal layout
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.console_input, stretch=1)
        input_layout.addWidget(clear_btn)

        if not has_console:
            self.console_input.hide()
            clear_btn.hide()

        content_layout.addWidget(self.system_console)
        content_layout.addLayout(input_layout)
        
        self.console_section.setContentWidget(content_container)

        # Modificamos la política de tamaño para que pueda estirarse en el QSplitter
        from PyQt5.QtWidgets import QSizePolicy
        self.console_section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.console_section.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        return self.console_section
