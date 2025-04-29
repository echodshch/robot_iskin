import cv2
import time
import threading
import logging
import signal
import sys
import os
import subprocess
import traceback
import asyncio
from typing import Optional
import gc
from camera_manager import CameraManager
from motor_control import MotorController
from distance_sensor import DistanceSensor
from navigation import NavigationSystem
from navigation import ObstacleDetector
from object_detector import ObjectDetector

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/detect_dog.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RobotSystem:
    def __init__(self):
        # Инициализация компонентов
        self.camera = CameraManager()
        self.motor = MotorController()
        self.sensor = DistanceSensor()
        self.detector = ObjectDetector()
        self._stop_event = threading.Event()
        self.dog_detected_event = threading.Event()
        self._lock = threading.Lock()
        self.nav = NavigationSystem(self.motor, self.sensor)
        self.loop = asyncio.new_event_loop()
        self.detect_obst = ObstacleDetector(self.sensor, self.motor)
        self._last_detection = time.time()
                
        # Флаги состояния
        self.running = False
        self.game_script_running = False
        self._game_process: Optional[subprocess.Popen] = None
        
        # Потоки обработки
        self.threads = []

        # Запускаем event loop в отдельном потоке
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

    def moving(self):
        """Поток движения и объезда"""
        try:
            while not self._stop_event.is_set():
                distance = self.sensor.get_distance()
                logger.info(f"Текущее измерение: {distance:.2f} см")
                if distance is not None:
                    # Запускаем асинхронную задачу
                    future = asyncio.run_coroutine_threadsafe(
                        self.nav.monitor_distance(),
                        self.loop
                    )
                    try:
                        future.result(timeout=0.1)  # Ожидаем завершения
                    except asyncio.TimeoutError:
                        pass  # Продолжаем цикл
                time.sleep(0.1)

        except Exception as e:
            logger.error(f"Ошибка в потоке движения и объезда: {e}")        

    def detect_objects(self):
        """Поток обнаружения объектов"""
        logger.info("Запуск потока обнаружения объектов")
        while not self._stop_event.is_set():
            try:
                #logger.info("Запрашиваю кадр..")
                frame = self.camera.get_frame()
                if frame is None:
                    logger.info("Нет кадра, пропускаем итерацию")
                    continue

                if frame is not None:
                    detections = self.detector.detect_objects(frame, target_label='dog')

                    if detections:
                        cv2.imshow("dog", frame)
                        self.dog_detected_event.set()
                        break

            except Exception as e:
                logger.error(f"Ошибка в потоке обнаружения: {e}")
                break

    def detect_obstacles(self):
        """Поток обнаружения препятствий через камеру"""
        logger.info("Запуск потока обнаружения препятствий через камеру")
        while not self._stop_event.is_set():
            try:
                frame = self.camera.get_frame()
                if frame is None:
                    continue
                if frame is not None:
                    #cv2.imshow("detect_obstacles", frame)
                    self.detect_obst.process_frame(frame)
                else:
                    logger.info("Временное отсутствие кадров (ожидание...)")
                time.sleep(0.05)
            except Exception as e:
                logger.error(f"Ошибка в потоке препятствий через камеру: {e}")
                break

    def handle_dog_detection(self):
        """Обработка обнаружения собаки"""
        try:
            self.game_script_running = True

            # Остановить в основном процессе
            self.stop()
            time.sleep(2)
            gc.collect()

            # Запуск в новом процессе с отсоединением
            logger.info("Собака обнаружена! Запуск игры.")
            subprocess.Popen(
                [sys.executable, "play_with_dog.py"],
                start_new_session=True
            )
            
            # Гарантированный выход
            logging.info("Игра успешно запущена, завершаю основной скрипт")
            os._exit(0)

        except Exception as e:
            logger.error(f"Ошибка запуска игры: {e}")

    def start(self):
        """Запуск системы"""
        self.running = True
        
        # Инициализация потоков
        #self.threads = [
        #    threading.Thread(target=self.detect_obstacles)
        #]
        #
        ## Запуск потоков
        #for thread in self.threads:
        #    thread.start()
        
        # Старт движения
        self.motor.move_forward(30)
        logger.info("Робот начал движение")
        robot.moving()

        # Запуск потока обнаружения
        detection_thread = threading.Thread(
            target=self.detect_objects,
            name="DetectionThread"
        )
        detection_thread.start()

        # Ожидаем событие обнаружения или остановки
        while not self._stop_event.is_set():
            if self.dog_detected_event.wait(timeout=0.5):
                self.handle_dog_detection()  # Вызывается в главном потоке!
                break

        detection_thread.join(timeout=1)
        logger.info("Основной цикл завершен")

    def stop(self):
        """Остановка всех компонентов"""
        with self._lock:
            if self._stop_event.is_set():
                return

            self._stop_event.set()
            self.running = False
            logger.info("Инициирована остановка")

            # Остановка моторов
            self.motor.emerg_stop()
            self.camera.stop()
            self.loop.call_soon_threadsafe(self.loop.stop)
            if self.loop.is_running():
                self.loop.call_soon_threadsafe(self.loop.stop)
        
            # Остановка потоков
            #for thread in self.threads:
            #    if thread is not threading.current_thread():
            #        thread.join(timeout=1)
            #    if thread.is_alive():
            #        logger.warning(f"❌ Поток {thread.name} не завершился!")
            #dump_threads()

            logger.info("Все компоненты остановлены")
            #sys.exit(0)  # Корректный выход

def stop_all(signum=None, frame=None):
    """Глобальная функция остановки"""
    print("\nОстановка всех движений и очистка ресурсов...")
    robot.stop()  # Выключаем систему робота

    sys.exit(0 if signum == signal.SIGINT else 1)

def signal_handler(signum, frame):
    """Универсальный обработчик сигналов"""
    if not hasattr(signal_handler, 'called'):  # Защита от повторных вызовов
        signal_handler.called = True
        logger.warning(f"Получен сигнал {signum}, инициирую остановку...")
        
        # Глобальный доступ к объекту робота
        global robot
        if 'robot' in globals():
            robot.stop()
        
        # Принудительный выход через 1 секунду, если система не остановилась
        sys.exit(1)

def dump_threads():
    logger.info("📍 Dump всех потоков:")
    for thread_id, frame in sys._current_frames().items():
        logger.info(f"🔹 Поток {thread_id}:")
        for filename, lineno, name, line in traceback.extract_stack(frame):
            logger.info(f"  File {filename}, line {lineno}, in {name}")
            if line:
                logger.info(f"    {line.strip()}")

if __name__ == "__main__":
    robot = RobotSystem()
        
    # Регистрация обработчиков сигналов
    signal.signal(signal.SIGINT, lambda s, f: signal_handler(s, f))
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler(s, f))
        
    try:
        loop = asyncio.new_event_loop()
        threading.Thread(target=loop.run_forever, daemon=True).start()

        # Запуск системы
        robot.start()
        
        # Главный цикл
        while True:
            time.sleep(1)
            robot.game_script_running = False  # Сброс флага
            
    except Exception as e:
        logger.critical(f"Фатальная ошибка: {e}", exc_info=True)
        stop_all()
    except KeyboardInterrupt:
        print("Завершение работы...")
        stop_all()

    finally:
        robot.stop()
        stop_all()