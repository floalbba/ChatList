"""ChatList — отправка промта в несколько нейросетей и сравнение ответов."""

import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
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
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

import db
import models as models_module
import network
import temp_results


class SendWorker(QThread):
    """Поток для отправки запросов без блокировки UI."""
    finished = pyqtSignal(list)  # list of {model, response, error}

    def __init__(self, models: list, prompt: str):
        super().__init__()
        self.models = models
        self.prompt = prompt

    def run(self):
        results = network.send_prompt_to_models(self.models, self.prompt)
        self.finished.emit(results)


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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChatList")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        self.setup_ui()
        self.load_prompts()
        self.restore_geometry()

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

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setRange(0, 0)  # indeterminate

        btn_row.addWidget(self.btn_send)
        btn_row.addWidget(self.btn_save)
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

    def on_send(self):
        prompt = self.prompt_edit.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Внимание", "Введите промт")
            return

        active = models_module.get_active_models()
        if not active:
            QMessageBox.warning(
                self, "Внимание",
                "Нет активных моделей. Добавьте модели в настройках."
            )
            return

        # Сохраняем промт и очищаем временную таблицу при новом запросе
        prompt_id = db.create_prompt(prompt)
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
            self.results_table.setItem(i, 2, QTableWidgetItem(r["response"]))
        self.results_table.blockSignals(False)

    def on_checkbox_changed(self, index: int, state):
        temp_results.set_selected(index, state == Qt.Checked)

    def on_cell_changed(self, row, col):
        pass  # для синхронизации при ручном редактировании — при необходимости

    def on_save(self):
        count = temp_results.save_selected_to_db()
        self.refresh_results_table()
        self.btn_save.setEnabled(False)
        self.btn_export.setEnabled(False)
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

        QMessageBox.information(self, "Экспорт", f"Сохранено в {path}")

    def open_models_dialog(self):
        ModelsDialog(self).exec_()

    def restore_geometry(self):
        geom = db.get_setting("window_geometry")
        if geom:
            self.restoreGeometry(bytes.fromhex(geom))

    def save_geometry(self):
        db.set_setting("window_geometry", self.saveGeometry().toHex().data().decode())

    def closeEvent(self, event):
        self.save_geometry()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
