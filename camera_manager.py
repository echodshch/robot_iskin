import queue
import threading
import time
from picamera2 import Picamera2
from libcamera import controls

class CameraManager:
    def __init__(self):
        self.picam2 = Picamera2()
        self._stop_event = threading.Event()
        self.frame_queue = queue.Queue(maxsize=2)
        self._capture_thread = None

        # Настройка камеры (важно: используем RGB888)
        self.config = self.picam2.create_still_configuration(
            main={"size": (640, 480), "format": "RGB888"},
            buffer_count=2
        )
        self.picam2.configure(self.config)

        self.start()

    def start(self):
        """Явный запуск потока захвата"""
        if not self._capture_thread or not self._capture_thread.is_alive():
            self._stop_event.clear()
            self.picam2.start()
            self._capture_thread = threading.Thread(
                target=self._capture_worker,
                daemon=True,
                name="CameraCaptureThread"
            )
            self._capture_thread.start()
            time.sleep(2)  # Важно: даем камере время на инициализацию

    def _capture_worker(self):
        test_count = 0
        while not self._stop_event.is_set():
            try:
                frame = self.picam2.capture_array()
                if frame is None:
                    print("Получен None-кадр")
                    continue

                #print(f"Размер кадра: {frame.shape}, тип: {frame.dtype}")

                # Сохраняем тестовый кадр
                #if test_count < 3:
                #    import cv2
                #    cv2.imwrite(f"test_frame_{test_count}.jpg", frame)
                #    test_count += 1

                try:
                    self.frame_queue.put_nowait(frame)
                except queue.Full:
                    pass

            except Exception as e:
                print(f"Ошибка в потоке захвата: {e}")

    def get_frame(self):
        """Получение кадра из очереди"""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return None
        
    def stop(self):
        """Корректная остановка"""
        self._stop_event.set()
        if self._capture_thread:
            self._capture_thread.join(timeout=1.0)
        self.picam2.stop()

    @staticmethod
    def _is_valid_frame(frame):
        """Проверка кадра на валидность"""
        return (
            isinstance(frame, np.ndarray) and
            frame.size > 0 and
            np.mean(frame) > 10  # Проверка на чёрный кадр
        )