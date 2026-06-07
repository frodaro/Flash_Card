import sys
import random
import os
import threading
import time
import ctypes
import platform
import subprocess
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

from gtts import gTTS
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QSpinBox, QComboBox,
    QGraphicsScene, QGraphicsView, QGraphicsProxyWidget, QScrollArea,
    QLineEdit, QGraphicsDropShadowEffect, QMessageBox
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject, QTimer, pyqtProperty
from PyQt6.QtGui import QFont, QTransform, QColor, QKeyEvent, QPalette, QPainter

# --- Costanti ---
DEFAULT_WORDS = [
    {"IT": "Mela", "DE": "Apfel", "category": "Cibo"},
    {"IT": "Gatto", "DE": "Katze", "category": "Animali"},
    {"IT": "Libro", "DE": "Buch", "category": "Oggetti"},
    {"IT": "Cane", "DE": "Hund", "category": "Animali"},
    {"IT": "Sole", "DE": "Sonne", "category": "Natura"},
    {"IT": "Acqua", "DE": "Wasser", "category": "Natura"},
    {"IT": "Tavolo", "DE": "Tisch", "category": "Oggetti"},
    {"IT": "Amico", "DE": "Freund", "category": "Persone"},
    {"IT": "Casa", "DE": "Haus", "category": "Luoghi"},
    {"IT": "Macchina", "DE": "Auto", "category": "Oggetti"},
]

