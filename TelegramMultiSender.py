import json
import os
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QFileDialog, QTabWidget, QLabel, QPushButton,
    QTextEdit, QLineEdit, QVBoxLayout, QHBoxLayout,
    QListWidget, QComboBox, QSpinBox, QMenuBar, QMenu,
    QInputDialog, QDialog
)
from telethon import TelegramClient, errors
import asyncio
import qasync  # Для интеграции asyncio с Qt
import qrcode
from io import BytesIO

SESSIONS_FOLDER = "sessions"
API_PROFILES_FILE = "api_profiles.json"


def ensure_sessions_folder():
    if not os.path.exists(SESSIONS_FOLDER):
        os.makedirs(SESSIONS_FOLDER)


def load_api_profiles():
    if not os.path.exists(API_PROFILES_FILE):
        return []
    try:
        with open(API_PROFILES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("profiles", [])
    except Exception as e:
        print(f"Ошибка при загрузке {API_PROFILES_FILE}: {e}")
        return []


def save_api_profiles(profiles):
    data = {"profiles": profiles}
    try:
        with open(API_PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка при сохранении {API_PROFILES_FILE}: {e}")


def get_session_files():
    ensure_sessions_folder()
    try:
        return [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith(".session")]
    except Exception as e:
        print(f"Ошибка при загрузке сессий: {e}")
        return []


class DebugWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Debug Window")
        self.setGeometry(150, 150, 600, 400)

        # Применяем тёмную тему (копируем из set_dark_theme)
        self.setStyleSheet("""
            QWidget { background-color: #121212; color: white; }
            QPushButton { background-color: #333; color: white; border-radius: 5px; padding: 5px; }
            QPushButton:hover { background-color: #444; }
            QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox {
                background-color: #222; color: white; border: 1px solid #444;
            }
        """)

        self.text_edit = QTextEdit(self)
        self.text_edit.setReadOnly(True)

        central_widget = QtWidgets.QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.text_edit)
        self.setCentralWidget(central_widget)


    def append_debug(self, message: str):
        self.text_edit.append(message)


class TelegramSender(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.qr_login_in_progress = False
        self.client = None
        self.running = False
        self.users_file = None
        self.attachment_path = None

        # Храним профили API в памяти
        self.api_profiles = load_api_profiles()

        # Создадим окно для Debug (вместо вкладки)
        self.debug_window = DebugWindow()

        self.initUI()
        self.update_api_profiles_list()
        self.update_session_list()

    def initUI(self):
        self.setWindowTitle("Telegram Sender (Multiple APIs)")
        self.setWindowIcon(QIcon("icon.png"))
        self.setGeometry(100, 100, 700, 500)

        # Меню-бар (сверху) вместо отдельной вкладки «Дебаг»
        menubar = QMenuBar(self)
        tools_menu = QMenu("Debug", self)
        open_debug_action = QAction("Open Debug Window", self)
        open_debug_action.triggered.connect(self.show_debug_window)
        tools_menu.addAction(open_debug_action)
        menubar.addMenu(tools_menu)

        # Основной лейаут
        main_layout = QVBoxLayout()
        main_layout.setMenuBar(menubar)

        # Водяной знак / шапка
        top_layout = QHBoxLayout()
        self.creator_label = QLabel("made by !ниц")
        self.creator_label.setStyleSheet("color: #8B0000; font-size: 12pt;")
        top_layout.addStretch()
        top_layout.addWidget(self.creator_label)

        main_layout.addLayout(top_layout)

        # Создаём вкладки (убираем вкладку «Дебаг», т.к. у нас теперь отдельное окно)
        self.tabs = QTabWidget(self)
        self.tab_main = QtWidgets.QWidget()
        self.tab_sessions = QtWidgets.QWidget()
        self.tab_api = QtWidgets.QWidget()

        self.tabs.addTab(self.tab_main, "Основное")
        self.tabs.addTab(self.tab_sessions, "Сессии")
        self.tabs.addTab(self.tab_api, "API")

        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

        self.init_main_tab()
        self.init_sessions_tab()
        self.init_api_tab()

        self.set_dark_theme()

    def show_debug_window(self):
        # Показать/активировать окно отладки
        self.debug_window.show()
        self.debug_window.raise_()
        self.debug_window.activateWindow()

    def set_dark_theme(self):
        self.setStyleSheet("""
            QWidget { background-color: #121212; color: white; }
            QPushButton { background-color: #333; color: white; border-radius: 5px; padding: 5px; }
            QPushButton:hover { background-color: #444; }
            QLineEdit, QTextEdit, QComboBox, QListWidget, QSpinBox {
                background-color: #222; color: white; border: 1px solid #444;
            }
        """)
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                background: #333;
                color: white;
                border: 1px solid #444;
                padding: 5px;
                margin: 2px;
            }
            QTabBar::tab:hover {
                background: #444;
            }
            QTabBar::tab:selected {
                background: #444;
                border-bottom: 2px solid #FF5722;
            }
        """)

    ############################################
    # Вкладка «Основное»
    ############################################
    def init_main_tab(self):
        layout = QVBoxLayout(self.tab_main)

        # Выбор профиля API
        layout.addWidget(QLabel("Выберите профиль API:"))
        self.api_profile_combo = QComboBox(self)
        layout.addWidget(self.api_profile_combo)

        # Выбор сессии
        layout.addWidget(QLabel("Выберите сессию для отправки сообщений:"))
        self.session_combo_box = QComboBox(self)
        layout.addWidget(self.session_combo_box)

        # Поле ввода текста сообщения
        self.message_input = QTextEdit(self)
        self.message_input.setPlaceholderText("Введите текст сообщения")
        layout.addWidget(self.message_input)

        # Блок настроек (задержка и т.д.)
        settings_layout = QHBoxLayout()
        delay_label = QLabel("Задержка (сек) между сообщениями [Рекомендовано: 60-120сек]:")
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(0, 300)  # от 0 до 5 минут
        self.delay_spinbox.setValue(2)       # по умолчанию 2 секунды
        settings_layout.addWidget(delay_label)
        settings_layout.addWidget(self.delay_spinbox)
        layout.addLayout(settings_layout)

        # Кнопки загрузки файла пользователей и вложений
        self.file_button = QPushButton("Выбрать файл с юзерами")
        self.file_button.clicked.connect(self.load_users_file)
        layout.addWidget(self.file_button)

        self.attach_button = QPushButton("Добавить вложение")
        self.attach_button.clicked.connect(self.load_attachment)
        layout.addWidget(self.attach_button)

        # Кнопки запуска/остановки
        self.start_button = QPushButton("Запустить бота")
        self.start_button.clicked.connect(self.start_bot)
        layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Остановить бота")
        self.stop_button.clicked.connect(self.stop_bot)
        layout.addWidget(self.stop_button)

        # Лог работы бота (короткий)
        layout.addWidget(QLabel("Бот лог:"))
        self.bot_log_output = QTextEdit(self)
        self.bot_log_output.setReadOnly(True)
        layout.addWidget(self.bot_log_output)

    ############################################
    # Вкладка «Сессии»
    ############################################
    def init_sessions_tab(self):
        layout = QVBoxLayout(self.tab_sessions)

        layout.addWidget(QLabel("Список сессий:"))
        self.session_list_widget = QListWidget(self)
        layout.addWidget(self.session_list_widget)

        self.session_name_input = QLineEdit(self)
        self.session_name_input.setPlaceholderText("Имя новой сессии")
        layout.addWidget(self.session_name_input)

        btn_create = QPushButton("Создать сессию (QR)")
        btn_create.clicked.connect(self.create_session)
        layout.addWidget(btn_create)

        btn_delete = QPushButton("Удалить выбранную сессию")
        btn_delete.clicked.connect(self.delete_session)
        layout.addWidget(btn_delete)

        self.qr_label = QLabel(self)
        layout.addWidget(self.qr_label)

    ############################################
    # Вкладка «API»
    ############################################
    def init_api_tab(self):
        layout = QVBoxLayout(self.tab_api)

        layout.addWidget(QLabel("Список профилей API:"))
        self.api_list_widget = QListWidget(self)
        layout.addWidget(self.api_list_widget)

        self.api_profile_name_input = QLineEdit(self)
        self.api_profile_name_input.setPlaceholderText("Имя профиля (например, 'MainAccount')")
        layout.addWidget(self.api_profile_name_input)

        self.api_id_input = QLineEdit(self)
        self.api_id_input.setPlaceholderText("API ID")
        layout.addWidget(self.api_id_input)

        self.api_hash_input = QLineEdit(self)
        self.api_hash_input.setPlaceholderText("API HASH")
        layout.addWidget(self.api_hash_input)

        btn_create_api = QPushButton("Создать профиль API")
        btn_create_api.clicked.connect(self.create_api_profile)
        layout.addWidget(btn_create_api)

        btn_delete_api = QPushButton("Удалить выбранный профиль API")
        btn_delete_api.clicked.connect(self.delete_api_profile)
        layout.addWidget(btn_delete_api)

    ############################################
    # Методы для работы с файлами
    ############################################
    def load_users_file(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Выберите файл с юзерами", "",
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.users_file = file_path
            self.log_bot(f"📂 Файл с юзерами загружен: {file_path}")

    def load_attachment(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Выберите вложение", "",
            "All Files (*)"
        )
        if file_path:
            self.attachment_path = file_path
            self.log_bot(f"📎 Вложение загружено: {file_path}")

    ############################################
    # Логика логов
    ############################################
    def log_bot(self, message: str):
        self.bot_log_output.append(message)
        self.log_debug(message)  # Дублируем в debug

    def log_debug(self, message: str):
        print(message)
        self.debug_window.append_debug(message)

    ############################################
    # Работа с API-профилями
    ############################################
    def create_api_profile(self):
        name = self.api_profile_name_input.text().strip()
        api_id = self.api_id_input.text().strip()
        api_hash = self.api_hash_input.text().strip()

        if not name:
            self.log_bot("⚠️ Укажите имя профиля API!")
            return
        if not api_id:
            self.log_bot("⚠️ Укажите API ID!")
            return
        if not api_hash:
            self.log_bot("⚠️ Укажите API HASH!")
            return

        # Проверяем, нет ли профиля с таким именем
        for p in self.api_profiles:
            if p["name"] == name:
                self.log_bot(f"⚠️ Профиль API с именем '{name}' уже существует!")
                return

        new_profile = {
            "name": name,
            "api_id": api_id,
            "api_hash": api_hash
        }
        self.api_profiles.append(new_profile)
        save_api_profiles(self.api_profiles)
        self.log_bot(f"✅ Профиль API '{name}' создан!")
        self.update_api_profiles_list()

    def delete_api_profile(self):
        selected_items = self.api_list_widget.selectedItems()
        if not selected_items:
            self.log_bot("⚠️ Выберите профиль API для удаления!")
            return

        for item in selected_items:
            name_to_delete = item.text()
            for p in self.api_profiles:
                if p["name"] == name_to_delete:
                    self.api_profiles.remove(p)
                    self.log_bot(f"✅ Профиль API '{name_to_delete}' удалён!")
                    break

        save_api_profiles(self.api_profiles)
        self.update_api_profiles_list()

    def update_api_profiles_list(self):
        self.api_list_widget.clear()
        self.api_profile_combo.clear()

        for profile in self.api_profiles:
            self.api_list_widget.addItem(profile["name"])
            self.api_profile_combo.addItem(profile["name"])

    ############################################
    # Работа с сессиями
    ############################################
    def create_session(self):
        session_name = self.session_name_input.text().strip()
        if not session_name:
            self.log_bot("⚠️ Введите имя новой сессии!")
            return
        asyncio.create_task(self.login_with_qr_async(session_name))

    def delete_session(self):
        selected_items = self.session_list_widget.selectedItems()
        if not selected_items:
            self.log_bot("⚠️ Выберите сессию для удаления!")
            return
        for item in selected_items:
            session_file = item.text()
            file_path = os.path.join(SESSIONS_FOLDER, session_file)
            try:
                os.remove(file_path)
                self.log_bot(f"✅ Сессия удалена: {session_file}")
            except Exception as e:
                self.log_bot("❌ Ошибка при удалении сессии. Подробности в Дебаг.")
                self.log_debug(f"❌ Ошибка при удалении {session_file}: {e}")
        self.update_session_list()

    def update_session_list(self):
        sessions = get_session_files()
        if hasattr(self, 'session_list_widget'):
            self.session_list_widget.clear()
            self.session_list_widget.addItems(sessions)
        if hasattr(self, 'session_combo_box'):
            self.session_combo_box.clear()
            self.session_combo_box.addItems(sessions)

    ############################################
    # QR-вход для создания/авторизации сессии + 2FA
    ############################################
    async def login_with_qr_async(self, session_name):
        try:
            self.log_debug("DEBUG: Начало метода login_with_qr_async")

            selected_profile_name = self.api_profile_combo.currentText()
            if not selected_profile_name:
                self.log_bot("❌ Сначала создайте и выберите профиль API во вкладке 'API'.")
                return

            profile_data = None
            for p in self.api_profiles:
                if p["name"] == selected_profile_name:
                    profile_data = p
                    break
            if not profile_data:
                self.log_bot(f"❌ Профиль API '{selected_profile_name}' не найден!")
                return

            api_id_str = profile_data["api_id"]
            api_hash_str = profile_data["api_hash"]
            self.log_debug(f"DEBUG: Используем профиль API '{selected_profile_name}' -> ID={api_id_str}, HASH={api_hash_str}")

            try:
                api_id = int(api_id_str)
            except ValueError:
                self.log_bot("❌ API ID должен быть числом!")
                return

            api_hash = api_hash_str.strip()
            if not api_hash:
                self.log_bot("❌ API HASH пуст!")
                return

            session_path = os.path.join(SESSIONS_FOLDER, session_name)

            # Отключаем предыдущий клиент, если есть
            if self.client is not None:
                await self.client.disconnect()

            self.client = TelegramClient(session_path, api_id, api_hash)
            self.log_debug("DEBUG: Клиент Telegram создан для сессии " + session_name)

            await self.client.connect()
            self.log_debug("DEBUG: Попытка подключения к Telegram")

            if await self.client.is_user_authorized():
                self.log_bot("✅ Сессия уже авторизована!")
                self.update_session_list()
                return

            self.log_bot("🔄 Запуск входа через QR‑код...")
            qr_login = await self.client.qr_login()
            self.log_debug("DEBUG: qr_login получен")
            qr_url = qr_login.url
            self.log_debug("DEBUG: qr_url: " + qr_url)

            qr_img = qrcode.make(qr_url)
            buf = BytesIO()
            qr_img.save(buf, format='PNG')
            qt_img = QtGui.QImage()
            qt_img.loadFromData(buf.getvalue())
            pixmap = QtGui.QPixmap.fromImage(qt_img)
            self.qr_label.setPixmap(pixmap)
            self.log_debug("DEBUG: QR‑код отображен в QLabel")

            self.log_bot("📲 Отсканируйте QR‑код в приложении Telegram для входа.")
            await qr_login.wait()
            self.log_bot("✅ Успешный вход через QR‑код!")
            self.qr_label.clear()
            self.update_session_list()

            # Проверяем, не нужна ли 2FA (пароль)
            if not await self.client.is_user_authorized():
                # Возможно, требуется ввести пароль
                try:
                    await self.client.sign_in()  # Может выдать SessionPasswordNeededError
                except errors.SessionPasswordNeededError:
                    # Запросим у пользователя пароль 2FA
                    password, ok = QInputDialog.getText(
                        self, "2FA Password",
                        "Введите пароль 2FA (двухфакторная аутентификация):",
                        QLineEdit.EchoMode.Password
                    )
                    if ok and password:
                        await self.client.sign_in(password=password)
                        self.log_bot("✅ 2FA пароль принят, авторизация завершена!")
                    else:
                        self.log_bot("❌ Авторизация отменена (не введён пароль).")

            self.update_session_list()

        except Exception as e:
            self.log_bot("❌ Ошибка при входе через QR‑код. Смотрите Дебаг.")
            self.log_debug(f"❌ Ошибка login_with_qr_async: {e}")
        finally:
            self.qr_login_in_progress = False

    ############################################
    # Работа бота (отправка сообщений)
    ############################################
    async def send_messages(self):
        self.running = True
        try:
            selected_profile_name = self.api_profile_combo.currentText()
            if not selected_profile_name:
                self.log_bot("❌ Не выбран профиль API!")
                return

            profile_data = None
            for p in self.api_profiles:
                if p["name"] == selected_profile_name:
                    profile_data = p
                    break
            if not profile_data:
                self.log_bot(f"❌ Профиль API '{selected_profile_name}' не найден!")
                return

            try:
                api_id = int(profile_data["api_id"])
            except ValueError:
                self.log_bot("❌ API ID должен быть числом!")
                return

            api_hash = profile_data["api_hash"].strip()
            if not api_hash:
                self.log_bot("❌ API HASH пуст!")
                return

            session_name = self.session_combo_box.currentText()
            if not session_name:
                self.log_bot("❌ Не выбрана сессия!")
                return

            session_path = os.path.join(SESSIONS_FOLDER, session_name)

            if self.client is None or not self.client.is_connected():
                self.client = TelegramClient(session_path, api_id, api_hash)
                await self.client.connect()
                self.log_debug("DEBUG: Подключение к Telegram в send_messages")

            if not await self.client.is_user_authorized():
                self.log_bot("❌ Сессия не авторизована! Сначала авторизуйтесь через QR‑код во вкладке 'Сессии'.")
                return

            self.log_bot("✅ Подключение к Telegram успешно!")

            with open(self.users_file, "r", encoding="utf-8") as f:
                users = [line.strip() for line in f if line.strip()]

            processed_file = "processed.txt"
            processed_users = set()
            if os.path.exists(processed_file):
                with open(processed_file, "r", encoding="utf-8") as pf:
                    processed_users = set(pf.read().splitlines())

            for username in users:
                if not self.running:
                    self.log_bot("🛑 Бот остановлен!")
                    break
                if username in processed_users:
                    self.log_bot(f"⚠️ Уже отправлено: {username}")
                    continue
                try:
                    if self.attachment_path:
                        await self.client.send_file(
                            username, self.attachment_path,
                            caption=self.message_input.toPlainText()
                        )
                    else:
                        await self.client.send_message(
                            username, self.message_input.toPlainText()
                        )
                    self.log_bot(f"✅ Сообщение отправлено: {username}")
                    with open(processed_file, "a", encoding="utf-8") as pf:
                        pf.write(username + "\n")
                    # Используем значение из спинбокса (задержка)
                    await asyncio.sleep(self.delay_spinbox.value())
                except Exception as e:
                    self.log_bot(f"❌ Ошибка при отправке сообщения пользователю '{username}': {e}")
                    self.log_debug(f"❌ Ошибка при отправке {username}: {e}")
                    # Можно продолжить или остановиться - решайте сами
                    # break

        except Exception as e:
            self.log_bot("❌ Ошибка подключения к Telegram. Смотрите Дебаг.")
            self.log_debug(f"❌ Ошибка в send_messages: {e}")
        self.running = False
        self.log_bot("✅ Бот завершил работу!")

    def start_bot(self):
        if not self.users_file:
            self.log_bot("⚠️ Сначала выберите файл с юзерами!")
            return
        self.log_bot("🚀 Бот запущен...")
        asyncio.create_task(self.send_messages())

    def stop_bot(self):
        self.running = False
        self.log_bot("🛑 Бот остановлен!")

    ############################################
    # Загрузка и закрытие приложения
    ############################################
    def closeEvent(self, event):
        # Закроем также окно отладки, если нужно
        self.debug_window.close()
        event.accept()


if __name__ == "__main__":
    ensure_sessions_folder()

    app = QtWidgets.QApplication([])
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    window = TelegramSender()
    window.show()
    with loop:
        loop.run_forever()
