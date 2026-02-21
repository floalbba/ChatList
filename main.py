"""ChatList — отправка промта в несколько нейросетей и сравнение ответов."""

import sys
import logging
from pathlib import Path

# Настройка логирования в терминал
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
    force=True,
)
log = logging.getLogger(__name__)

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QTextBrowser,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
    QProgressBar,
    QDialog,
    QFormLayout,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QHeaderView,
    QAbstractItemView,
    QFileDialog,
    QTabWidget,
    QScrollArea,
    QMenuBar,
    QMenu,
    QAction,
    QSpinBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QPalette, QColor

import db
import models as models_module
import network
import temp_results
import prompt_improver


class SendWorker(QThread):
    """Поток для отправки запросов без блокировки UI."""
    finished = pyqtSignal(list)  # list of {model, response, error}

    def __init__(self, models: list, prompt: str):
        super().__init__()
        self.models = models
        self.prompt = prompt

    def run(self):
        log.info("Отправка запроса в %d моделей...", len(self.models))
        for m in self.models:
            log.info("  → %s", m["name"])
        results = network.send_prompt_to_models(self.models, self.prompt)
        ok = sum(1 for r in results if r["error"] is None)
        log.info("Получено ответов: %d/%d", ok, len(results))
        for r in results:
            if r["error"]:
                log.warning("  %s: %s", r["model"]["name"], r["error"])
            else:
                log.info("  %s: OK (%d символов)", r["model"]["name"], len(r["response"]))
        self.finished.emit(results)


class ImproveWorker(QThread):
    """Поток для улучшения промта."""
    finished = pyqtSignal(object, object)  # result, error

    def __init__(self, original: str, model: dict):
        super().__init__()
        self.original = original
        self.model = model

    def run(self):
        result, error = prompt_improver.improve_prompt(
            self.original, self.model
        )
        self.finished.emit(result, error)


class PromptImproverDialog(QDialog):
    """Диалог улучшения промта с AI-ассистентом."""

    def __init__(self, original_prompt: str, prompt_edit_ref, parent=None):
        super().__init__(parent)
        self.original_prompt = original_prompt
        self.prompt_edit_ref = prompt_edit_ref
        self.result = None
        self.setWindowTitle("Улучшить промт")
        self.setMinimumSize(650, 550)
        self.resize(800, 600)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Модель:"))
        self.model_combo = QComboBox()
        models = models_module.get_active_models()
        saved_id = db.get_setting("improver_model_id")
        for i, m in enumerate(models):
            self.model_combo.addItem(m["name"], m)
            if saved_id and str(m["id"]) == saved_id:
                self.model_combo.setCurrentIndex(i)
        model_row.addWidget(self.model_combo, 1)
        self.btn_start = QPushButton("Запустить")
        self.btn_start.clicked.connect(self.start_improvement)
        model_row.addWidget(self.btn_start)
        layout.addLayout(model_row)

        layout.addWidget(QLabel("Исходный промт:"))
        self.original_edit = QTextEdit()
        self.original_edit.setReadOnly(True)
        self.original_edit.setPlainText(self.original_prompt)
        self.original_edit.setMaximumHeight(80)
        layout.addWidget(self.original_edit)

        self.tabs = QTabWidget()
        self.tab_improved = QWidget()
        tab_improved_layout = QVBoxLayout(self.tab_improved)
        tab_improved_layout.addWidget(QLabel("Улучшенный промт:"))
        self.improved_edit = QTextEdit()
        self.improved_edit.setReadOnly(True)
        tab_improved_layout.addWidget(self.improved_edit)
        self.btn_use_improved = QPushButton("Подставить в поле ввода")
        self.btn_use_improved.clicked.connect(lambda: self.use_text(self.improved_edit.toPlainText()))
        tab_improved_layout.addWidget(self.btn_use_improved)
        self.tabs.addTab(self.tab_improved, "Улучшенный")

        self.tab_variants = QWidget()
        tab_variants_layout = QVBoxLayout(self.tab_variants)
        tab_variants_layout.addWidget(QLabel("Альтернативные варианты:"))
        self.variants_widget = QWidget()
        self.variants_layout = QVBoxLayout(self.variants_widget)
        scroll = QScrollArea()
        scroll.setWidget(self.variants_widget)
        scroll.setWidgetResizable(True)
        tab_variants_layout.addWidget(scroll)
        self.tabs.addTab(self.tab_variants, "Варианты")

        self.tab_adapted = QWidget()
        tab_adapted_layout = QVBoxLayout(self.tab_adapted)
        tab_adapted_layout.addWidget(QLabel("Адаптация под разные задачи:"))
        self.adapted_edits = {}
        for key, label in [("code", "Код"), ("analysis", "Анализ"), ("creative", "Креатив")]:
            tab_adapted_layout.addWidget(QLabel(f"{label}:"))
            edit = QTextEdit()
            edit.setReadOnly(True)
            edit.setMaximumHeight(100)
            self.adapted_edits[key] = edit
            tab_adapted_layout.addWidget(edit)
            btn = QPushButton(f"Подставить ({label})")
            btn.clicked.connect(lambda checked, e=edit: self.use_text(e.toPlainText()))
            tab_adapted_layout.addWidget(btn)
        self.tabs.addTab(self.tab_adapted, "Адаптация")

        layout.addWidget(self.tabs)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.progress)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def start_improvement(self):
        model = self.model_combo.currentData()
        if not model:
            self.error_label.setText("Нет активных моделей.")
            return
        db.set_setting("improver_model_id", str(model["id"]))
        self.btn_start.setEnabled(False)
        self.progress.setVisible(True)
        self.error_label.clear()
        self.worker = ImproveWorker(self.original_prompt, model)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, result: dict, error: str):
        self.progress.setVisible(False)
        self.btn_start.setEnabled(True)
        if error:
            self.error_label.setText(error)
            return
        self.result = result
        self.improved_edit.setPlainText(result.get("improved", ""))
        for i, v in enumerate(result.get("variants", [])):
            w = QWidget()
            l = QVBoxLayout(w)
            l.addWidget(QLabel(f"Вариант {i + 1}:"))
            e = QTextEdit()
            e.setReadOnly(True)
            e.setPlainText(v)
            e.setMaximumHeight(80)
            l.addWidget(e)
            btn = QPushButton("Подставить")
            btn.clicked.connect(lambda checked, t=v: self.use_text(t))
            l.addWidget(btn)
            self.variants_layout.addWidget(w)
        for key, edit in self.adapted_edits.items():
            edit.setPlainText(result.get("adapted", {}).get(key, ""))

    def use_text(self, text: str):
        if self.prompt_edit_ref and text:
            self.prompt_edit_ref.setPlainText(text)
        self.accept()