CARD_SIZE = (400, 280)
ANIMATION_DURATION = 550  # ms
PERSPECTIVE_SHEAR_FACTOR = 0.12
AUDIO_CACHE_DIR = "audio_cache"
DATA_DIR = "data"
WORDS_FILE = Path(DATA_DIR) / "words.txt"
CATEGORIES_FILE = Path(DATA_DIR) / "categories.json"

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("flashcard_game.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# --- Enums ---
class Language(Enum):
    IT = auto()
    DE = auto()

class Difficulty(Enum):
    EASY = "Facile"
    MEDIUM = "Medio"
    HARD = "Difficile"

# --- Dataclasses ---
@dataclass
class Word:
    it: str
    de: str
    category: str = "Generale"

@dataclass
class Player:
    name: str
    emoji: str
    score: int = 0

@dataclass
class GameSettings:
    num_players: int = 1
    difficulty: Difficulty = Difficulty.MEDIUM
    selected_categories: List[str] = field(default_factory=list)
    timer_enabled: bool = False
    timer_seconds: int = 10

# --- Segnali personalizzati ---
class AudioSignal(QObject):
    audio_finished = pyqtSignal()
    audio_error = pyqtSignal(str)
    audio_done = pyqtSignal()  # emesso sempre a fine riproduzione (thread-safe)

# --- Audio Player (Cross-Platform) ---
class AudioPlayer:
    """Gestore audio asincrono e cross-platform per TTS."""

    def __init__(self, cache_dir: str = AUDIO_CACHE_DIR):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.is_speaking = False
        self.current_thread: Optional[threading.Thread] = None
        self.signal = AudioSignal()

    def speak(self, text: str, lang: str, button_to_disable: QPushButton) -> None:
        """Avvia la riproduzione audio di un testo."""
        if self.is_speaking:
            logger.warning("Audio già in riproduzione. Ignoro la richiesta.")
            return

        self.is_speaking = True
        # La disabilitazione avviene sul thread GUI (chiamante): è sicura.
        button_to_disable.setEnabled(False)

        if self.current_thread and self.current_thread.is_alive():
            self.current_thread.join(timeout=0.1)

        self.current_thread = threading.Thread(
            target=self._play,
            args=(text, lang),
            daemon=True
        )
        self.current_thread.start()

    def _play(self, text: str, lang: str) -> None:
        """Riproduce l'audio in un thread separato."""
        try:
            safe_word = "".join(
                c for c in text.lower() if c.isalnum() or c == " "
            ).replace(" ", "_")
            cache_file = self.cache_dir / f"{safe_word}_{lang}.mp3"

            # Genera il file audio se non esiste
            if not cache_file.exists():
                logger.info(f"Genero audio per: {text} ({lang})")
                gTTS(text=text, lang=lang, slow=False).save(str(cache_file))

            # Riproduzione cross-platform
            if platform.system() == "Windows":
                self._play_windows(cache_file)
            elif platform.system() == "Darwin":  # macOS
                self._play_macos(cache_file)
            else:  # Linux e altri
                self._play_linux(cache_file)

            self.signal.audio_finished.emit()
        except Exception as e:
            logger.error(f"Errore riproduzione audio: {e}")
            self.signal.audio_error.emit(str(e))
        finally:
            self.is_speaking = False
            # La riabilitazione del bottone va fatta sul thread GUI: si delega
            # tramite segnale invece di toccare il widget da questo thread.
            self.signal.audio_done.emit()

    def _play_windows(self, cache_file: Path) -> None:
        """Riproduzione audio su Windows usando winmm."""
        winmm = ctypes.windll.winmm
        winmm.mciSendStringW(f'open "{cache_file}" type mpegvideo alias f_audio', None, 0, 0)
        winmm.mciSendStringW('play f_audio', None, 0, 0)

        while True:
            buf = ctypes.create_unicode_buffer(256)
            winmm.mciSendStringW('status f_audio mode', buf, 256, 0)
            if 'stopped' in buf.value or buf.value == '':
                break
            time.sleep(0.05)

        winmm.mciSendStringW('close f_audio', None, 0, 0)

    def _play_macos(self, cache_file: Path) -> None:
        """Riproduzione audio su macOS usando afplay."""
        subprocess.run(["afplay", str(cache_file)], check=True)

    def _play_linux(self, cache_file: Path) -> None:
        """Riproduzione audio su Linux usando aplay o paplay."""
        try:
            subprocess.run(["aplay", str(cache_file)], check=True)
        except FileNotFoundError:
            subprocess.run(["paplay", str(cache_file)], check=True)

# --- Flipped Card (3D) ---
class FlippedCard(QWidget):
    """Widget personalizzato per la carta 3D con animazione di flip."""

    # Segnale emesso quando l'angolo cambia
    angle_changed = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._angle = 0.0
        self.is_flipped = False
        self.text_it = ""
        self.text_de = ""
        self.current_lang = Language.IT

        # Imposta dimensioni fisse
        self.setFixedSize(*CARD_SIZE)

        # Layout e label
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(
            "color: #0f172a; font-weight: bold; font-size: 32px; background: transparent;"
        )
        self.layout.addWidget(self.label)

        # Stile della carta
        self.setStyleSheet("""
            FlippedCard {
                background-color: white;
                border-radius: 20px;
                border: 2px solid #e0e7ff;
            }
        """)

        # Effetto ombra
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 120))
        shadow.setOffset(0, 10)
        self.setGraphicsEffect(shadow)

    @pyqtProperty(float)
    def angle(self) -> float:
        return self._angle

    @angle.setter
    def angle(self, val: float) -> None:
        self._angle = val
        self._update_text_based_on_angle()
        self.update()
        self.angle_changed.emit(val)  # Emetti il segnale quando l'angolo cambia

    def _update_text_based_on_angle(self) -> None:
        """Aggiorna il testo in base all'angolo di rotazione."""
        if self._angle >= 90 and not self.is_flipped:
            self.is_flipped = True
            self.current_lang = Language.DE
            self.label.setText(self.text_de)
        elif self._angle < 90 and self.is_flipped:
            self.is_flipped = False
            self.current_lang = Language.IT
            self.label.setText(self.text_it)

    def set_words(self, it: str, de: str, current_lang: Language) -> None:
        """Imposta le parole sulla carta."""
        self.text_it = it
        self.text_de = de
        self.current_lang = current_lang
        self.is_flipped = (current_lang == Language.DE)
        self.label.setText(de if self.is_flipped else it)
        self._angle = 180 if self.is_flipped else 0

    def flip(self) -> None:
        """Inverte la carta istantaneamente (senza animazione)."""
        self.is_flipped = not self.is_flipped
        self._angle = 180 if self.is_flipped else 0
        self._update_text_based_on_angle()

