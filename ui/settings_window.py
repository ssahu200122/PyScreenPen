from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton, 
                               QFileDialog, QHBoxLayout, QLineEdit, QGroupBox, QFormLayout,
                               QScrollArea, QWidget)
from PySide6.QtGui import QKeySequence, QKeyEvent
from PySide6.QtCore import Qt, Signal
from core.state import state

class KeySequenceEditButton(QPushButton):
    keySequenceChanged = Signal(str)

    def __init__(self, initial_sequence="", parent=None):
        super().__init__(parent)
        self.current_sequence = initial_sequence
        self.is_recording = False
        self.update_display_text()
        self.clicked.connect(self.start_recording)

    def update_display_text(self):
        if self.is_recording:
            self.setText("Press Key Combo...")
            self.setStyleSheet("background-color: #ff4757; color: white; font-weight: bold; border-radius: 4px; padding: 6px;")
        else:
            self.setText(self.current_sequence if self.current_sequence else "None")
            self.setStyleSheet("background-color: #f1f2f6; color: #2f3542; border: 1px solid #ced6e0; border-radius: 4px; padding: 6px;")

    def start_recording(self):
        self.is_recording = True
        self.setFocus()
        self.update_display_text()

    def keyPressEvent(self, event: QKeyEvent):
        if not self.is_recording:
            super().keyPressEvent(event)
            return

        key = event.key()
        # Ignore standalone modifier key presses
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        if key == Qt.Key_Escape:
            self.is_recording = False
            self.update_display_text()
            self.clearFocus()
            event.accept()
            return

        # --- THE FIX ---
        # Let PySide6 natively handle the combination of the key and its modifiers
        # Let PySide6 natively handle the combination of the key and its modifiers
        combination = event.keyCombination()
        seq = QKeySequence(combination)
        
        # PortableText forces universal English names (Ctrl, Alt, Shift) with no spaces
        self.current_sequence = seq.toString(QKeySequence.PortableText)
        # ---------------
        
        self.is_recording = False
        self.update_display_text()
        self.clearFocus()
        self.keySequenceChanged.emit(self.current_sequence)
        event.accept()

    def focusOutEvent(self, event):
        if self.is_recording:
            self.is_recording = False
            self.update_display_text()
        super().focusOutEvent(event)

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        
        # 1. Removed setFixedSize. Now using minimum size and a starting default size.
        self.setMinimumSize(450, 400)
        self.resize(500, 600)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        # The main layout for the dialog window
        main_dialog_layout = QVBoxLayout(self)
        
        # 2. Create the Scroll Area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # 3. Create a widget to hold all the content inside the scroll area
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(15)
        
        # --- ALL CONTENT GOES INTO 'layout' NOW ---
        
        # Title
        title = QLabel("DrawBoard Preferences")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        layout.addWidget(title)
        
        # 1. Default Save Location
        loc_layout = QVBoxLayout()
        loc_layout.setSpacing(5)
        loc_layout.addWidget(QLabel("Default Save Location:"))
        
        file_box = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Desktop (Default)")
        self.path_input.setReadOnly(True)
        file_box.addWidget(self.path_input)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_location)
        file_box.addWidget(browse_btn)
        
        loc_layout.addLayout(file_box)
        layout.addLayout(loc_layout)
        
        # 2. Options
        self.chk_gpu = QCheckBox("Enable Hardware Acceleration (Restart required)")
        self.chk_gpu.setChecked(True)
        layout.addWidget(self.chk_gpu)
        
        self.chk_autosave = QCheckBox("Autosave every 5 minutes")
        layout.addWidget(self.chk_autosave)
        
        # 3. Keyboard Shortcuts Section
        shortcut_group = QGroupBox("Keyboard Shortcuts")
        shortcut_layout = QFormLayout()
        shortcut_layout.setSpacing(10) # Added spacing between rows

        self.shortcut_actions = [
            ("toggle_eraser", "Pen Button (Lower) - Toggle Eraser"),
            ("toggle_cursor", "Pen Button (Upper) - Toggle Pointer"),
            ("increase_size", "Increase Brush Size"),
            ("decrease_size", "Decrease Brush Size"),
            ("toggle_board", "Toggle Whiteboard Background"),
            ("toggle_lasso", "Toggle Lasso Select"),
            ("clear_canvas", "Clear Entire Screen"),
            ("toggle_laser", "Toggle Laser / Highlighter"),
            ("exit_app", "Quit / Kill Application"),
            ("toggle_visibility", "Hide / Unhide Overlay")
        ]

        for action_id, label_text in self.shortcut_actions:
            btn = KeySequenceEditButton(state.get_shortcut(action_id))
            btn.keySequenceChanged.connect(lambda seq, aid=action_id: state.set_shortcut(aid, seq))
            btn.keySequenceChanged.connect(self.refresh_canvas_shortcuts)
            shortcut_layout.addRow(label_text + ":", btn)

        shortcut_group.setLayout(shortcut_layout)
        layout.addWidget(shortcut_group)
        
        layout.addStretch()
        
        # --- FINALIZE SCROLL AREA ---
        scroll_area.setWidget(content_widget)
        main_dialog_layout.addWidget(scroll_area)
        
        # Close Button (Placed outside the scroll area so it is always at the bottom)
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: #ddd;")
        close_btn.clicked.connect(self.accept)
        main_dialog_layout.addWidget(close_btn)

    def refresh_canvas_shortcuts(self):
        """Safely finds the main Canvas and forces it to reload the global keyboard listeners."""
        parent_widget = self.parent()
        if parent_widget and hasattr(parent_widget, 'setup_global_shortcuts'):
            parent_widget.setup_global_shortcuts()

    def browse_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Default Save Folder")
        if folder:
            self.path_input.setText(folder)