from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton, 
                               QFileDialog, QHBoxLayout, QLineEdit, QGroupBox, QFormLayout,
                               QScrollArea, QWidget, QComboBox, QSlider, QColorDialog)
from PySide6.QtGui import QKeySequence, QKeyEvent, QColor
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
        self.is_recording = True; self.setFocus(); self.update_display_text()

    def keyPressEvent(self, event: QKeyEvent):
        if not self.is_recording:
            super().keyPressEvent(event); return

        key = event.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta): return
        if key == Qt.Key_Escape:
            self.is_recording = False; self.update_display_text(); self.clearFocus(); event.accept(); return

        combination = event.keyCombination()
        seq = QKeySequence(combination)
        self.current_sequence = seq.toString(QKeySequence.PortableText)
        
        self.is_recording = False; self.update_display_text(); self.clearFocus()
        self.keySequenceChanged.emit(self.current_sequence); event.accept()

    def focusOutEvent(self, event):
        if self.is_recording:
            self.is_recording = False; self.update_display_text()
        super().focusOutEvent(event)


class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(480, 600)
        self.resize(500, 700)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        main_dialog_layout = QVBoxLayout(self)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setSpacing(15)
        
        title = QLabel("DrawBoard Preferences")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #333;")
        layout.addWidget(title)
        
        # --- 1. Default Save Location ---
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
        
        # --- 2. Options ---
        self.chk_gpu = QCheckBox("Enable Hardware Acceleration (Restart required)")
        self.chk_gpu.setChecked(True)
        layout.addWidget(self.chk_gpu)
        
        self.chk_autosave = QCheckBox("Autosave every 5 minutes")
        layout.addWidget(self.chk_autosave)
        
        # --- 3. Keyboard Shortcuts Section ---
        shortcut_group = QGroupBox("Keyboard Shortcuts")
        shortcut_layout = QFormLayout()
        shortcut_layout.setSpacing(10)

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
            ("toggle_visibility", "Hide / Unhide Overlay"),
            ("toggle_ghost", "Ghost Mode (Hide Menu Only)")
        ]

        for action_id, label_text in self.shortcut_actions:
            btn = KeySequenceEditButton(state.get_shortcut(action_id))
            btn.keySequenceChanged.connect(lambda seq, aid=action_id: state.set_shortcut(aid, seq))
            btn.keySequenceChanged.connect(self.refresh_canvas_shortcuts)
            shortcut_layout.addRow(label_text + ":", btn)

        shortcut_group.setLayout(shortcut_layout)
        layout.addWidget(shortcut_group)

        # --- 4. NEW: BACKGROUND PATTERNS SECTION ---
        pattern_group = QGroupBox("Background Patterns (Grid & Lines)")
        pattern_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        
        self.pattern_layout = QFormLayout()
        self.pattern_layout.setSpacing(12)
        
        self.pattern_combo = QComboBox()
        self.pattern_combo.addItems(["None", "Grid", "Lined Paper", "Dotted", "Coordinate System"])
        self.pattern_types = ["none", "grid", "lines", "dots", "coordinate"]
        
        current_idx = self.pattern_types.index(state.pattern_type) if state.pattern_type in self.pattern_types else 0
        self.pattern_combo.setCurrentIndex(current_idx)
        self.pattern_combo.currentIndexChanged.connect(self.on_pattern_type_changed)
        self.pattern_layout.addRow("Pattern Type:", self.pattern_combo)
        
        # Spacing Slider
        self.slider_spacing = QSlider(Qt.Horizontal)
        self.slider_spacing.setRange(10, 200)
        self.slider_spacing.valueChanged.connect(lambda v: self.update_current_pattern("spacing", v))
        self.pattern_layout.addRow("Spacing/Size:", self.slider_spacing)
        
        # Thickness Slider
        self.slider_thickness = QSlider(Qt.Horizontal)
        self.slider_thickness.setRange(1, 10)
        self.slider_thickness.valueChanged.connect(lambda v: self.update_current_pattern("thickness", v))
        self.pattern_layout.addRow("Line/Dot Thickness:", self.slider_thickness)

        # Opacity Slider
        self.slider_opacity = QSlider(Qt.Horizontal)
        self.slider_opacity.setRange(10, 255)
        self.slider_opacity.valueChanged.connect(lambda v: self.update_current_pattern("opacity", v))
        self.pattern_layout.addRow("Opacity:", self.slider_opacity)

        # Color Button
        self.btn_color = QPushButton("Pick Pattern Color")
        self.btn_color.setStyleSheet("font-weight: bold;")
        self.btn_color.clicked.connect(self.pick_pattern_color)
        self.pattern_layout.addRow("Color:", self.btn_color)

        # Axis Color (Only for Coordinate System)
        self.lbl_axis_color = QLabel("Axis Color:")
        self.btn_axis_color = QPushButton("Pick Center Axis Color")
        self.btn_axis_color.clicked.connect(self.pick_axis_color)
        self.pattern_layout.addRow(self.lbl_axis_color, self.btn_axis_color)

        pattern_group.setLayout(self.pattern_layout)
        layout.addWidget(pattern_group)
        # ----------------------------------------------

        layout.addStretch()
        
        scroll_area.setWidget(content_widget)
        main_dialog_layout.addWidget(scroll_area)
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("padding: 8px; font-weight: bold; background-color: #ddd;")
        close_btn.clicked.connect(self.accept)
        main_dialog_layout.addWidget(close_btn)

        # Initialize the pattern UI to reflect memory
        self.refresh_pattern_ui_state()

    def refresh_canvas_shortcuts(self):
        parent_widget = self.parent()
        if parent_widget and hasattr(parent_widget, 'setup_global_shortcuts'):
            parent_widget.setup_global_shortcuts()

    def browse_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Default Save Folder")
        if folder: self.path_input.setText(folder)

    # --- PATTERN UI LOGIC ---
    def on_pattern_type_changed(self, index):
        p_type = self.pattern_types[index]
        state.set_pattern_type(p_type)
        self.refresh_pattern_ui_state()

    def refresh_pattern_ui_state(self):
        p_type = state.pattern_type
        is_active = p_type != "none"
        
        # Disable sliders if "None" is selected
        self.slider_spacing.setEnabled(is_active)
        self.slider_thickness.setEnabled(is_active)
        self.slider_opacity.setEnabled(is_active)
        self.btn_color.setEnabled(is_active)
        
        # Handle Coordinate Axis visibility
        is_coord = (p_type == "coordinate")
        self.lbl_axis_color.setVisible(is_coord)
        self.btn_axis_color.setVisible(is_coord)
        
        if is_active:
            settings = state.pattern_settings.get(p_type, {})
            self.slider_spacing.blockSignals(True)
            self.slider_thickness.blockSignals(True)
            self.slider_opacity.blockSignals(True)
            
            self.slider_spacing.setValue(settings.get("spacing", 40))
            self.slider_thickness.setValue(settings.get("thickness", 1))
            self.slider_opacity.setValue(settings.get("opacity", 100))
            
            c_hex = settings.get("color", "#808080")
            self.btn_color.setStyleSheet(f"background-color: {c_hex}; color: {'black' if QColor(c_hex).lightness() > 128 else 'white'};")
            
            if is_coord:
                a_hex = settings.get("axis_color", "#FF4444")
                self.btn_axis_color.setStyleSheet(f"background-color: {a_hex}; color: {'black' if QColor(a_hex).lightness() > 128 else 'white'};")

            self.slider_spacing.blockSignals(False)
            self.slider_thickness.blockSignals(False)
            self.slider_opacity.blockSignals(False)

    def update_current_pattern(self, key, value):
        if state.pattern_type != "none":
            state.update_pattern_settings(state.pattern_type, key, value)

    def pick_pattern_color(self):
        if state.pattern_type == "none": return
        current_hex = state.pattern_settings.get(state.pattern_type, {}).get("color", "#808080")
        color = QColorDialog.getColor(QColor(current_hex), self, "Select Pattern Color")
        if color.isValid():
            self.update_current_pattern("color", color.name())
            self.refresh_pattern_ui_state()

    def pick_axis_color(self):
        if state.pattern_type != "coordinate": return
        current_hex = state.pattern_settings.get("coordinate", {}).get("axis_color", "#FF4444")
        color = QColorDialog.getColor(QColor(current_hex), self, "Select Center Axis Color")
        if color.isValid():
            self.update_current_pattern("axis_color", color.name())
            self.refresh_pattern_ui_state()
