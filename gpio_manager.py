import RPi.GPIO as GPIO
import logging
from typing import Dict, Set

class GPIOManager:
    _instance = None
    _initialized = False
    _used_pins: Dict[int, str] = {}  # pin: purpose
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            self._initialized = True
            logging.info("GPIO Manager инициализирован (режим BCM)")
    
    def setup_pin(self, pin: int, mode: int, purpose: str):
        if pin in self._used_pins:
            if GPIO.gpio_function(pin) != mode:
                raise RuntimeError(f"Конфликт пина {pin}: уже используется как {self._used_pins[pin]}")
            return
            
        GPIO.setup(pin, mode)
        self._used_pins[pin] = purpose
        logging.debug(f"Пин {pin} настроен как {mode} для {purpose}")
    
    def cleanup(self):
        if self._initialized:
            GPIO.cleanup()
            self._initialized = False
            logging.info("Ресурсы GPIO освобождены")

    def __del__(self):
        self.cleanup()