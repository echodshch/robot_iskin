import RPi.GPIO as GPIO
import time
import logging
from gpio_manager import GPIOManager

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("motor_control.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MotorController:
    def __init__(self):
        
        # Настройка пинов
        self.FRONT_IN1 = 17
        self.FRONT_IN2 = 27
        self.FRONT_IN3 = 22
        self.FRONT_IN4 = 25
        self.ENA_FRONT = 20
        self.ENB_FRONT = 21
 
        self.BACK_IN1 = 16
        self.BACK_IN2 = 5
        self.BACK_IN3 = 6
        self.BACK_IN4 = 26
        self.ENA_BACK = 4
        self.ENB_BACK = 3

        # Инициализация GPIO
        self._setup_pins()
        # Инициализация ШИМ
        self._init_pwm()

        # Настройка скорости
        self.MIN_SPEED = 26
        self.MAX_SPEED = 30  # Ограничиваем максимальную скорость
        self._current_speed = self.MIN_SPEED  # Начальная скорость

    # Геттер
    @property
    def current_speed(self):
        return self._current_speed
    
    # Сеттер
    @current_speed.setter
    def current_speed(self, value):
        value = max(self.MIN_SPEED, min(self.MAX_SPEED, value))
        self._current_speed = value

    def _setup_pins(self):
        """Настраивает все GPIO пины как OUTPUT"""
        GPIO.setmode(GPIO.BCM)
        try:
            pins = [self.FRONT_IN1, self.FRONT_IN2, self.FRONT_IN3, self.FRONT_IN4, self.ENA_FRONT, self.ENB_FRONT,
                    self.BACK_IN1, self.BACK_IN2, self.BACK_IN3, self.BACK_IN4, self.ENA_BACK, self.ENB_BACK]
            for pin in pins:
                #logger.info(f"Настраиваю пин {pin} как OUTPUT")
                GPIO.setup(pin, GPIO.OUT)
                GPIO.output(pin, GPIO.LOW)
            logger.info("GPIO успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка при инициализации GPIO: {e}")
            raise

    def _init_pwm(self):
        """Инициализация ШИМ-каналов с проверкой"""
        try:
            self.pwm_front_A = GPIO.PWM(self.ENA_FRONT, 500)
            self.pwm_front_B = GPIO.PWM(self.ENB_FRONT, 500)
            self.pwm_back_A = GPIO.PWM(self.ENA_BACK, 500)
            self.pwm_back_B = GPIO.PWM(self.ENB_BACK, 500)

            # Явный запуск с 0% мощности
            self.pwm_front_A.start(0)
            self.pwm_front_B.start(0)
            self.pwm_back_A.start(0)
            self.pwm_back_B.start(0)
            logger.info("ШИМ успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации ШИМ: {e}")
            raise  

    def set_speed(self, speed):
        if self.current_speed is None:
            self.current_speed = 0
        """Плавное изменение скорости с защитой от float"""
        speed = int(round(max(0, min(self.MAX_SPEED, speed)))) 

        if speed == self.current_speed:
            return

        step = 1 if speed > self.current_speed else -1

        # Преобразуем в целые числа для range()
        start = int(round(self.current_speed))
        end = int(round(speed))
        
        for s in range(start, end, step):
            self.pwm_front_A.ChangeDutyCycle(s)
            self.pwm_front_B.ChangeDutyCycle(s)
            self.pwm_back_A.ChangeDutyCycle(s)
            self.pwm_back_B.ChangeDutyCycle(s)
            time.sleep(0.02)  # 20ms на каждый шаг
        
        self.current_speed = speed
        print(f"Установлена скорость: {speed}%")

    def move_forward(self, speed=None):
        """Движение вперед с указанной или текущей скоростью"""
        # Инициализация current_speed, если её нет
        if not hasattr(self, 'pwm_front_A'):
            self._init_pwm()  # Переинициализация при необходимости
        
        if speed is not None:
            self.set_speed(speed)

        # Передние моторы
        GPIO.output(self.FRONT_IN1, GPIO.HIGH)
        GPIO.output(self.FRONT_IN2, GPIO.LOW)
        GPIO.output(self.FRONT_IN3, GPIO.HIGH)
        GPIO.output(self.FRONT_IN4, GPIO.LOW)

        # Задние моторы
        GPIO.output(self.BACK_IN1, GPIO.HIGH)
        GPIO.output(self.BACK_IN2, GPIO.LOW)
        GPIO.output(self.BACK_IN3, GPIO.HIGH)
        GPIO.output(self.BACK_IN4, GPIO.LOW)

        logger.info("Движение вперед")
        #print(f"Состояние пинов: IN1={GPIO.input(self.FRONT_IN1)}, IN2={GPIO.input(self.FRONT_IN2)}")
        
    def calibrate_min_speed(self):
        print("Калибровка минимальной скорости...")

        # Устанавливаем моторы в режим "вперёд"
        GPIO.output(self.FRONT_IN1, GPIO.HIGH)
        GPIO.output(self.FRONT_IN2, GPIO.LOW)
        GPIO.output(self.FRONT_IN3, GPIO.HIGH)
        GPIO.output(self.FRONT_IN4, GPIO.LOW)
        GPIO.output(self.BACK_IN1, GPIO.HIGH)
        GPIO.output(self.BACK_IN2, GPIO.LOW)
        GPIO.output(self.BACK_IN3, GPIO.HIGH)
        GPIO.output(self.BACK_IN4, GPIO.LOW)

        for speed in range(0, 101):
            self.pwm_front_A.ChangeDutyCycle(speed)
            self.pwm_front_B.ChangeDutyCycle(speed)
            self.pwm_back_A.ChangeDutyCycle(speed)
            self.pwm_back_B.ChangeDutyCycle(speed)
            print(f"Пробуем скорость: {speed}%", end='\r')
            time.sleep(0.1)
            
            if input("Мотор начал вращаться? [y/n]: ").lower() == 'y':
                self.MIN_SPEED = speed + 5  # Добавляем запас 5%
                print(f"\n🎯 Минимальная рабочая скорость: {self.MIN_SPEED}%")
                self.set_speed(0)  # Останавливаем мотор
                return
        print("Мотор не запустился! Проверьте питание и подключение.")

    def move_backward(self):
        
        logger.info("Движение назад")
        # Передние моторы
        GPIO.output(self.FRONT_IN1, GPIO.LOW)
        GPIO.output(self.FRONT_IN2, GPIO.HIGH)
        GPIO.output(self.FRONT_IN3, GPIO.LOW)
        GPIO.output(self.FRONT_IN4, GPIO.HIGH)
        # Задние моторы
        GPIO.output(self.BACK_IN1, GPIO.LOW)
        GPIO.output(self.BACK_IN2, GPIO.HIGH)
        GPIO.output(self.BACK_IN3, GPIO.LOW)
        GPIO.output(self.BACK_IN4, GPIO.HIGH)
    
    def turn_left(self):
        
        logger.info("Поворот налево")
        # левое колесо - назад
        GPIO.output(self.FRONT_IN1, GPIO.LOW)
        GPIO.output(self.FRONT_IN2, GPIO.HIGH)
        GPIO.output(self.BACK_IN1, GPIO.HIGH)
        GPIO.output(self.BACK_IN2, GPIO.LOW)
        # правое колесо - вперед
        GPIO.output(self.FRONT_IN3, GPIO.HIGH)
        GPIO.output(self.FRONT_IN4, GPIO.LOW)
        GPIO.output(self.BACK_IN3, GPIO.LOW)
        GPIO.output(self.BACK_IN4, GPIO.HIGH)
    
    def turn_right(self):
        
        logger.info("Поворот направо")
        # левое колесо - вперед
        GPIO.output(self.FRONT_IN1, GPIO.HIGH)
        GPIO.output(self.FRONT_IN2, GPIO.LOW)
        GPIO.output(self.BACK_IN1, GPIO.LOW)
        GPIO.output(self.BACK_IN2, GPIO.HIGH)
        # правое колесо - назад
        GPIO.output(self.FRONT_IN3, GPIO.LOW)
        GPIO.output(self.FRONT_IN4, GPIO.HIGH)
        GPIO.output(self.BACK_IN3, GPIO.HIGH)
        GPIO.output(self.BACK_IN4, GPIO.LOW)
    
    def stop(self):
        self.set_speed(0)
        logger.info("Остановка")
        # Остановка всех моторов
        GPIO.output(self.FRONT_IN1, GPIO.LOW)
        GPIO.output(self.FRONT_IN2, GPIO.LOW)
        GPIO.output(self.FRONT_IN3, GPIO.LOW)
        GPIO.output(self.FRONT_IN4, GPIO.LOW)
        GPIO.output(self.BACK_IN1, GPIO.LOW)
        GPIO.output(self.BACK_IN2, GPIO.LOW)
        GPIO.output(self.BACK_IN3, GPIO.LOW)
        GPIO.output(self.BACK_IN4, GPIO.LOW)
    
    def emerg_stop(self, reverse_time=0.3):
        logger.info("Экстренная остановка")
        # Экстренное торможение с обратным ходом
        GPIO.output(self.FRONT_IN1, GPIO.LOW)
        GPIO.output(self.FRONT_IN2, GPIO.HIGH)
        GPIO.output(self.FRONT_IN3, GPIO.LOW)
        GPIO.output(self.FRONT_IN4, GPIO.HIGH)
        GPIO.output(self.BACK_IN1, GPIO.LOW)
        GPIO.output(self.BACK_IN2, GPIO.HIGH)
        GPIO.output(self.BACK_IN3, GPIO.LOW)
        GPIO.output(self.BACK_IN4, GPIO.HIGH)

        if reverse_time > 0:
            time.sleep(reverse_time)  # Длительность обратного хода

        # Полная остановка
        self.set_speed(0)
        GPIO.output(self.FRONT_IN1, GPIO.LOW)
        GPIO.output(self.FRONT_IN2, GPIO.LOW)
        GPIO.output(self.FRONT_IN3, GPIO.LOW)
        GPIO.output(self.FRONT_IN4, GPIO.LOW)
        GPIO.output(self.BACK_IN1, GPIO.LOW)
        GPIO.output(self.BACK_IN2, GPIO.LOW)
        GPIO.output(self.BACK_IN3, GPIO.LOW)
        GPIO.output(self.BACK_IN4, GPIO.LOW)

    def cleanup(self):
        """Корректное завершение"""
        self.stop()
        self.pwm.stop()
        GPIO.cleanup()

