import time
import random
import logging
import cv2
import atexit
import asyncio
import threading
from concurrent.futures import Future
import numpy as np
from picamera2 import Picamera2
from libcamera import controls
from motor_control import MotorController
from distance_sensor import DistanceSensor

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StuckDetector:
    def __init__(self, motor, distance_sensor):
        self.motor = motor
        self.distance_sensor = distance_sensor
        self.last_valid_distance = None
        self.last_movement_time = time.time()
        self.error_count = 0
        self.MAX_ERRORS = 3
        self.STUCK_TIME = 1.5
        self.MIN_CHANGE = 2.0

    def check_stuck(self):
        try:
            dist = self.distance_sensor.get_distance()

            if dist is None:
                self.error_count += 1
                if self.error_count >= self.MAX_ERRORS:
                    return True
                return False

            # Первоначальная проверка изменения
            if self.last_valid_distance is None:
                self.last_valid_distance = dist
                self.last_movement_time = time.time()
                return False

            if abs(dist - self.last_valid_distance) >= self.MIN_CHANGE:
                self.last_valid_distance = dist
                self.last_movement_time = time.time()
                self.error_count = 0
                return False

            return (time.time() - self.last_movement_time) >= self.STUCK_TIME

        except Exception as e:
            logger.error(f"Ошибка при проверке застревания: {e}")
            return False
        
    def recovery_procedure(self):
        """Процедура выхода из застревания"""
        logger.info("Выполняю процедуру анти-застревания...")
        
        # 1. Отъезд назад
        self.motor.set_speed(self.motor.MIN_SPEED)
        self.motor.move_backward()
        time.sleep(1.0)
        
        # 2. Поворот в случайном направлении
        if random.choice([True, False]):
            self.motor.turn_left()
        else:
            self.motor.turn_right()
        time.sleep(0.8)
        
        # 3. Попытка движения вперед
        self.motor.move_forward(self.motor.MIN_SPEED)
        time.sleep(1.5)
        
        self.reset_detector()
    
    def reset_detector(self):
        """Сброс состояния детектора"""
        self.last_distance = None
        self.last_change_time = time.time()

class NavigationSystem:
    def __init__(self, motor, distance_sensor):
        self.motor = motor
        self.distance_sensor = distance_sensor
        self.stuck_detector = StuckDetector(motor, distance_sensor)
        self.SAFE_DISTANCE = 70  # см (начинать плавное торможение)
        self.EMERGENCY_DISTANCE = 50  # см (начинать объезд)
        self.CRITICAL_DISTANCE = 20  # см (экстренная остановка)
        self.turn_time = None

    @atexit.register
    def log_shutdown():
        with open('/home/mira/last_crash.log', 'a') as f:
            f.write(f"Shutdown at {time.ctime()}\n")

    async def recovery_sequence(self):
        """Полная процедура восстановления после застревания"""
        #logger.info("Запуск комплексного восстановления")
        
        # 1. Экстренный останов
        self.motor.emerg_stop()
        await asyncio.sleep(1)
        
        # 2. Отъезд назад (1 секундa)
        self.motor.set_speed(self.motor.MIN_SPEED + 10)
        self.motor.move_backward()
        await asyncio.sleep(1)
        
        # 3. Случайный поворот (30-60 градусов)
        self.turn_time = random.uniform(0.5, 1.0)
        if random.choice([True, False]):
            self.motor.turn_left()
        else:
            self.motor.turn_right()
        await asyncio.sleep(self.turn_time)
        self.motor.stop()
        
        # 4. Плавный старт
        self.motor.move_forward(self.motor.MIN_SPEED)
        logger.info("Восстановление завершено")

    async def monitor_distance(self):
        while True:
            # Проверка застревания (работает даже при ошибках датчика)
            if self.stuck_detector.check_stuck():
                logger.warning("Застревание обнаружено!")
                await self.recovery_sequence()
                continue
                
            # Основная логика движения
            distance = self.distance_sensor.get_distance()

            if distance and distance < self.CRITICAL_DISTANCE:
                logger.info("Расстояние < см, остановка")
                self.motor.emerg_stop()  # Плавная остановка
                await asyncio.sleep(1)
                logger.info("Расстояние < 10см, объезд")
                await self.bypass_obstacle()

            # Основная логика объезда препятствий
            elif distance and distance < self.EMERGENCY_DISTANCE:
                logger.info("Объезд")
                await self.bypass_obstacle()

            elif distance and distance < self.SAFE_DISTANCE:
                # Линейное снижение скорости от 100% до 30% при 70 см -> 50 см
                logger.info("Плавное снижение скорости")
                speed_percent = 30 + (distance - 50) * (70 / (self.SAFE_DISTANCE - 50))
                self.motor.set_speed(max(30, speed_percent))  # Не ниже 30%

            # Проверка застревания в любом режиме
            if self.stuck_detector.check_stuck():
                logger.info("Обнаружено застревание!")
                self.stuck_detector.recovery_procedure()
            
            await asyncio.sleep(0.05)
    
    async def bypass_obstacle(self):
        """Логика объезда препятствия"""
        logger.info(f"Препятствие, начинаю объезд...")
        import traceback
        # Покажет, откуда идёт вызов
        #traceback.print_stack()  

        # Торможение
        self.motor.stop()

        # Маневр объезда
        self.motor.set_speed(self.motor.MIN_SPEED)
        self.motor.move_backward()

        # Случайный выбор направления
        turn_direction = random.choice(['right', 'left'])

        # Устанавливаем скорость и направление
        self.motor.set_speed(30)
        if turn_direction == 'right':
            self.motor.turn_right()
        else:
            self.motor.turn_left()

        # Ждем достаточное время для поворота
        await asyncio.sleep(0.1)

        # Останавливаем моторы после поворота
        self.motor.stop()
        
        # Плавный старт движения вперед
        self.motor.move_forward(self.motor.MIN_SPEED + 20)  # Импульс для старта
        await asyncio.sleep(0.3)
        self.motor.move_forward(self.motor.MIN_SPEED)

        # Время начала манёвра
        #start_time = time.time()

        # Выполняем поворот в течение turn_time с проверкой застревания
        #while time.time() - start_time < self.turn_time:
        #    if self.stuck_detector.check_stuck():
        #        break
            #await asyncio.sleep(0.05)  # Частота проверки застревания

        # Если застряли - выполняем процедуру восстановления
        if self.stuck_detector.check_stuck():
            logger.info("Обнаружено застревание!")
            self.stuck_detector.recovery_procedure()

        await asyncio.sleep(0.05)


