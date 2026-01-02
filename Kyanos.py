import sys, os, json
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTextEdit, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QLabel,
    QDialog, QMessageBox
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont

from openai import OpenAI


# ================== CONFIG ==================
APP_DIR = os.path.join(os.path.expanduser("~"), ".Kyanos")
os.makedirs(APP_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DIR, "config.json")


def load_api_key():
    if os.path.exists(CONFIG_FILE):
        return json.load(open(CONFIG_FILE)).get("api_key")
    return None


def save_api_key(key):
    json.dump({"api_key": key}, open(CONFIG_FILE, "w"))


# ================== API KEY DIALOG ==================
class ApiKeyDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Kyanos Setup")
        self.setFixedSize(420, 200)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel("Kyanos")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))

        subtitle = QLabel("Enter your OpenAI API key")
        subtitle.setStyleSheet("color:#9ca3af;")

        self.input = QLineEdit()
        self.input.setPlaceholderText("sk-...")

        btn = QPushButton("Continue")
        btn.clicked.connect(self.save)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.input)
        layout.addWidget(btn)

    def save(self):
        key = self.input.text().strip()
        if not key.startswith("sk-"):
            QMessageBox.warning(self, "Invalid", "Invalid API key")
            return
        save_api_key(key)
        self.accept()


# ================== AI WORKER ==================
class AIWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, client, system, prompt):
        super().__init__()
        self.client = client
        self.system = system
        self.prompt = prompt

    def run(self):
        try:
            today = datetime.now().strftime("%d %B %Y")
            response = self.client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {"role": "system", "content": f"{self.system}\nToday's date is {today}."},
                    {"role": "user", "content": self.prompt}
                ]
            )
            self.done.emit(response.output_text)
        except Exception as e:
            self.done.emit(f"❌ Error: {e}")


# ================== CHAT VIEW ==================
class ChatView(QWidget):
    def __init__(self, client):
        super().__init__()
        self.client = client

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        self.chat = QTextEdit(readOnly=True)
        self.chat.setFont(QFont("Segoe UI", 11))
        self.chat.setStyleSheet("border:none;")
        self.chat.setPlaceholderText("Conversation will appear here…")

        self.input = QLineEdit()
        self.input.setPlaceholderText("Message Kyanos…")
        self.input.returnPressed.connect(self.send)

        layout.addWidget(self.chat)
        layout.addWidget(self.input)

        # Intro message (shown ONCE)
        self.add_message(
            "ai",
            "👋 Hi, I’m Kyanos — a calm, clear study assistant.\n\n"
            "Ask questions, generate notes, quizzes, or flashcards anytime ✨"
        )

    def add_message(self, sender, text):
        if sender == "user":
            label = "You"
            label_color = "#ed7ba3"
            bg = "#0f172a"
            padding = "10px"
        else:
            label = "Kyanos"
            label_color = "#e8e115"
            bg = "#111827"
            padding = "12px"

        html = f"""
        <div style="margin-bottom:14px;">
            <div style="font-size:11px; color:{label_color}; margin-bottom:4px;">
                {label}
            </div>
            <div style="
                background:{bg};
                border:1px solid #1f2937;
                padding:{padding};
                border-radius:10px;
                max-width:80%;
            ">
                {text}
            </div>
        </div>
        """

        self.chat.append(html)
        self.chat.verticalScrollBar().setValue(
            self.chat.verticalScrollBar().maximum()
        )

    def send(self):
        text = self.input.text().strip()
        if not text:
            return

        self.add_message("user", text)
        self.input.clear()

        self.worker = AIWorker(
            self.client,
            "You are Kyanos, a calm, clear, helpful study assistant.",
            text
        )
        self.worker.done.connect(lambda msg: self.add_message("ai", msg))
        self.worker.start()


# ================== CONTENT VIEW ==================
class ContentView(QWidget):
    def __init__(self, client, mode):
        super().__init__()
        self.client = client
        self.mode = mode

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title = QLabel(mode)
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))

        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter topic")

        self.output = QTextEdit(readOnly=True)
        self.output.setFont(QFont("Segoe UI", 11))

        btn = QPushButton("Generate")
        btn.clicked.connect(self.generate)

        layout.addWidget(title)
        layout.addWidget(self.input)
        layout.addWidget(btn)
        layout.addWidget(self.output)

    def generate(self):
        topic = self.input.text().strip()
        if not topic:
            return

        if self.mode == "Notes":
            prompt = f"Create concise, well-structured study notes on {topic}."
        elif self.mode == "Quiz":
            prompt = f"Create 5 MCQs on {topic} with options and correct answers."
        else:
            prompt = f"Create flashcards on {topic} in Q&A format."

        self.output.setText("Generating…")

        self.worker = AIWorker(
            self.client,
            "You are an expert educator.",
            prompt
        )
        self.worker.done.connect(self.output.setText)
        self.worker.start()


# ================== MAIN WINDOW ==================
class MainWindow(QMainWindow):
    def __init__(self, client):
        super().__init__()
        self.setWindowTitle("Kyanos")
        self.resize(1100, 720)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        sidebar = QVBoxLayout()
        sidebar_widget = QWidget()
        sidebar_widget.setLayout(sidebar)
        sidebar_widget.setFixedWidth(220)

        title = QLabel("Kyanos")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))

        btn_chat = QPushButton("Chat")
        btn_notes = QPushButton("Notes")
        btn_quiz = QPushButton("Quiz")
        btn_flash = QPushButton("Flashcards")

        for b in (btn_chat, btn_notes, btn_quiz, btn_flash):
            b.setFlat(True)
            sidebar.addWidget(b)

        sidebar.addStretch()
        sidebar_widget.layout().insertWidget(0, title)

        # Views
        self.chat = ChatView(client)
        self.notes = ContentView(client, "Notes")
        self.quiz = ContentView(client, "Quiz")
        self.flash = ContentView(client, "Flashcards")

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.addWidget(self.chat)

        def switch(view):
            while self.container_layout.count():
                self.container_layout.takeAt(0).widget().setParent(None)
            self.container_layout.addWidget(view)

        btn_chat.clicked.connect(lambda: switch(self.chat))
        btn_notes.clicked.connect(lambda: switch(self.notes))
        btn_quiz.clicked.connect(lambda: switch(self.quiz))
        btn_flash.clicked.connect(lambda: switch(self.flash))

        layout.addWidget(sidebar_widget)
        layout.addWidget(self.container)
        self.setCentralWidget(root)


# ================== ENTRY ==================
def main():
    app = QApplication(sys.argv)

    app.setStyleSheet("""
    QWidget {
        background:#020617;
        color:#e5e7eb;
        font-family: Segoe UI;
    }
    QLineEdit, QTextEdit {
        background:#111827;
        border:1px solid #1f2937;
        border-radius:10px;
        padding:10px;
    }
    QPushButton {
        color:#9ca3af;
        padding:8px;
        text-align:left;
        border:none;
    }
    QPushButton:hover {
        color:#7c7cff;
        background:#111827;
        border-radius:8px;
    }
    """)

    key = load_api_key()
    if not key:
        dlg = ApiKeyDialog()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            sys.exit()
        key = load_api_key()

    client = OpenAI(api_key=key)
    win = MainWindow(client)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