class MarkdownViewerDialog(QDialog):
    """Диалог просмотра ответа в форматированном Markdown."""

    def __init__(self, model_name: str, response: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Ответ: {model_name}")
        self.setMinimumSize(600, 500)
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"<b>{model_name}</b>"))
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        try:
            import markdown
            html = markdown.markdown(response, extensions=["fenced_code", "tables", "nl2br"])
        except ImportError:
            html = response.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        self.browser.setHtml(f"<html><body style='font-family: sans-serif; padding: 10px;'>{html}</body></html>")
        layout.addWidget(self.browser)


class ModelsDialog(QDialog):
    """Диалог управления моделями."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка моделей")
        self.setMinimumSize(500, 400)
        self.setup_ui()
        self.load_models()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Активна", "Название", "API URL", "API ID", "Тип"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Добавить")
        btn_add.clicked.connect(self.add_model)
        btn_edit = QPushButton("Изменить")
        btn_edit.clicked.connect(self.edit_model)
        btn_delete = QPushButton("Удалить")
        btn_delete.clicked.connect(self.delete_model)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_edit)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def load_models(self):
        models = db.get_models()
        self.table.setRowCount(len(models))
        for i, m in enumerate(models):
            cb = QCheckBox()
            cb.setChecked(bool(m["is_active"]))
            cb.stateChanged.connect(lambda s, mid=m["id"]: self.toggle_active(mid, s))
            self.table.setCellWidget(i, 0, cb)
            self.table.setItem(i, 1, QTableWidgetItem(m["name"]))
            self.table.setItem(i, 2, QTableWidgetItem(m["api_url"]))
            self.table.setItem(i, 3, QTableWidgetItem(m["api_id"]))
            self.table.setItem(i, 4, QTableWidgetItem(m.get("model_type", "openai")))
        self._models_data = models

    def toggle_active(self, model_id: int, state):
        for m in self._models_data:
            if m["id"] == model_id:
                db.update_model(
                    m["id"], m["name"], m["api_url"], m["api_id"],
                    1 if state == Qt.Checked else 0,
                    m.get("model_type", "openai")
                )
                break

    def add_model(self):
        d = ModelEditDialog(self)
        if d.exec_() == QDialog.Accepted:
            db.create_model(
                d.name.text(),
                d.api_url.text(),
                d.api_id.text(),
                1 if d.is_active.isChecked() else 0,
                d.model_type.currentText().lower()
            )
            self.load_models()

    def edit_model(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите модель для редактирования")
            return
        m = self._models_data[row]
        d = ModelEditDialog(self, m)
        if d.exec_() == QDialog.Accepted:
            db.update_model(
                m["id"],
                d.name.text(),
                d.api_url.text(),
                d.api_id.text(),
                1 if d.is_active.isChecked() else 0,
                d.model_type.currentText().lower()
            )
            self.load_models()

    def delete_model(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите модель для удаления")
            return
        m = self._models_data[row]
        if QMessageBox.question(
            self, "Подтверждение",
            f"Удалить модель «{m['name']}»?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        ) == QMessageBox.Yes:
            db.delete_model(m["id"])
            self.load_models()


class ModelEditDialog(QDialog):
    """Диалог добавления/редактирования модели."""

    def __init__(self, parent=None, model: dict = None):
        super().__init__(parent)
        self.setWindowTitle("Редактирование модели" if model else "Добавить модель")
        self.setup_ui(model)

    def setup_ui(self, model: dict = None):
        layout = QFormLayout(self)
        self.name = QLineEdit()
        self.name.setPlaceholderText("openai/gpt-4o-mini или GPT-4")
        self.api_url = QLineEdit()
        self.api_url.setPlaceholderText("https://openrouter.ai/api/v1/chat/completions")
        self.api_id = QLineEdit()
        self.api_id.setPlaceholderText("OPENROUTER_API_KEY")
        self.is_active = QCheckBox("Активна")
        self.is_active.setChecked(True)
        self.model_type = QComboBox()
        self.model_type.addItems(["openai", "openrouter", "deepseek", "groq"])

        layout.addRow("Название:", self.name)
        layout.addRow("API URL:", self.api_url)
        layout.addRow("API ID (переменная .env):", self.api_id)
        layout.addRow(self.is_active)
        layout.addRow("Тип API:", self.model_type)

        if model:
            self.name.setText(model["name"])
            self.api_url.setText(model["api_url"])
            self.api_id.setText(model["api_id"])
            self.is_active.setChecked(bool(model["is_active"]))
            idx = self.model_type.findText(model.get("model_type", "openai"), Qt.MatchFixedString)
            if idx >= 0:
                self.model_type.setCurrentIndex(idx)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)


class SettingsDialog(QDialog):
    """Диалог настроек: тема и размер шрифта."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(350)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        layout = QFormLayout(self)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Светлая", "Тёмная"])
        layout.addRow("Тема:", self.theme_combo)
        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 24)
        self.font_spin.setSuffix(" pt")
        layout.addRow("Размер шрифта:", self.font_spin)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.save_and_apply)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def load_settings(self):
        theme = db.get_setting("theme") or "light"
        self.theme_combo.setCurrentIndex(1 if theme == "dark" else 0)
        try:
            fs = int(db.get_setting("font_size") or "10")
            self.font_spin.setValue(fs)
        except ValueError:
            self.font_spin.setValue(10)

    def save_and_apply(self):
        theme = "dark" if self.theme_combo.currentIndex() == 1 else "light"
        font_size = self.font_spin.value()
        db.set_setting("theme", theme)
        db.set_setting("font_size", str(font_size))
        apply_app_theme(QApplication.instance(), theme, font_size)
        self.accept()