class ObstacleDetector:
    def __init__(self, sensor, motor):
        self.sensor = sensor
        self.motor = motor
        self.nav = NavigationSystem(motor, sensor)
        self.loop = asyncio.new_event_loop() 
        self.EMERGENCY_DISTANCE = 50  # см
        self.SAFE_DISTANCE = 70  # см
        self.last_detection_time = 0
        self.detection_interval = 0.5  # Интервал между проверками (сек)

        # Запускаем loop в отдельном потоке сразу при инициализации
        self.thread = threading.Thread(
            target=self._run_loop, 
            daemon=True,
            name="EventLoopThread"
        )
        self.thread.start()

    def _run_loop(self):
        """Запуск event loop в отдельном потоке"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def process_frame(self, frame):
        """Основной метод обработки кадра"""
        current_time = time.time()
        if current_time - self.last_detection_time < self.detection_interval:
            return
            
        try:
            #cv2.imshow("process_frame", frame)
            # Конвертация цветового пространства с проверкой
            frame_rgb = self._convert_frame(frame)
            
            if self._detect_obstacles(frame_rgb):
                logger.info(f"Препятствие, начинаю объезд...")
                # Детекция препятствий
                self._avoid_obstacle(frame_rgb)
        
                # Продолжаем движение
                #self.motor.forward(self.motor.MIN_SPEED)      

        except Exception as e:
            logger.error(f"Критическая ошибка обработки: {e}")

    def _convert_frame(self, frame):
        """Безопасная конвертация цветового пространства"""
        try:
            if frame.ndim == 2:  # Если ч/б кадр
                return cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif frame.shape[2] == 3:  # Если уже BGR
                return frame.copy()
            else:
                return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        except Exception as e:
            self.logger.error(f"Ошибка конвертации: {e}")
            raise

    def _avoid_obstacle(self, distance):
        if not hasattr(self, 'loop') or self.loop.is_closed():
            self.loop = asyncio.new_event_loop()

        future = asyncio.run_coroutine_threadsafe(
            self.nav.bypass_obstacle(),
            self.loop
        )
        future.add_done_callback(self._obstacle_avoided)

    def _safe_imshow(self, window_name, frame):
        """Защищённое отображение кадра"""
        if not self._validate_frame(frame):
            return
            
        try:
            cv2.imshow(window_name, frame)
            cv2.waitKey(1)
        except Exception as e:
            self.logger.error(f"Ошибка отображения: {e}")

    def _obstacle_avoided(self, future):
        try:
            result = future.result()
            #print(f"Объезд завершен: {result}")
        except Exception as e:
            print(f"Ошибка при объезде: {e}")

    def _detect_obstacles(self, frame):
        """Проверка нависающих препятствий"""
        try:
            if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
                self.logger.warning("Получен невалидный кадр")
                return False
        
            # 2. Конвертация в RGB/BGR с проверкой формата
            if frame.ndim == 2:  # Если кадр ч/б
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif frame.shape[2] == 4:  # Если RGBA
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            else:  # Если уже BGR (3 канала)
                frame_rgb = frame.copy()

            # 3. Выделение ROI 
            height, width = frame_rgb.shape[:2]
            #roi = frame_rgb[:int(height*0.5), :]    #(верхние 50%)
            roi = frame_rgb[int(height*0.5):, :]    #(нижние 50%)

            # 4. Детекция препятствий
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 30, 100)         # Выделение границ алгоритмом Canny

            # 5. Расчет плотности границ
            edge_density = cv2.countNonZero(edges) / (roi.size / 3)

            # 6. Отладочное отображение
            debug_frame = frame_rgb.copy()
            cv2.putText(debug_frame, f"Density: {edge_density:.2f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            if hasattr(self, '_debug_window'):
                cv2.imshow("Obstacle Debug", debug_frame)
                cv2.waitKey(1)
            else:
                self._debug_window = True
                cv2.namedWindow("Obstacle Debug", cv2.WINDOW_NORMAL)
            if edge_density > 0.05:
                logger.info(f"Препятствие {edge_density}")
            return edge_density > 0.05
        
        except Exception as e:
            self.logger.error(f"Ошибка в _check_overhead: {str(e)}")
            return False
        
    def stop(self):
        """Корректная остановка"""
        self.stop_event.set()
        self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread.is_alive():
            self.thread.join(timeout=1)