import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSharedMemory
from ui.overlay.canvas import Canvas
from ui.menu.radial_widget import DrawboardMenu

def main():
    app = QApplication(sys.argv)
    
    # --- SINGLE INSTANCE LOCK ---
    # Create a unique memory ID for this application
    shared_mem = QSharedMemory("PyScreenPen_Unique_Instance_Lock")
    
    # Try to attach to it. If successful, another instance is already running.
    if shared_mem.attach():
        sys.exit(0) # Silently close this duplicate instance
        
    # If not attached, create the memory block to claim ownership
    shared_mem.create(1)
    # ----------------------------
    
    canvas = Canvas()
    canvas.showFullScreen()
    
    menu = DrawboardMenu(canvas)
    
    # Pass menu ref to canvas to block clicks on menu
    canvas.set_menu_ref(menu)
    
    menu.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()