# 🖊️ PyScreenPen

[⬇️ **Download Latest Installer (.exe)**](https://github.com/ssahu200122/PyScreenPen/releases/latest)

**PyScreenPen** is a powerful, lightweight screen annotation and digital whiteboard utility built with Python and PySide6. Designed specifically for educators, presenters, and developers, it provides a seamless drawing layer over your entire screen, complete with advanced drawing tablet support and a highly responsive animated radial menu.

---

## ✨ Key Features

* **Advanced Tablet Integration:** Full support for drawing tablets (like XP-Pen). Detects stylus pressure for variable stroke width and natively supports hardware buttons for instant Pen/Eraser toggling.
* **Smart Radial Menu:** A custom-built, animated, multi-tier circular menu that gives you instant access to pens, highlighters, shapes, colors, and settings without cluttering the screen.
* **Auto-Shape Recognition:** Draw a rough circle, rectangle, or triangle, hold your pen still, and PyScreenPen will use OpenCV to automatically snap your ink into a perfect geometric vector shape.
* **Global Hotkeys:** Fully customizable keyboard shortcuts powered by the `keyboard` library that work even when the app is in the background.
* **Ghost & Whiteboard Modes:** Instantly drop a solid background color to use the app as a traditional whiteboard, or trigger "Ghost Mode" to hide the UI and focus purely on teaching.
* **Selection & Transformation:** Select drawn strokes, move them, rotate them, scale them, or copy/paste them directly on the canvas.

---

## 🏗️ Architecture

The application is structured around a central state manager and specialized UI components, ensuring a clean separation of logic and rendering.

* **`main.py`**: The application entry point that initializes the PySide6 `QApplication` and system tray.
* **`core/state.py`**: A robust `StateManager` utilizing Qt Signals. It acts as the central brain of the app, storing current tool states, colors, thickness, and managing shortcut preferences. It automatically persists user settings to the hidden `AppData/Roaming/PyScreenPen` directory.
* **`ui/overlay/canvas.py`**: The core drawing engine. A transparent, frameless `QWidget` that spans all monitors. It captures raw `QTabletEvent` data, handles the `QPainter` buffer for rendering ink, manages the undo/redo stack, and processes OpenCV contour detection for shape snapping.
* **`ui/menu/radial_widget.py` & `menu_models.py`**: The UI logic for the 340x340 animated circular menu. It uses mathematical trigonometry to calculate slice paths, icon placements, and perimeter button anchoring, alongside smooth `QPropertyAnimation` transitions.

---

## 🛠️ Dependencies & Tech Stack

* **Python 3.10+**
* **PySide6**: Core GUI framework, rendering, and tablet event handling.
* **OpenCV (`opencv-python`) & NumPy**: Used for perimeter approximation and bounding box math during Auto-Shape recognition.
* **Keyboard**: Used for low-level, system-wide hotkey hooking.

---

## 🚀 Running locally (Development)

1. Clone the repository:
   ```bash
   git clone [https://github.com/yourusername/PyScreenPen.git](https://github.com/yourusername/PyScreenPen.git)
   cd PyScreenPen



Install the required dependencies:Bashpip install PySide6 opencv-python numpy keyboard
Run the application:Bashpython main.py
📦 Building the Executable (.exe)To compile the Python application into a standalone Windows executable, we use PyInstaller. The project includes a dynamic path resolver in the code to ensure assets are bundled correctly.Install PyInstaller:Bashpip install pyinstaller
Run the build command from the project root:Bashpyinstaller --noconfirm --onedir --windowed --add-data "assets;assets" --icon="logo.ico" main.py
Your compiled application will be available inside the dist/main/ folder.💿 Creating the Installer (Inno Setup)To package the dist/main directory into a professional Windows installer (setup.exe) that installs to Program Files and creates desktop shortcuts:Download and install Inno Setup.Open the included setup_script.iss file in the Inno Setup Compiler.Click the Run button (green play icon) at the top.The final installer (PyScreenPen_Setup.exe) will be generated inside an Output folder in your project directory.⌨️ Default Global ShortcutsActionShortcutIncrease Brush SizeF5Decrease Brush SizeF6Toggle Laser / HighlighterF7Toggle EraserF8Toggle Pointer / CursorF9Hide / Unhide OverlayF10Ghost Mode (Hide Menu)F11Clear CanvasF4Toggle WhiteboardF2Exit ApplicationCtrl + Q(Shortcuts can be fully customized from the in-app settings menu).

AuthorCreated by Sourabh sahu