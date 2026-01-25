import sys
from PySide6.QtWidgets import QApplication
from ui.overlay.canvas import Canvas
from ui.menu.radial_widget import DrawboardMenu

def main():
    app = QApplication(sys.argv)
    
    canvas = Canvas()
    canvas.showFullScreen()
    
    menu = DrawboardMenu(canvas)
    
    # Pass menu ref to canvas to block clicks on menu
    canvas.set_menu_ref(menu)
    
    menu.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()