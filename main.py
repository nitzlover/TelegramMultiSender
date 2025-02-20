import json
import os
from PyQt6 import QtWidgets, QtGui
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFileDialog, QTabWidget, QLabel, QPushButton,
    QTextEdit, QLineEdit, QVBoxLayout, QHBoxLayout, QListWidget, QComboBox
)
from telethon import TelegramClient
import asyncio
import qasync  # Для интеграции asyncio с Qt
import qrcode
from io import BytesIO

SESSIONS_FOLDER = "sessions"
API_PROFILES_FILE = "api_profiles.json"


def ensure_sessions_folder():
    """Гарантируем, что папка для сессий существует."""
    if not os.path.exists(SESSIONS_FOLDER):
        os.makedirs(SESSIONS_FOLDER)


def load_api_profiles():
    """
    Загружаем список профилей API из JSON-файла.
    Формат файла:
    {
      "profiles": [
        {
          "name": "Profile1",
          "api_id": "12345",
          "api_hash": "abcdefg"
        },
        ...
      ]
    }
    """
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
    """
    Сохраняем список профилей API в JSON-файл.
    profiles – это список словарей вида:
    [
      {"name": ..., "api_id": ..., "api_hash": ...},
      ...
    ]
    """
    data = {"profiles": profiles}
    try:
        with open(API_PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка при сохранении {API_PROFILES_FILE}: {e}")


def get_session_files():
    """Возвращаем список *.session в папке sessions."""
    ensure_sessions_folder()
    try:
        return [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith(".session")]
    except Exception as e:
        print(f"Ошибка при загрузке сессий: {e}")
        return []


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

        self.initUI()
        self.update_api_profiles_list()  # Обновляем список API-профилей
        self.update_session_list()       # Обновляем список сессий

    def initUI(self):
        self.setWindowTitle("Telegram Sender (Multiple APIs)")
        # Устанавливаем иконку (замените путь "icon.png" на ваш реальный путь к файлу иконки)
        self.setWindowIcon(QIcon("icon.png"))
        self.setGeometry(100, 100, 600, 500)

        # Создаём вкладки
        self.tabs = QTabWidget(self)

        # Создаём общий вертикальный лейаут
        main_layout = QVBoxLayout()

        # ---- Водяной знак / «шапка» ----
        top_layout = QHBoxLayout()

        # Надпись кроваво-красного цвета
        self.creator_label = QLabel("made by !ниц")
        self.creator_label.setStyleSheet("color: #8B0000; font-size: 12pt;")

        # Если хотим, чтобы надпись была справа
        top_layout.addStretch()
        top_layout.addWidget(self.creator_label)

        # Добавляем шапку и вкладки в основной лейаут
        main_layout.addLayout(top_layout)
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

        # Создаём вкладки: Основное, Сессии, API, Дебаг
        self.tab_main = QtWidgets.QWidget()
        self.tab_sessions = QtWidgets.QWidget()
        self.tab_api = QtWidgets.QWidget()
        self.tab_debug = QtWidgets.QWidget()

        self.tabs.addTab(self.tab_main, "Основное")
        self.tabs.addTab(self.tab_sessions, "Сессии")
        self.tabs.addTab(self.tab_api, "API")
        self.tabs.addTab(self.tab_debug, "Дебаг")

        # Инициализируем содержимое вкладок
        self.init_main_tab()
        self.init_sessions_tab()
        self.init_api_tab()
        self.init_debug_tab()

        # Применяем темную тему
        self.set_dark_theme()

    def set_dark_theme(self):
        # Общий стиль
        self.setStyleSheet("""
            QWidget { background-color: #121212; color: white; }
            QPushButton { background-color: #333; color: white; border-radius: 5px; padding: 5px; }
            QPushButton:hover { background-color: #444; }
            QLineEdit, QTextEdit, QComboBox, QListWidget { background-color: #222; color: white; border: 1px solid #444; }
        """)
        # Стиль вкладок
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

        # Лог работы бота
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
    # Вкладка «Дебаг»
    ############################################
    def init_debug_tab(self):
        layout = QVBoxLayout(self.tab_debug)
        layout.addWidget(QLabel("Отладочный лог (все сообщения):"))
        self.debug_log_output = QTextEdit(self)
        self.debug_log_output.setReadOnly(True)
        layout.addWidget(self.debug_log_output)

    ############################################
    # Методы для работы с файлами
    ############################################
    def load_users_file(self):
        """Открываем диалог выбора файла с юзерами."""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self, "Выберите файл с юзерами", "",
            "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.users_file = file_path
            self.log_bot(f"📂 Файл с юзерами загружен: {file_path}")

    def load_attachment(self):
        """Открываем диалог выбора вложения."""
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
        """
        Лог работы бота (на вкладке 'Основное').
        + Дублируем в 'Дебаг', чтобы там были все сообщения.
        """
        self.bot_log_output.append(message)
        self.debug_log_output.append(message)
        print(message)

    def log_debug(self, message: str):
        """
        Отладочный лог (на вкладке 'Дебаг').
        """
        self.debug_log_output.append(message)
        print(message)

    ############################################
    # Работа с API-профилями
    ############################################
    def create_api_profile(self):
        """
        Создаёт новый профиль API (name, api_id, api_hash),
        сохраняет в api_profiles.json и обновляет список.
        """
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

        # Добавляем новый профиль в список
        new_profile = {
            "name": name,
            "api_id": api_id,
            "api_hash": api_hash
        }
        # Проверяем, нет ли профиля с таким именем
        for p in self.api_profiles:
            if p["name"] == name:
                self.log_bot(f"⚠️ Профиль API с именем '{name}' уже существует!")
                return

        self.api_profiles.append(new_profile)
        save_api_profiles(self.api_profiles)
        self.log_bot(f"✅ Профиль API '{name}' создан!")
        self.update_api_profiles_list()

    def delete_api_profile(self):
        """
        Удаляет выбранный профиль API из списка и сохраняет.
        """
        selected_items = self.api_list_widget.selectedItems()
        if not selected_items:
            self.log_bot("⚠️ Выберите профиль API для удаления!")
            return

        for item in selected_items:
            name_to_delete = item.text()
            # Ищем профиль с таким именем
            for p in self.api_profiles:
                if p["name"] == name_to_delete:
                    self.api_profiles.remove(p)
                    self.log_bot(f"✅ Профиль API '{name_to_delete}' удалён!")
                    break

        save_api_profiles(self.api_profiles)
        self.update_api_profiles_list()

    def update_api_profiles_list(self):
        """
        Обновляет список профилей API на вкладке «API»
        и комбо-бокс на вкладке «Основное».
        """
        # Очищаем виджеты
        self.api_list_widget.clear()
        self.api_profile_combo.clear()

        # Добавляем имена профилей
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
    # QR-вход для создания/авторизации сессии
    ############################################
    async def login_with_qr_async(self, session_name):
        """
        Создаёт или обновляет сессию с заданным именем через QR-код.
        Для работы нужен выбранный API-профиль в combo-box на вкладке «Основное».
        """
        try:
            self.log_debug("DEBUG: Начало метода login_with_qr_async")

            # Узнаём, какой API-профиль выбран на вкладке «Основное»
            selected_profile_name = self.api_profile_combo.currentText()
            if not selected_profile_name:
                self.log_bot("❌ Сначала создайте и выберите профиль API во вкладке 'API'.")
                return

            # Ищем данные профиля в self.api_profiles
            profile_data = None
            for p in self.api_profiles:
                if p["name"] == selected_profile_name:
                    profile_data = p
                    break
            if not profile_data:
                self.log_bot(f"❌ Профиль API '{selected_profile_name}' не найден!")
                return

            # Извлекаем API_ID, API_HASH
            api_id_str = profile_data["api_id"]
            api_hash_str = profile_data["api_hash"]
            self.log_debug(f"DEBUG: Используем профиль API '{selected_profile_name}' -> ID={api_id_str}, HASH={api_hash_str}")

            # Проверяем корректность API_ID
            try:
                api_id = int(api_id_str)
            except ValueError:
                self.log_bot("❌ API ID должен быть числом!")
                return

            api_hash = api_hash_str.strip()
            if not api_hash:
                self.log_bot("❌ API HASH пуст!")
                return

            # Полный путь к сессии
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
            # Смотрим, какой профиль API выбран
            selected_profile_name = self.api_profile_combo.currentText()
            if not selected_profile_name:
                self.log_bot("❌ Не выбран профиль API!")
                return

            # Ищем данные профиля
            profile_data = None
            for p in self.api_profiles:
                if p["name"] == selected_profile_name:
                    profile_data = p
                    break
            if not profile_data:
                self.log_bot(f"❌ Профиль API '{selected_profile_name}' не найден!")
                return

            # Проверяем API_ID
            try:
                api_id = int(profile_data["api_id"])
            except ValueError:
                self.log_bot("❌ API ID должен быть числом!")
                return

            api_hash = profile_data["api_hash"].strip()
            if not api_hash:
                self.log_bot("❌ API HASH пуст!")
                return

            # Проверяем выбранную сессию
            session_name = self.session_combo_box.currentText()
            if not session_name:
                self.log_bot("❌ Не выбрана сессия!")
                return

            # Путь к файлу сессии
            session_path = os.path.join(SESSIONS_FOLDER, session_name)

            # Подключаемся к Telegram, если клиент не создан или не подключен
            if self.client is None or not self.client.is_connected():
                self.client = TelegramClient(session_path, api_id, api_hash)
                await self.client.connect()
                self.log_debug("DEBUG: Подключение к Telegram в send_messages")

            if not await self.client.is_user_authorized():
                self.log_bot("❌ Сессия не авторизована! Сначала авторизуйтесь через QR‑код во вкладке 'Сессии'.")
                return

            self.log_bot("✅ Подключение к Telegram успешно!")

            # Загружаем список пользователей
            with open(self.users_file, "r", encoding="utf-8") as f:
                users = [line.strip() for line in f if line.strip()]

            processed_file = "processed.txt"
            processed_users = set()
            if os.path.exists(processed_file):
                with open(processed_file, "r", encoding="utf-8") as pf:
                    processed_users = set(pf.read().splitlines())

            # Отправляем сообщения
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
                    await asyncio.sleep(2)
                except Exception as e:
                    self.log_bot("❌ Ошибка при отправке сообщения. Бот завершил работу с ошибкой, смотрите Дебаг.")
                    self.log_debug(f"❌ Ошибка при отправке {username}: {e}")

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
        # Можно добавить любую дополнительную логику при закрытии
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
