from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtWidgets import QFrame, QSizePolicy, QPushButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    def __init__(self, title: str, parent=None, expanded: bool = True, section_id: str = None):
        super().__init__(parent)
        self.section_id = section_id
        self.title_text = title

        # Usar QSettings para guardar el estado colapsable
        self.settings = QSettings("Uandes", "PhotolithSimulator")
        
        if self.section_id:
            val = self.settings.value(f"section_expanded_{self.section_id}", expanded)
            if isinstance(val, str):
                expanded = val.lower() == 'true'
            else:
                expanded = bool(val)

        # Usar QPushButton con texto explícito para la flecha
        self.toggle_button = QPushButton()
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(expanded)
        self._update_button_text(expanded)
        
        self.toggle_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.toggle_button.setObjectName("sectionTitle")
        self.toggle_button.setCursor(Qt.PointingHandCursor)

        self.content_area = QFrame()
        self.content_area.setFrameShape(QFrame.NoFrame)
        self.content_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        self.content_area.setLayout(self.content_layout)
        self.content_area.setVisible(expanded)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

        self.toggle_button.toggled.connect(self._on_toggled)

    def _update_button_text(self, expanded: bool):
        arrow = "▼" if expanded else "▶"
        self.toggle_button.setText(f"{arrow}  {self.title_text}")

    def _on_toggled(self, checked: bool) -> None:
        self._update_button_text(checked)
        self.content_area.setVisible(checked)
        if self.section_id:
            self.settings.setValue(f"section_expanded_{self.section_id}", checked)

    def setContentWidget(self, widget: QWidget) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self.content_layout.addWidget(widget)

    def set_collapsed(self, collapsed: bool) -> None:
        self.toggle_button.setChecked(not collapsed)

    def is_collapsed(self) -> bool:
        return not self.toggle_button.isChecked()
