"""
Secciones: 📁 ARCHIVOS + 📋 CONSOLA DEL SISTEMA.

Métodos:
    _build_file_tree()         → árbol de navegación de archivos
    _build_console_section()   → consola de log en el pie de la ventana
"""
from PyQt5.QtWidgets import (
    QVBoxLayout, QLabel, QPushButton, QWidget, QTextEdit, QTreeWidget,
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
        """📁 ARCHIVOS — árbol de navegación de archivos del proyecto."""
        files_title = QLabel("📁 ARCHIVOS")
        files_title.setObjectName("sectionTitle")
        self.info_layout.addWidget(files_title)

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

        self.info_layout.addWidget(self.file_tree, stretch=1)

    def _build_console_section(self) -> CollapsibleSection:
        """📋 Consola del Sistema — log de mensajes en el pie de la ventana."""
        console_section = CollapsibleSection("📋 Consola del Sistema", expanded=False)
        content = QWidget()
        console_layout = QVBoxLayout(content)
        console_layout.setContentsMargins(*CONSOLE_CONTENT_MARGINS)

        self.system_console = QTextEdit()
        self.system_console.setReadOnly(True)
        self.system_console.setMaximumHeight(CONSOLE_MAX_HEIGHT)
        self.system_console.setPlaceholderText(
            "Los mensajes del sistema aparecerán aquí..."
        )

        clear_btn = QPushButton("🗑️ Limpiar Consola")
        clear_btn.clicked.connect(self.clear_console)

        console_layout.addWidget(self.system_console)
        console_layout.addWidget(clear_btn)
        console_section.setContentWidget(content)

        return console_section
