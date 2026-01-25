from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton, QFileDialog, QHBoxLayout, QLineEdit
from PySide6.QtCore import Qt
from core.state import state

class SettingsWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setFixedSize(400, 300)
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout()
        layout.setSpacing(15)
        
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
        
        layout.addStretch()
        
        # Close Button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)

    def browse_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Default Save Folder")
        if folder:
            self.path_input.setText(folder)
            # In a real app, you would save this to a config file/state here