import subprocess
import time
import logging
import json
from vosk import Model, KaldiRecognizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("voice_command_listener.log"),
        logging.StreamHandler()
    ]
)

# Путь к модели vosk
MODEL_PATH = "vosk_model/vosk-model-small-ru-0.22"

# Настройки arecord для bluetooth через bluealsa
ARECORD_CMD = [
    "arecord",
    "-D", "bluealsa:DEV=E5:AF:7E:BA:3E:06,PROFILE=sco",
    "-f", "S16_LE",
    "-r", "16000",
    "-c", "1",
    "-"
]

def handle_command(command):
    if command is None:
        return

    if "поиграй с собакой" in command:
        logging.info("Запуск скрипта игры с собакой...")
        subprocess.Popen(["python3", "detect_dog.py"])
    elif "остановись" in command:
        logging.info("Остановка всех скриптов...")
        subprocess.run(["pkill", "-f", "detect_dog.py"])
    elif "выйди" in command:
        logging.info("Завершение работы...")
        exit()
    elif "тест" in command:
        subprocess.run('echo "тест" | RHVoice-test -p Anna -o temp.wav', shell=True, check=True)

        # Конвертируем temp.wav в temp_fixed.wav
        subprocess.run(["sox", "temp.wav", "--rate", "16000", "--bits", "16", "--channels", "1", "temp_fixed.wav"], check=True)

        # Воспроизводим temp_fixed.wav через bluealsa
        subprocess.run(["aplay", "-D", "bluealsa:DEV=E5:AF:7E:BA:3E:06,PROFILE=sco", "temp_fixed.wav"], check=True)
    else:
        logging.warning(f"Неизвестная команда: {command}")

def main():
    logging.info("Инициализация модели Vosk...")
    model = Model(MODEL_PATH)
    recognizer = KaldiRecognizer(model, 16000)

    logging.info("Запуск arecord для захвата аудио...")
    try:
        process = subprocess.Popen(
            ARECORD_CMD,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
    except Exception as e:
        logging.error(f"Ошибка запуска arecord: {e}")
        return

    if process.stdout is None:
        logging.error("Нет потока stdout от arecord!")
        return

    logging.info("Голосовой ассистент запущен. Ожидание команд...")

    try:
        while True:
            data = process.stdout.read(4000)
            if not data:
                logging.warning("Нет данных от микрофона. Завершение работы.")
                break

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                command = result.get('text', '').strip().lower()
                logging.info(f"Распознано: '{command}'")

                if command:
                    handle_command(command)
            else:
                partial = json.loads(recognizer.PartialResult())
                logging.debug(f"Промежуточный результат: {partial.get('partial', '')}")

            time.sleep(0.1)  # чтобы не грузить CPU

    except KeyboardInterrupt:
        logging.info("Принудительное завершение пользователем (Ctrl+C)")
    finally:
        process.terminate()
        logging.info("Процесс arecord остановлен.")

if __name__ == "__main__":
    main()
