import os
import subprocess
import sys
import threading
import time

import requests
from flask import Flask, jsonify, request
from packaging import version

from config import UPDATE_CHECK_URL  # URL для проверки обновлений
from logger import logging

# Текущая версия приложения
VERSION = "1.0.0"
CHECK_INTERVAL = 3600  # Интервал проверки в секундах (1 час)


# Flask приложение
app = Flask(__name__)


# Основной маршрут для открытия папок
@app.route("/open-folder", methods=["POST"])
def open_folder():
    folder_path = request.json.get("folder_path")
    if folder_path and os.path.exists(folder_path):
        try:
            # Открываем папку в зависимости от ОС
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
    while True:
        try:
            logging.info(f"Текущая версия: {VERSION}. Проверка обновлений...")

            response = requests.get(UPDATE_CHECK_URL)
            logging.info(f"Ответ от сервера: {response.status_code}")
            if response.status_code == 200:
                data = response.json()

                latest_version = data.get("version")
                logging.info(f"Последняя версия: {latest_version}")
                download_url = data.get("download_url")

                if not latest_version or not download_url:
                    logging.warning(
                        "Ответ от сервера некорректен. Нет версии или ссылки."
                    )
                    continue

                # Сравниваем версии
                if version.parse(latest_version) > version.parse(VERSION):
                    logging.info(
                        f"Доступна новая версия: {latest_version}. Скачивание..."
                    )
                    download_and_update(download_url)
                else:
                    logging.info("Новых обновлений нет.")
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

        # Ждём перед следующей проверкой
        time.sleep(CHECK_INTERVAL)


# Функция загрузки и установки новой версии
def download_and_update(download_url):
    try:
        # Скачиваем файл
        response = requests.get(download_url, stream=True)
        if response.status_code == 200:
            new_version_path = "client_app_new.exe"
            with open(new_version_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024):
                    f.write(chunk)
            logging.info("Обновление скачано. Замена старой версии...")

            # Перезапускаем приложение с новой версией
            restart_application(new_version_path)
    except Exception as e:
        logging.error(f"Ошибка загрузки обновления: {e}")


# Функция перезапуска приложения
def restart_application(new_version_path=None):
    try:
        current_exe = sys.argv[0]
        if new_version_path:
            # Создаём резервную копию текущей версии
            os.rename(current_exe, current_exe + ".old")
            # Заменяем старый файл новым
            os.rename(new_version_path, current_exe)

        # Перезапускаем приложение
        subprocess.Popen([current_exe])
        sys.exit(0)
    except Exception as e:
        logging.error(f"Ошибка при перезапуске: {e}")


# Основной запуск приложения
if __name__ == "__main__":
    # Запуск проверки обновлений в отдельном потоке
    threading.Thread(target=check_for_updates, daemon=True).start()

    # Запуск Flask приложения
    app.run(host="localhost", port=5001)
    logging.info("Flask приложение запущено")
