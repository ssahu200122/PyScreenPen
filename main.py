import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from ui.overlay.canvas import Canvas
from ui.menu.radial_widget import DrawboardMenu

# A unique name for your application's local server
SERVER_NAME = "PyScreenPen_Toggle_Server"

def main():
    app = QApplication(sys.argv)
    
    # --- STEP 1: Check if the app is already running ---
    socket = QLocalSocket()
    socket.connectToServer(SERVER_NAME)
    
    if socket.waitForConnected(500):
        # Connection successful! This means the app is already open.
        # Send the shutdown command to the running instance.
        socket.write(b"SHUTDOWN")
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        sys.exit(0) # Close this duplicate launch instantly
        
    # --- STEP 2: First Instance Setup ---
    # If the socket couldn't connect, this is the first time launching.
    # Clean up any leftover server configurations from past crashes, then start the server.
    QLocalServer.removeServer(SERVER_NAME)
    server = QLocalServer()
    server.listen(SERVER_NAME)
    
    # Function to listen for future Key 1 presses (new connections)
    def handle_new_connection():
        client = server.nextPendingConnection()
        if client.waitForReadyRead(500):
            message = client.readAll().data()
            if message == b"SHUTDOWN":
                app.quit() # Cleanly close the whole application
                
    server.newConnection.connect(handle_new_connection)
    
    # --- STEP 3: Boot the Application ---
    canvas = Canvas()
    canvas.showFullScreen()
    
    menu = DrawboardMenu(canvas)
    
    # Pass menu ref to canvas to block clicks on menu
    canvas.set_menu_ref(menu)
    
    menu.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()