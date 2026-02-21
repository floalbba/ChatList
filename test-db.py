"""Тестовая программа для просмотра и редактирования SQLite баз данных."""

import sqlite3
import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QMessageBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QFileDialog,
    QDialogButtonBox,
    QHeaderView,
    QAbstractItemView,
    QSpinBox,
    QComboBox,
)
from PyQt5.QtCore import Qt


PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 500]


def get_tables(conn: sqlite3.Connection) -> list[str]:
    """Возвращает список таблиц в БД."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    return [row[0] for row in cur.fetchall()]


def get_table_info(conn: sqlite3.Connection, table: str) -> list[tuple]:
    """Возвращает информацию о колонках таблицы."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    return cur.fetchall()


def get_table_data(
    conn: sqlite3.Connection,
    table: str,
    limit: int,
    offset: int
) -> tuple[list, int]:
    """Возвращает (данные, общее количество строк)."""
    cur = conn.execute(f"SELECT COUNT(*) FROM [{table}]")
    total = cur.fetchone()[0]
    cur = conn.execute(f"SELECT * FROM [{table}] LIMIT ? OFFSET ?", (limit, offset))
    rows = cur.fetchall()
    return rows, total


def get_column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    """Возвращает имена колонок."""
    info = get_table_info(conn, table)
    return [col[1] for col in info]


