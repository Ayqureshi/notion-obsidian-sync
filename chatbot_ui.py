import sys
import requests
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QTextEdit

# 1. BACKGROUND WORKER
# Runs the network request off the main thread so the window never freezes





















class ApiWorker(QThread):
    finished = pyqtSignal(str)

    def __init__(self, query_text):
        super().__init__()
        self.query_text = query_text

    def run(self):
        try:
            # Connects directly to your chatbot.py FastAPI server
            res = requests.post(
                "http://127.0.0.1:8000/query",
                json={"prompt": self.query_text},
                timeout=15
            )
            data = res.json()
            self.finished.emit(data.get("response", "No 'response' key returned from backend."))
        except Exception as e:
            self.finished.emit(f"Connection Error: Is chatbot.py running?\n\n{e}")

# 2. THE FRONTEND WINDOW
class PopUpWindow(QWidget):
    def __init__(self):
        super().__init__()
        
        # Window Behaviors (Frameless + Floating)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(500, 300)
        
        # Functional UI Elements
        layout = QVBoxLayout()
        
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("Type your vault query and press Enter...")
        self.input_box.returnPressed.connect(self.send_to_backend)
        
        self.display_box = QTextEdit()
        self.display_box.setReadOnly(True)
        
        layout.addWidget(self.input_box)
        layout.addWidget(self.display_box)
        self.setLayout(layout)

    def send_to_backend(self):
        text = self.input_box.text().strip()
        if not text:
            return
            
        self.display_box.setText("Querying LlamaIndex + Groq...")
        
        # Trigger background HTTP request
        self.worker = ApiWorker(text)
        self.worker.finished.connect(self.receive_from_backend)
        self.worker.start()

    def receive_from_backend(self, response_text):
        self.display_box.setText(response_text)

    # Auto-dismiss pop-up when clicking away
    def changeEvent(self, event):
        if event.type() == event.Type.ActivationChange and not self.isActiveWindow():
            self.hide()
        super().changeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PopUpWindow()
    window.show()
    sys.exit(app.exec())