class AboutDialog(QDialog):
    """Диалог «О программе»."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setFixedSize(400, 220)
        layout = QVBoxLayout(self)
        title = QLabel("ChatList")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)
        layout.addWidget(QLabel(
            "Программа для отправки одного промта в несколько нейросетей "
            "и сравнения их ответов."
        ))
        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("Стек: Python, PyQt5, SQLite, OpenRouter API"))
        layout.addWidget(QLabel(""))
        layout.addWidget(QLabel("© 2025"))
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)


def apply_app_theme(app, theme: str, font_size: int = 10):
    """Применяет тему и размер шрифта ко всему приложению."""
    font = QFont()
    font.setPointSize(font_size)
    app.setFont(font)
    if theme == "dark":
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)
    else:
        app.setPalette(QPalette())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatList")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        self.setup_menu()
        self.setup_ui()
        self.load_prompts()
        self.restore_geometry()

    def setup_menu(self):
        menubar = self.menuBar()
        service = menubar.addMenu("Сервис")
        act_settings = QAction("Настройки...", self)
        act_settings.triggered.connect(self.open_settings)
        service.addAction(act_settings)
        help_menu = menubar.addMenu("Справка")
        act_about = QAction("О программе", self)
        act_about.triggered.connect(self.open_about)
        help_menu.addAction(act_about)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Верхняя часть: промт
        prompt_layout = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(QLabel("Промт:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Введите запрос или выберите сохранённый промт...")
        self.prompt_edit.setMaximumHeight(120)
        left.addWidget(self.prompt_edit)
        self.btn_improve = QPushButton("Улучшить промт")
        self.btn_improve.clicked.connect(self.on_improve_prompt)
        left.addWidget(self.btn_improve)

        right = QVBoxLayout()
        right.addWidget(QLabel("Сохранённые промты:"))
        self.prompt_search = QLineEdit()
        self.prompt_search.setPlaceholderText("Поиск...")
        self.prompt_search.textChanged.connect(self.load_prompts)
        right.addWidget(self.prompt_search)
        self.prompts_list = QListWidget()
        self.prompts_list.setMaximumWidth(250)
        self.prompts_list.itemClicked.connect(self.on_prompt_selected)
        right.addWidget(self.prompts_list)
        prompts_crud = QHBoxLayout()
        self.btn_prompt_add = QPushButton("Добавить")
        self.btn_prompt_add.clicked.connect(self.on_prompt_add)
        self.btn_prompt_edit = QPushButton("Изменить")
        self.btn_prompt_edit.clicked.connect(self.on_prompt_edit)
        self.btn_prompt_delete = QPushButton("Удалить")
        self.btn_prompt_delete.clicked.connect(self.on_prompt_delete)
        prompts_crud.addWidget(self.btn_prompt_add)
        prompts_crud.addWidget(self.btn_prompt_edit)
        prompts_crud.addWidget(self.btn_prompt_delete)
        right.addLayout(prompts_crud)

        prompt_layout.addLayout(left, 1)
        prompt_layout.addLayout(right)

        btn_row = QHBoxLayout()
        self.btn_send = QPushButton("Отправить")
        self.btn_send.clicked.connect(self.on_send)
        self.btn_save = QPushButton("Сохранить выбранные")
        self.btn_save.clicked.connect(self.on_save)
        self.btn_save.setEnabled(False)
        self.btn_models = QPushButton("Модели...")
        self.btn_models.clicked.connect(self.open_models_dialog)
        self.btn_export = QPushButton("Экспорт...")
        self.btn_export.clicked.connect(self.on_export)
        self.btn_export.setEnabled(False)
        self.btn_open = QPushButton("Открыть")
        self.btn_open.clicked.connect(self.on_open)
        self.btn_open.setEnabled(False)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)  # indeterminate

        btn_row.addWidget(self.btn_send)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_open)
        btn_row.addWidget(self.btn_models)
        btn_row.addWidget(self.btn_export)
        btn_row.addWidget(self.progress, 1)
        layout.addLayout(prompt_layout)
        layout.addLayout(btn_row)

        # Таблица результатов
        layout.addWidget(QLabel("Результаты:"))
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["", "Модель", "Ответ"])
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.results_table.setColumnWidth(0, 40)
        self.results_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.results_table.verticalHeader().setMinimumSectionSize(60)
        self.results_table.cellChanged.connect(self.on_cell_changed)
        layout.addWidget(self.results_table)

    def load_prompts(self):
        self.prompts_list.clear()
        search = self.prompt_search.text().strip() if hasattr(self, "prompt_search") else None
        prompts = db.get_prompts(search=search or None)
        for p in prompts:
            item = QListWidgetItem(p["prompt"][:80] + ("..." if len(p["prompt"]) > 80 else ""))
            item.setData(Qt.UserRole, p)
            self.prompts_list.addItem(item)

    def on_prompt_selected(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if data:
            self.prompt_edit.setText(data["prompt"])
            temp_results.clear()
            self.refresh_results_table()
            self.btn_open.setEnabled(False)

    def on_prompt_add(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Внимание", "Введите текст промта")
            return
        db.create_prompt(prompt)
        self.load_prompts()
        log.info("Промт добавлен")

    def on_prompt_edit(self):
        item = self.prompts_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Внимание", "Выберите промт для редактирования")
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Внимание", "Введите текст промта")
            return
        db.update_prompt(data["id"], prompt, data.get("tags", ""))
        self.load_prompts()
        log.info("Промт обновлён")

    def on_prompt_delete(self):
        item = self.prompts_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Внимание", "Выберите промт для удаления")
            return
        data = item.data(Qt.UserRole)
        if not data:
            return
        if QMessageBox.question(
            self, "Подтверждение",
            "Удалить выбранный промт?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        ) != QMessageBox.Yes:
            return
        db.delete_prompt(data["id"])
        self.prompt_edit.clear()
        self.load_prompts()
        log.info("Промт удалён")

    def on_send(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            log.warning("Промт пуст")
            QMessageBox.warning(self, "Внимание", "Введите промт")
            return

        active = models_module.get_active_models()
        if not active:
            log.warning("Нет активных моделей")
            QMessageBox.warning(
                self, "Внимание",
                "Нет активных моделей. Добавьте модели в настройках."
            )
            return

        # Сохраняем промт и очищаем временную таблицу при новом запросе
        prompt_id = db.create_prompt(prompt)
        log.info("Промт сохранён (id=%d), отправка...", prompt_id)
        temp_results.clear()
        temp_results.set_prompt_id(prompt_id)

        self.btn_send.setEnabled(False)
        self.progress.setVisible(True)
        self.worker = SendWorker(active, prompt)
        self.worker.finished.connect(self.on_send_finished)
        self.worker.start()

    def on_send_finished(self, results: list):
        self.btn_send.setEnabled(True)
        self.progress.setVisible(False)
        temp_results.fill_from_network_results(results)
        self.refresh_results_table()
        self.btn_save.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_open.setEnabled(True)
        self.load_prompts()

    def refresh_results_table(self):
        rows = temp_results.get_all()
        self.results_table.setRowCount(len(rows))
        self.results_table.blockSignals(True)
        for i, r in enumerate(rows):
            cb = QCheckBox()
            cb.setChecked(r["selected"])
            cb.stateChanged.connect(lambda s, idx=i: self.on_checkbox_changed(idx, s))
            self.results_table.setCellWidget(i, 0, cb)
            self.results_table.setItem(i, 1, QTableWidgetItem(r["model_name"]))
            response_item = QTableWidgetItem(r["response"])
            response_item.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
            self.results_table.setItem(i, 2, response_item)
        self.results_table.resizeRowsToContents()
        self.results_table.blockSignals(False)

    def on_checkbox_changed(self, index: int, state):
        temp_results.set_selected(index, state == Qt.Checked)

    def on_cell_changed(self, row, col):
        pass  # для синхронизации при ручном редактировании — при необходимости

    def on_open(self):
        row = self.results_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Внимание", "Выберите строку с ответом")
            return
        rows = temp_results.get_all()
        if row >= len(rows):
            return
        r = rows[row]
        MarkdownViewerDialog(r["model_name"], r["response"], self).exec_()

    def on_save(self):
        count = temp_results.save_selected_to_db()
        log.info("Сохранено результатов: %d", count)
        self.refresh_results_table()
        self.btn_save.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_open.setEnabled(False)
        QMessageBox.information(self, "Сохранено", f"Сохранено записей: {count}")

    def on_export(self):
        rows = temp_results.get_all()
        selected = [r for r in rows if r["selected"]]
        if not selected:
            QMessageBox.warning(self, "Внимание", "Выберите строки для экспорта (чекбоксы)")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт",
            "",
            "Markdown (*.md);;JSON (*.json);;Все файлы (*)"
        )
        if not path:
            return

        if path.endswith(".json"):
            import json
            data = [{"model": r["model_name"], "response": r["response"]} for r in selected]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            lines = []
            for r in selected:
                lines.append(f"## {r['model_name']}\n\n{r['response']}\n\n")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        log.info("Экспорт в %s", path)
        QMessageBox.information(self, "Экспорт", f"Сохранено в {path}")

    def open_models_dialog(self):
        ModelsDialog(self).exec_()

    def open_settings(self):
        SettingsDialog(self).exec_()

    def open_about(self):
        AboutDialog(self).exec_()

    def on_improve_prompt(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Внимание", "Введите текст для улучшения")
            return
        models = models_module.get_active_models()
        if not models:
            QMessageBox.warning(
                self, "Внимание",
                "Нет активных моделей. Добавьте модели в настройках."
            )
            return
        PromptImproverDialog(prompt, self.prompt_edit, self).exec_()

    def restore_geometry(self):
        geom = db.get_setting("window_geometry")
        if geom:
            self.restoreGeometry(bytes.fromhex(geom))

    def save_geometry(self):
        db.set_setting("window_geometry", self.saveGeometry().toHex().data().decode())

    def closeEvent(self, event):
        log.info("Закрытие приложения")
        self.save_geometry()
        event.accept()


def main():
    log.info("Запуск ChatList...")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    theme = db.get_setting("theme") or "light"
    try:
        font_size = int(db.get_setting("font_size") or "10")
    except ValueError:
        font_size = 10
    apply_app_theme(app, theme, font_size)
    window = MainWindow()
    window.show()
    log.info("Окно открыто")
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