# --- Game Window (Main) ---
class GameWindow(QMainWindow):
    """Finestra principale del gioco delle flashcard 3D."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flashcard Tedesco 3D 🇩🇪🇮🇹")
        self.resize(1000, 800)

        # Inizializza i widget a None per evitare errori e gestire la rimozione
        self.game_widget = None
        self.names_widget = None
        self.end_widget = None

        # Imposta lo stile globale
        self._setup_global_style()

        # Variabili di stato
        self.words: List[Word] = []
        self.all_words: List[Word] = []  # elenco completo immutato (sorgente del filtro)
        self.players: List[Player] = []
        self.current_player_idx = 0
        self.current_word_idx = 0
        self.current_lang = Language.IT
        self.settings = GameSettings()
        self.timer: Optional[QTimer] = None
        self.time_left = 0

        # Audio
        self.audio = AudioPlayer()
        self.audio.signal.audio_finished.connect(self._on_audio_finished)
        self.audio.signal.audio_error.connect(self._on_audio_error)
        self.audio.signal.audio_done.connect(self._on_audio_done)

        # Interfaccia
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Carica i dati e inizializza l'interfaccia
        self._load_data()
        self._init_setup_ui()

    def _setup_global_style(self) -> None:
        """Imposta lo stile globale dell'applicazione."""
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#e0e7ff"))
        self.setPalette(palette)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QLabel {
                color: #e0e7ff;
            }
            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e3a5f;
            }
            QPushButton:disabled {
                opacity: 0.6;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #1e293b;
                color: #e0e7ff;
                border: 1px solid #334155;
                border-radius: 5px;
                padding: 8px;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

    def _load_data(self) -> None:
        """Carica le parole e le categorie dai file."""
        # Crea le directory se non esistono
        Path(DATA_DIR).mkdir(exist_ok=True)
        self.audio.cache_dir.mkdir(exist_ok=True)

        # Carica le parole
        if not WORDS_FILE.exists():
            self._save_default_words()
        else:
            try:
                with open(WORDS_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and "|" in line:
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) >= 2:
                                category = parts[2] if len(parts) > 2 else "Generale"
                                self.words.append(
                                    Word(it=parts[0], de=parts[1], category=category)
                                )
                logger.info(f"Caricate {len(self.words)} parole da {WORDS_FILE}")
            except Exception as e:
                logger.error(f"Errore caricamento parole: {e}")
                self._save_default_words()

        # Carica le categorie (opzionale)
        if CATEGORIES_FILE.exists():
            try:
                with open(CATEGORIES_FILE, "r", encoding="utf-8") as f:
                    categories = json.load(f)
                    self.settings.selected_categories = categories.get("selected", [])
            except Exception as e:
                logger.error(f"Errore caricamento categorie: {e}")

        # Mescola le parole e conserva l'elenco completo come sorgente del filtro
        random.shuffle(self.words)
        self.all_words = list(self.words)

    def _save_default_words(self) -> None:
        """Salva le parole predefinite nel file."""
        with open(WORDS_FILE, "w", encoding="utf-8") as f:
            for word in DEFAULT_WORDS:
                f.write(f"{word['IT']}|{word['DE']}|{word['category']}\n")
        logger.info(f"Salvate {len(DEFAULT_WORDS)} parole predefinite in {WORDS_FILE}")

    def _init_setup_ui(self) -> None:
        """Inizializza l'interfaccia di configurazione iniziale."""
        setup_widget = QWidget()
        layout = QVBoxLayout(setup_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        # Titolo
        title = QLabel("🎓 FLASHCARD TEDESCO 3D")
        title.setStyleSheet(
            "color: #00d4ff; font-size: 42px; font-weight: bold; margin-bottom: 10px;"
        )
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Sottotitolo
        subtitle = QLabel("Impara il tedesco divertendoti!")
        subtitle.setStyleSheet("color: #64748b; font-size: 16px;")
        layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignCenter)

        # Numero giocatori
        lbl_players = QLabel("Quanti giocatori?")
        lbl_players.setStyleSheet("color: #e0e7ff; font-size: 18px;")
        layout.addWidget(lbl_players, alignment=Qt.AlignmentFlag.AlignCenter)

        self.spin_players = QSpinBox()
        self.spin_players.setRange(1, 10)
        self.spin_players.setValue(1)
        self.spin_players.setStyleSheet(
            "background: #1e293b; color: #00d4ff; font-size: 20px; padding: 10px; border-radius: 8px;"
        )
        self.spin_players.setFixedWidth(100)
        self.spin_players.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.spin_players, alignment=Qt.AlignmentFlag.AlignCenter)

        # Difficoltà
        lbl_difficulty = QLabel("Difficoltà:")
        lbl_difficulty.setStyleSheet("color: #e0e7ff; font-size: 18px;")
        layout.addWidget(lbl_difficulty, alignment=Qt.AlignmentFlag.AlignCenter)

        self.combo_difficulty = QComboBox()
        self.combo_difficulty.addItems([d.value for d in Difficulty])
        self.combo_difficulty.setCurrentIndex(1)  # Medio
        self.combo_difficulty.setStyleSheet(
            "background: #1e293b; color: #00d4ff; font-size: 16px; padding: 8px; border-radius: 8px;"
        )
        layout.addWidget(self.combo_difficulty, alignment=Qt.AlignmentFlag.AlignCenter)

        # Timer
        self.chk_timer = QPushButton("⏱️ Timer: 10s")
        self.chk_timer.setCheckable(True)
        self.chk_timer.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #00d4ff;
                font-size: 16px;
                padding: 8px 16px;
                border-radius: 8px;
            }
            QPushButton:checked {
                background-color: #00d4ff;
                color: #0f172a;
            }
        """)
        self.chk_timer.clicked.connect(self._toggle_timer)
        layout.addWidget(self.chk_timer, alignment=Qt.AlignmentFlag.AlignCenter)

        # Pulsante continua
        btn_continue = QPushButton("Continua ➜")
        btn_continue.setStyleSheet(
            "background-color: #00d4ff; color: #0f172a; font-size: 16px; font-weight: bold; "
            "padding: 15px 40px; border-radius: 8px; margin-top: 10px;"
        )
        btn_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_continue.clicked.connect(self._init_names_ui)
        layout.addWidget(btn_continue, alignment=Qt.AlignmentFlag.AlignCenter)

        self.stacked_widget.addWidget(setup_widget)

    def _toggle_timer(self) -> None:
        """Attiva/disattiva il timer."""
        self.settings.timer_enabled = self.chk_timer.isChecked()
        if self.settings.timer_enabled:
            self.chk_timer.setText("⏱️ Timer: 10s (attivo)")
        else:
            self.chk_timer.setText("⏱️ Timer: 10s")

    def _init_names_ui(self) -> None:
        """Inizializza l'interfaccia per l'inserimento dei nomi dei giocatori."""
        self.settings.num_players = self.spin_players.value()
        self.settings.difficulty = Difficulty(self.combo_difficulty.currentText())

        # Rimuovi l'eventuale schermata nomi precedente per non accumularla nello stack
        if self.names_widget is not None:
            self.stacked_widget.removeWidget(self.names_widget)
            self.names_widget.deleteLater()

        names_widget = QWidget()
        self.names_widget = names_widget
        main_layout = QVBoxLayout(names_widget)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # Titolo
        title = QLabel("👥 NOMI E ICONE")
        title.setStyleSheet("color: #00d4ff; font-size: 28px; font-weight: bold;")
        main_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Scroll area per i giocatori
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_layout.setSpacing(10)

        # Emoji disponibili
        emojis = ["🦁", "🐯", "🐻", "🐼", "🦊", "🐨", "🦘", "🐧", "🦅", "🦈", "👑", "🎮", "🎨", "🚀", "🌟"]

        # Input per ogni giocatore
        self.name_inputs: List[QLineEdit] = []
        self.emoji_inputs: List[QComboBox] = []

        for i in range(self.settings.num_players):
            row = QWidget()
            row.setStyleSheet("background-color: #1e293b; border-radius: 10px; padding: 10px;")
            row_layout = QHBoxLayout(row)
            row_layout.setSpacing(10)

            # Label giocatore
            lbl = QLabel(f"Giocatore {i+1}:")
            lbl.setStyleSheet("color: #00d4ff; font-weight: bold; font-size: 14px;")
            row_layout.addWidget(lbl)

            # Input nome
            entry = QLineEdit()
            entry.setPlaceholderText(f"Nome {i+1}")
            entry.setStyleSheet(
                "background-color: #0f172a; color: white; padding: 8px; "
                "border-radius: 5px; border: 1px solid #334155;"
            )
            row_layout.addWidget(entry)
            self.name_inputs.append(entry)

            # Input emoji
            combo = QComboBox()
            combo.addItems(emojis)
            combo.setCurrentIndex(i % len(emojis))
            combo.setStyleSheet(
                "background-color: #0f172a; color: white; padding: 5px; border-radius: 5px;"
            )
            row_layout.addWidget(combo)
            self.emoji_inputs.append(combo)

            scroll_layout.addWidget(row)

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # Pulsante inizia
        btn_start = QPushButton("Inizia Gioco! 🚀")
        btn_start.setStyleSheet(
            "background-color: #00d4ff; color: #0f172a; font-size: 18px; font-weight: bold; "
            "padding: 15px 40px; border-radius: 8px; margin-top: 20px;"
        )
        btn_start.clicked.connect(self._start_game)
        main_layout.addWidget(btn_start, alignment=Qt.AlignmentFlag.AlignCenter)

        self.stacked_widget.addWidget(names_widget)
        self.stacked_widget.setCurrentWidget(names_widget)

    def _start_game(self) -> None:
        """Avvia il gioco con i giocatori configurati."""
        self.players = []
        for i in range(len(self.name_inputs)):
            name = self.name_inputs[i].text().strip() or f"Giocatore {i+1}"
            emoji = self.emoji_inputs[i].currentText()
            self.players.append(Player(name=name, emoji=emoji, score=0))

        # Filtra le parole in base alla difficoltà e alle categorie
        self._filter_words()

        # Evita di avviare una partita senza parole (es. filtro troppo restrittivo)
        if not self.words:
            QMessageBox.warning(
                self,
                "Nessuna parola",
                "Nessuna parola corrisponde ai filtri selezionati.\n"
                "Prova a cambiare difficoltà o categoria.",
            )
            self.stacked_widget.setCurrentIndex(0)
            return

        # Inizializza l'interfaccia di gioco
        self._init_game_ui()

    def _filter_words(self) -> None:
        """Filtra le parole in base alla difficoltà e alle categorie selezionate.

        Parte sempre dall'elenco completo `self.all_words` per non perdere parole
        tra una partita e l'altra (il filtro non è più distruttivo).
        """
        filtered_words = []
        for word in self.all_words:
            # Filtro per difficoltà (esempio: parole corte = facile)
            if self.settings.difficulty == Difficulty.EASY and len(word.it) > 6:
                continue
            elif self.settings.difficulty == Difficulty.HARD and len(word.it) < 5:
                continue

            # Filtro per categorie (se selezionate)
            if self.settings.selected_categories:
                if word.category not in self.settings.selected_categories:
                    continue

            filtered_words.append(word)

        self.words = filtered_words
        random.shuffle(self.words)
        logger.info(f"Parole filtrate: {len(self.words)}")

    def _init_game_ui(self) -> None:
        """Inizializza l'interfaccia di gioco."""
        # Rimuovi l'eventuale schermata di gioco precedente (es. dopo un riavvio)
        if self.game_widget is not None:
            self.stacked_widget.removeWidget(self.game_widget)
            self.game_widget.deleteLater()

        self.game_widget = QWidget()
        layout = QVBoxLayout(self.game_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 20, 40, 20)

        # Layout punteggi
        self.score_layout = QHBoxLayout()
        self.score_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.score_layout.setSpacing(10)
        layout.addLayout(self.score_layout)

        # Progresso
        self.lbl_progress = QLabel()
        self.lbl_progress.setStyleSheet(
            "color: #64748b; font-size: 16px; font-weight: bold;"
        )
        layout.addWidget(self.lbl_progress, alignment=Qt.AlignmentFlag.AlignCenter)

        # Vista 3D della carta
        self.scene = QGraphicsScene(self)
        # IMPOSTA LE DIMENSIONI DELLA SCENA (FONDAMENTALE!)
        self.scene.setSceneRect(0, 0, 500, 380)  # Stesse dimensioni del view

        self.view = QGraphicsView(self.scene, self.game_widget)
        self.view.setFixedSize(500, 380)
        self.view.setStyleSheet("background: transparent; border: 1px solid #334155;")  # Bordino per debug
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)  # Miglioramento grafico

        # Widget della carta
        self.card_widget = FlippedCard()
        self.proxy = self.scene.addWidget(self.card_widget)
        self.proxy.setTransformOriginPoint(CARD_SIZE[0] / 2, CARD_SIZE[1] / 2)
        # POSIZIONA LA CARTA AL CENTRO DELLA SCENA
        self.proxy.setPos(50, 50)  # (500-400)/2 = 50, (380-280)/2 = 50

        # Connetti il segnale per l'animazione
        self.card_widget.angle_changed.connect(self._apply_perspective_transform)

       # Gestione click sulla carta
        self.view.mousePressEvent = lambda e: self._animate_card_flip()

        layout.addWidget(self.view, alignment=Qt.AlignmentFlag.AlignCenter)

        # Suggerimento
        self.lbl_hint = QLabel("Clicca sulla carta per girarla | Spazio per flip | Freccia DX/SX per risposta")
        self.lbl_hint.setStyleSheet(
            "color: #64748b; font-style: italic; font-size: 12px;"
        )
        layout.addWidget(self.lbl_hint, alignment=Qt.AlignmentFlag.AlignCenter)

        # Pulsanti azione
        actions_layout = QHBoxLayout()
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        actions_layout.setSpacing(20)

        # Pulsante audio
        self.btn_audio = QPushButton("🔊 Ascolta")
        self.btn_audio.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6; color: white; font-weight: bold;
                font-size: 16px; padding: 12px 24px; border-radius: 8px;
            }
            QPushButton:pressed {
                background-color: #2563eb;
            border: 1px solid #1d4ed8;
            }
        """)
        self.btn_audio.clicked.connect(self._play_word_audio)
        actions_layout.addWidget(self.btn_audio)

        # Pulsante sbagliato
        btn_wrong = QPushButton("❌ SBAGLIATO")
        btn_wrong.setStyleSheet("""
            QPushButton {
                background-color: #ef4444; color: white; font-weight: bold;
                font-size: 16px; padding: 12px 24px; border-radius: 8px;
            }
            QPushButton:pressed {
                background-color: #dc2626;
                border: 1px solid #b91c1c;
            }
        """)
        btn_wrong.clicked.connect(lambda: self._handle_answer(False))
        actions_layout.addWidget(btn_wrong)

        # Pulsante giusto
        btn_correct = QPushButton("✅ GIUSTO")
        btn_correct.setStyleSheet("""
            QPushButton {
                background-color: #22c55e; color: white; font-weight: bold;
                font-size: 16px; padding: 12px 24px; border-radius: 8px;
            }
            QPushButton:pressed {
                background-color: #16a34a;
                border: 1px solid #15803d;
            }
        """)
        btn_correct.clicked.connect(lambda: self._handle_answer(True))
        actions_layout.addWidget(btn_correct)

        layout.addLayout(actions_layout)

        # Timer (se attivato)
        if self.settings.timer_enabled:
            self._start_timer()

        # Aggiungi il widget al stacked widget
        self.stacked_widget.addWidget(self.game_widget)
        self.stacked_widget.setCurrentWidget(self.game_widget)

        # Mostra la prima parola
        self._show_word()

        # Abilita la gestione della tastiera
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _start_timer(self) -> None:
        """Avvia il timer per la parola corrente."""
        self.time_left = self.settings.timer_seconds
        self.lbl_progress.setText(
            f"Parola {self.current_word_idx + 1} di {len(self.words)} | ⏳ {self.time_left}s"
        )

        if self.timer and self.timer.isActive():
            self.timer.stop()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_timer)
        self.timer.start(1000)  # 1 secondo

    def _update_timer(self) -> None:
        """Aggiorna il timer."""
        self.time_left -= 1
        self.lbl_progress.setText(
            f"Parola {self.current_word_idx + 1} di {len(self.words)} | ⏳ {self.time_left}s"
        )

        if self.time_left <= 0:
            self.timer.stop()
            self._handle_answer(False)  # Tempo scaduto = sbagliato

    def _apply_perspective_transform(self, angle: float) -> None:
        """Applica la trasformazione 3D con prospettiva alla carta."""
        transform = QTransform()

        # Trasla al centro
        transform.translate(CARD_SIZE[0] / 2, CARD_SIZE[1] / 2)

        # Ruota intorno all'asse Y
        transform.rotate(angle, Qt.Axis.YAxis)

        # Applica shear per la prospettiva
        if angle != 0 and angle != 180:
            shear_factor = PERSPECTIVE_SHEAR_FACTOR * (abs(angle - 90) / 90.0) * (-1 if angle > 90 else 1)
            transform.shear(0, shear_factor)

        # Trasla indietro
        transform.translate(-CARD_SIZE[0] / 2, -CARD_SIZE[1] / 2)

        self.proxy.setTransform(transform)

    def _animate_card_flip(self) -> None:
        """Anima il flip della carta."""
        if hasattr(self, 'anim') and self.anim.state() == QPropertyAnimation.State.Running:
            return

        start_ang = 0 if self.current_lang == Language.IT else 180
        end_ang = 180 if self.current_lang == Language.IT else 0
        self.current_lang = Language.DE if self.current_lang == Language.IT else Language.IT

        self.anim = QPropertyAnimation(self.card_widget, b"angle")
        self.anim.setDuration(ANIMATION_DURATION)
        self.anim.setStartValue(float(start_ang))
        self.anim.setEndValue(float(end_ang))
        self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim.start()

    def _show_word(self) -> None:
        """Mostra la parola corrente."""
        if self.current_word_idx < len(self.words):
            self.current_lang = Language.IT
            word = self.words[self.current_word_idx]
            self.card_widget.set_words(word.it, word.de, self.current_lang)
            self.lbl_progress.setText(
                f"Parola {self.current_word_idx + 1} di {len(self.words)}"
            )
            self.proxy.setTransform(QTransform())

            # Reimposta il timer se attivato
            if self.settings.timer_enabled:
                self._start_timer()
        else:
            self._show_end_ui()

    def _play_word_audio(self) -> None:
        """Riproduce l'audio della parola corrente."""
        if self.current_word_idx < len(self.words):
            word = self.words[self.current_word_idx]
            text = word.it if self.current_lang == Language.IT else word.de
            lang_code = "it" if self.current_lang == Language.IT else "de"
            self.audio.speak(text, lang_code, self.btn_audio)

    def _on_audio_finished(self) -> None:
        """Callback quando l'audio finisce."""
        logger.info("Riproduzione audio completata")

    def _on_audio_done(self) -> None:
        """Riabilita il bottone audio sul thread GUI (chiamato sempre)."""
        if hasattr(self, "btn_audio") and self.btn_audio is not None:
            self.btn_audio.setEnabled(True)

    def _on_audio_error(self, error: str) -> None:
        """Callback in caso di errore audio."""
        logger.error(f"Errore audio: {error}")
        QMessageBox.warning(self, "Errore Audio", f"Si è verificato un errore: {error}")

    def _handle_answer(self, is_correct: bool) -> None:
        """Gestisce la risposta del giocatore."""
        if self.current_word_idx >= len(self.words):
            return

        # Feedback visivo
        if is_correct:
            self._show_feedback("✅ Corretto!", "#22c55e")
            self.players[self.current_player_idx].score += 1
        else:
            self._show_feedback("❌ Sbagliato!", "#ef4444")

        # Passa alla parola successiva
        self.current_word_idx += 1
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
        self._update_score_ui()
        self._show_word()

    def _show_feedback(self, message: str, color: str) -> None:
        """Mostra un feedback visivo temporaneo."""
        feedback = QLabel(message)
        feedback.setStyleSheet(
            f"color: white; background-color: {color}; "
            "font-size: 24px; font-weight: bold; padding: 20px; "
            "border-radius: 10px; margin: 10px;"
        )
        feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Aggiungi temporaneamente al layout
        self.game_widget.layout().insertWidget(0, feedback)

        # Rimuovi dopo 1 secondo
        QTimer.singleShot(1000, feedback.deleteLater)

    def _update_score_ui(self) -> None:
        """Aggiorna l'interfaccia dei punteggi."""
        # Rimuovi tutti i widget attuali
        while self.score_layout.count():
            item = self.score_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Aggiungi i punteggi aggiornati
        for i, player in enumerate(self.players):
            lbl = QLabel(f" {player.emoji} {player.name}: {player.score} ")
            if i == self.current_player_idx:
                lbl.setStyleSheet(
                    "background-color: #00d4ff; color: #0f172a; "
                    "font-weight: bold; font-size: 16px; padding: 10px 15px; border-radius: 8px;"
                )
            else:
                lbl.setStyleSheet(
                    "background-color: #1e293b; color: #00d4ff; "
                    "font-weight: bold; font-size: 16px; padding: 10px 15px; border-radius: 8px;"
                )
            self.score_layout.addWidget(lbl)

    def _show_end_ui(self) -> None:
        """Mostra l'interfaccia di fine gioco."""
        # Ferma il timer se attivo
        if self.timer and self.timer.isActive():
            self.timer.stop()

        # Rimuovi l'eventuale schermata di fine gioco precedente
        if self.end_widget is not None:
            self.stacked_widget.removeWidget(self.end_widget)
            self.end_widget.deleteLater()

        end_widget = QWidget()
        self.end_widget = end_widget
        layout = QVBoxLayout(end_widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 40, 40, 40)

        # Titolo
        title = QLabel("🎉 GIOCO FINITO!")
        title.setStyleSheet("color: #22c55e; font-size: 42px; font-weight: bold;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignCenter)

        # Sottotitolo
        subtitle = QLabel("Ecco i risultati finali!")
        subtitle.setStyleSheet("color: #64748b; font-size: 18px;")
        layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignCenter)

        # Classifica
        lbl_rank = QLabel("📋 CLASSIFICA FINALE")
        lbl_rank.setStyleSheet("color: #00d4ff; font-size: 20px; font-weight: bold;")
        layout.addWidget(lbl_rank, alignment=Qt.AlignmentFlag.AlignCenter)

        # Ordina i giocatori per punteggio
        sorted_players = sorted(self.players, key=lambda p: p.score, reverse=True)

        for idx, player in enumerate(sorted_players, 1):
            medal = ["🥇", "🥈", "🥉"][idx-1] if idx <= 3 else f"{idx}."
            color = ["#22c55e", "#f59e0b", "#ef4444", "#e0e7ff"][min(idx-1, 3)]

            lbl_p = QLabel(f"{medal} {player.emoji} {player.name}: {player.score} punti")
            lbl_p.setStyleSheet(
                f"color: {color}; font-size: 20px; font-weight: bold; margin: 8px;"
            )
            layout.addWidget(lbl_p, alignment=Qt.AlignmentFlag.AlignCenter)

        # Pulsante riavvia
        btn_restart = QPushButton("🔄 Gioca Ancora")
        btn_restart.setStyleSheet(
            "background-color: #00d4ff; color: #0f172a; font-size: 18px; "
            "font-weight: bold; padding: 15px 40px; border-radius: 8px; margin-top: 20px;"
        )
        btn_restart.clicked.connect(self._restart_game)
        layout.addWidget(btn_restart, alignment=Qt.AlignmentFlag.AlignCenter)

        # Pulsante menu principale
        btn_menu = QPushButton("🏠 Menu Principale")
        btn_menu.setStyleSheet(
            "background-color: #64748b; color: white; font-size: 16px; "
            "font-weight: bold; padding: 12px 30px; border-radius: 8px;"
        )
        btn_menu.clicked.connect(self._return_to_menu)
        layout.addWidget(btn_menu, alignment=Qt.AlignmentFlag.AlignCenter)

        self.stacked_widget.addWidget(end_widget)
        self.stacked_widget.setCurrentWidget(end_widget)

    def _restart_game(self) -> None:
        """Riavvia il gioco con le stesse impostazioni."""
        self.current_word_idx = 0
        self.current_player_idx = 0
        self.current_lang = Language.IT

        # Reimposta i punteggi
        for player in self.players:
            player.score = 0

        # Mescola di nuovo le parole
        random.shuffle(self.words)

        # Torna all'interfaccia di gioco
        self._init_game_ui()

    def _return_to_menu(self) -> None:
        """Torna al menu principale."""
        self.stacked_widget.setCurrentIndex(0)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Gestisce gli eventi della tastiera."""
        # Controlla se game_widget esiste e se è il widget corrente
        if not hasattr(self, 'game_widget') or self.stacked_widget.currentWidget() != self.game_widget:
            return super().keyPressEvent(event)

        if event.key() == Qt.Key.Key_Space:
            self._animate_card_flip()
        elif event.key() == Qt.Key.Key_Right:
            self._handle_answer(True)
        elif event.key() == Qt.Key.Key_Left:
            self._handle_answer(False)
        elif event.key() == Qt.Key.Key_A:
            self._play_word_audio()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """Gestisce la chiusura della finestra."""
        if self.timer and self.timer.isActive():
            self.timer.stop()
        event.accept()

# --- Main ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Flashcard Tedesco 3D")
    app.setStyle("Fusion")  # Stile moderno

    window = GameWindow()
    window.show()
    sys.exit(app.exec())