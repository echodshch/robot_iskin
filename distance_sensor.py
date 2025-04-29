import time
import logging
import RPi.GPIO as GPIO
from statistics import median
from gpio_manager import GPIOManager

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DistanceSensor:
    def __init__(self):
        # Настройка пинов для ультразвукового датчика
        self.gpio = GPIOManager()
        self.TRIG = 23 # Пин Trig серый
        self.ECHO = 24 # Пин Echo

        # Явная инициализация пинов
        self.gpio.setup_pin(self.TRIG, GPIO.OUT, "Ультразвуковой датчик (TRIG)")
        self.gpio.setup_pin(self.ECHO, GPIO.IN, "Ультразвуковой датчик (ECHO)")
        GPIO.output(self.TRIG, False)

    def get_distance(self, samples=5, max_deviation=10, timeout=0.1):
        """Измерение расстояния с фильтрацией выбросов"""
        valid_readings = []

        for _ in range(samples):
            try:
                # Генерация импульса
                GPIO.output(self.TRIG, True)
                time.sleep(0.00001)
                GPIO.output(self.TRIG, False)

                pulse_start = time.time()
                timeout_time = time.time() + timeout  # Установка таймаута
                while GPIO.input(self.ECHO) == 0 and time.time() < timeout_time:
                    pulse_start = time.time()

                pulse_end = time.time()
                while GPIO.input(self.ECHO) == 1 and time.time() < timeout_time:
                    pulse_end = time.time()

                # Расчет расстояния
                duration = pulse_end - pulse_start
                current_distance = (duration * 34300) / 2  # в см
                logger.info(f"[{self.name}] Текущее измерение: {current_distance:.2f} см")

                if 2 <= current_distance <= 400:
                    valid_readings.append(current_distance)

                time.sleep(0.02)

            except Exception as e:
                logger.warning(f"Ошибка измерения: {str(e)}")
                continue
            
        if not valid_readings:
            return None

        avg_distance = sum(valid_readings) / len(valid_readings)
        filtered = [x for x in valid_readings if abs(x - avg_distance) <= max_deviation]

        if not filtered:
            return round(avg_distance, 2)

        return round(sum(filtered) / len(filtered), 2)
