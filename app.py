import os
import subprocess
import sys
import threading
import time

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from packaging import version

from config import UPDATE_CHECK_URL  # URL для проверки обновлений
from logger import logging

# Flask приложение
app = Flask(__name__)
CORS(app)


# Загружаем текущую версию из файла
def load_version():
    """Загружает текущую версию приложения из файла version.txt."""
    try:
        with open("version.txt", "r") as file:
            return file.read().strip()
    except FileNotFoundError:
        logging.warning("Файл версии не найден. Используется версия по умолчанию.")
        return "1.0.0"


# Сохраняем новую версию в файл
def save_version(new_version):
    """Сохраняет новую версию приложения в файл version.txt."""
    try:
        with open("version.txt", "w") as file:
            file.write(new_version)
        logging.info(f"Версия обновлена до: {new_version}")
    except Exception as e:
        logging.error(f"Ошибка сохранения версии: {e}")


# Основной маршрут для открытия папок
@app.route("/open-deal-folder", methods=["POST"])
def open_folder():
    """
    Открывает указанную папку на клиентском компьютере.
    """
    folder_path = request.json.get("folder_path")
    logging.info(f"Папка для открытия: {folder_path}")
    if folder_path and os.path.exists(folder_path):
        try:
            if os.name == "nt":  # Windows
                os.startfile(folder_path)
            elif os.uname().sysname == "Darwin":  # macOS
                subprocess.run(["open", folder_path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", folder_path], check=True)
            return jsonify({"status": "success"}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "error", "message": "Invalid path"}), 400


# Функция проверки обновлений
def check_for_updates():
    """
    Проверяет наличие обновлений на сервере и, если доступны, скачивает и применяет их.
    """
    while True:
        try:
            current_version = load_version()
            logging.info(f"Текущая версия: {current_version}. Проверка обновлений...")

            response = requests.get(UPDATE_CHECK_URL)
            logging.info(f"Ответ от сервера: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                latest_version = data.get("version")
                download_url = data.get("download_url")

                if not latest_version or not download_url:
                    logging.warning(
                        "Некорректный ответ от сервера: отсутствуют версия или URL."
                    )
                    continue

                if version.parse(latest_version) > version.parse(current_version):
                    logging.info(
                        f"Доступна новая версия: {latest_version}. Скачивание..."
                    )
                    download_and_update(download_url, latest_version)
                else:
                    logging.info(f"Вы используете последнюю версию: {current_version}.")
            else:
                logging.warning(
                    f"Не удалось получить обновления. Статус: {response.status_code}"
                )

        except requests.ConnectionError:
            logging.error("Ошибка соединения с сервером. Проверьте подключение.")
        except requests.Timeout:
            logging.error("Превышено время ожидания ответа от сервера.")
        except Exception as e:
            logging.error(f"Ошибка проверки обновлений: {e}")

        time.sleep(15)  # Проверяем обновления раз в час


# Функция загрузки и установки новой версии
def download_and_update(download_url, latest_version):
    """
    Скачивает новую версию приложения и перезапускает её.
    """
    try:
        new_version_path = f"client_app_v{latest_version}.exe"
        response = requests.get(download_url, stream=True)
        if response.status_code == 200:
            with open(new_version_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=1024):
                    file.write(chunk)
            logging.info(f"Новая версия скачана: {new_version_path}")

            # Сохраняем новую версию в файл version.txt
            save_version(latest_version)

            # Запускаем новую версию и завершаем текущую
            logging.info(f"Запуск новой версии: {new_version_path}")
            subprocess.Popen([new_version_path])
            sys.exit(0)  # Завершение текущего процесса
        else:
            logging.error(f"Ошибка загрузки файла. Статус: {response.status_code}")
    except Exception as e:
        logging.error(f"Ошибка загрузки обновления: {e}")


# Основной запуск приложения
if __name__ == "__main__":
    # Запуск проверки обновлений в отдельном потоке
    threading.Thread(target=check_for_updates, daemon=True).start()

    # Запуск Flask-приложения для обработки локальных запросов
    logging.info(f"Flask приложение запущено на порте 5001")
    try:
        app.run(host="localhost", port=5001)
    except Exception as e:
        logging.error(f"Ошибка запуска Flask приложения: {e}")