def get_primary_key(conn: sqlite3.Connection, table: str) -> list[str]:
    """Возвращает имена колонок первичного ключа."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = cur.fetchall()
    pk = [c[1] for c in cols if c[5] > 0]
    if not pk:
        pk = [cols[0][1]] if cols else []
    return pk


class TableViewDialog(QDialog):
    """Диалог просмотра таблицы с пагинацией и CRUD."""

    def __init__(self, db_path: Path, table: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.table = table
        self.current_page = 0
        self.page_size = 25
        self.total_rows = 0
        self.conn = None
        self.setWindowTitle(f"Таблица: {table}")
        self.setMinimumSize(700, 500)
        self.resize(900, 600)
        self.setup_ui()
        self.load_page()

    def get_connection(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Пагинация
        pagination = QHBoxLayout()
        self.btn_prev = QPushButton("← Назад")
        self.btn_prev.clicked.connect(self.prev_page)
        self.btn_next = QPushButton("Вперёд →")
        self.btn_next.clicked.connect(self.next_page)
        self.label_page = QLabel()
        self.spin_page_size = QSpinBox()
        self.spin_page_size.setRange(10, 500)
        self.spin_page_size.setValue(25)
        self.spin_page_size.setSuffix(" строк")
        self.spin_page_size.valueChanged.connect(self.on_page_size_changed)
        pagination.addWidget(self.btn_prev)
        pagination.addWidget(self.btn_next)
        pagination.addWidget(self.label_page)
        pagination.addStretch()
        pagination.addWidget(QLabel("Строк на странице:"))
        pagination.addWidget(self.spin_page_size)
        layout.addLayout(pagination)

        # Таблица
        self.table_widget = QTableWidget()
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        layout.addWidget(self.table_widget)

        # CRUD кнопки
        crud_layout = QHBoxLayout()
        self.btn_add = QPushButton("Добавить")
        self.btn_add.clicked.connect(self.on_add)
        self.btn_edit = QPushButton("Изменить")
        self.btn_edit.clicked.connect(self.on_edit)
        self.btn_delete = QPushButton("Удалить")
        self.btn_delete.clicked.connect(self.on_delete)
        crud_layout.addWidget(self.btn_add)
        crud_layout.addWidget(self.btn_edit)
        crud_layout.addWidget(self.btn_delete)
        crud_layout.addStretch()
        layout.addLayout(crud_layout)

    def load_page(self):
        conn = self.get_connection()
        cols = get_column_names(conn, self.table)
        rows, total = get_table_data(
            conn, self.table,
            self.page_size,
            self.current_page * self.page_size
        )
        self.total_rows = total

        self.table_widget.setColumnCount(len(cols))
        self.table_widget.setHorizontalHeaderLabels(cols)
        self.table_widget.setRowCount(len(rows))

        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table_widget.setItem(i, j, item)

        self.table_widget.resizeColumnsToContents()

        # Обновление пагинации
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(self.current_page < total_pages - 1)
        self.label_page.setText(
            f"Страница {self.current_page + 1} из {total_pages} "
            f"(всего {total} строк)"
        )

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.load_page()

    def next_page(self):
        total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self.load_page()

    def on_page_size_changed(self, value: int):
        self.page_size = value
        self.current_page = 0
        self.load_page()

    def on_add(self):
        conn = self.get_connection()
        cols = get_column_names(conn, self.table)
        info = get_table_info(conn, self.table)
        pk_cols = get_primary_key(conn, self.table)
        d = RowEditDialog(cols, info, None, self)
        if d.exec_() == QDialog.Accepted:
            values_dict = dict(zip(cols, d.get_values()))
            # Исключаем PK с пустым значением (autoincrement)
            insert_cols = [c for c in cols if c not in pk_cols or values_dict.get(c)]
            insert_vals = []
            for c in insert_cols:
                v = values_dict.get(c, "")
                insert_vals.append(None if v == "" else v)
            if not insert_cols:
                QMessageBox.warning(self, "Внимание", "Нет данных для вставки")
                return
            placeholders = ", ".join("?" * len(insert_vals))
            col_names = ", ".join(f"[{c}]" for c in insert_cols)
            try:
                conn.execute(
                    f"INSERT INTO [{self.table}] ({col_names}) VALUES ({placeholders})",
                    insert_vals
                )
                conn.commit()
                self.load_page()
                QMessageBox.information(self, "OK", "Запись добавлена")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Ошибка", str(e))

    def on_edit(self):
        row_idx = self.table_widget.currentRow()
        if row_idx < 0:
            QMessageBox.warning(self, "Внимание", "Выберите строку для редактирования")
            return
        conn = self.get_connection()
        cols = get_column_names(conn, self.table)
        info = get_table_info(conn, self.table)
        pk_cols = get_primary_key(conn, self.table)
        row_data = {}
        for j, col in enumerate(cols):
            item = self.table_widget.item(row_idx, j)
            row_data[col] = item.text() if item else ""
        d = RowEditDialog(cols, info, row_data, self)
        if d.exec_() == QDialog.Accepted:
            values = d.get_values()
            set_clause = ", ".join(f"[{c}] = ?" for c in cols)
            where_clause = " AND ".join(f"[{c}] = ?" for c in pk_cols)
            pk_values = [row_data[c] for c in pk_cols]
            try:
                conn.execute(
                    f"UPDATE [{self.table}] SET {set_clause} WHERE {where_clause}",
                    values + pk_values
                )
                conn.commit()
                self.load_page()
                QMessageBox.information(self, "OK", "Запись обновлена")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Ошибка", str(e))

    def on_delete(self):
        row_idx = self.table_widget.currentRow()
        if row_idx < 0:
            QMessageBox.warning(self, "Внимание", "Выберите строку для удаления")
            return
        if QMessageBox.question(
            self, "Подтверждение",
            "Удалить выбранную запись?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        ) != QMessageBox.Yes:
            return
        conn = self.get_connection()
        cols = get_column_names(conn, self.table)
        pk_cols = get_primary_key(conn, self.table)
        row_data = {}
        for j, col in enumerate(cols):
            item = self.table_widget.item(row_idx, j)
            row_data[col] = item.text() if item else ""
        where_clause = " AND ".join(f"[{c}] = ?" for c in pk_cols)
        pk_values = [row_data[c] for c in pk_cols]
        try:
            conn.execute(
                f"DELETE FROM [{self.table}] WHERE {where_clause}",
                pk_values
            )
            conn.commit()
            self.load_page()
            QMessageBox.information(self, "OK", "Запись удалена")
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def closeEvent(self, event):
        if self.conn:
            self.conn.close()
        event.accept()


class RowEditDialog(QDialog):
    """Диалог добавления/редактирования строки."""

    def __init__(self, columns: list, info: list, row_data: dict, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.info = info
        self.row_data = row_data or {}
        self.editors = {}
        self.setWindowTitle("Редактирование" if row_data else "Добавить запись")
        self.setup_ui()

    def setup_ui(self):
        layout = QFormLayout(self)
        for col_info in self.info:
            name = col_info[1]
            dtype = col_info[2]
            notnull = col_info[3]
            pk = col_info[5]
            value = self.row_data.get(name, "")
            edit = QLineEdit()
            edit.setText(str(value))
            if pk:
                edit.setReadOnly(True)
                edit.setPlaceholderText("(авто)")
            self.editors[name] = edit
            label = name + (" *" if notnull and not pk else "")
            layout.addRow(label, edit)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_values(self) -> list:
        return [self.editors[c].text() for c in self.columns]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Просмотр SQLite")
        self.setMinimumSize(400, 500)
        self.db_path = None
        self.conn = None
        self.setup_ui()

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        layout.addWidget(QLabel("Файл базы данных:"))
        file_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Путь к .db файлу...")
        self.btn_browse = QPushButton("Обзор...")
        self.btn_browse.clicked.connect(self.browse_file)
        file_layout.addWidget(self.path_edit)
        file_layout.addWidget(self.btn_browse)
        layout.addLayout(file_layout)

        layout.addWidget(QLabel("Таблицы:"))
        self.tables_list = QListWidget()
        layout.addWidget(self.tables_list)

        self.btn_open = QPushButton("Открыть")
        self.btn_open.clicked.connect(self.open_table)
        self.btn_open.setEnabled(False)
        layout.addWidget(self.btn_open)

    def browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите SQLite файл",
            "", "SQLite (*.db *.sqlite *.sqlite3);;Все файлы (*)"
        )
        if path:
            self.path_edit.setText(path)
            self.load_tables(path)

    def load_tables(self, path: str):
        self.tables_list.clear()
        self.db_path = None
        self.btn_open.setEnabled(False)
        try:
            conn = sqlite3.connect(path)
            tables = get_tables(conn)
            conn.close()
            for t in tables:
                self.tables_list.addItem(QListWidgetItem(t))
            self.db_path = Path(path)
            self.btn_open.setEnabled(len(tables) > 0)
        except sqlite3.Error as e:
            QMessageBox.critical(self, "Ошибка", str(e))

    def open_table(self):
        item = self.tables_list.currentItem()
        if not item or not self.db_path:
            QMessageBox.warning(self, "Внимание", "Выберите таблицу")
            return
        table = item.text()
        TableViewDialog(self.db_path, table, self).exec_()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    # Автозагрузка chatlist.db если есть
    default_db = Path(__file__).parent / "chatlist.db"
    if default_db.exists():
        window.path_edit.setText(str(default_db))
        window.load_tables(str(default_db))
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
