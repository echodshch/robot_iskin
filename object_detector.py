# object_detector.py
import cv2
import numpy as np

class ObjectDetector:
    def __init__(self):
        # Загрузка модели YOLO
        self.net = cv2.dnn.readNet('yolov3.weights', 'yolov3.cfg')
        
        # Получение выходных слоев
        layer_names = self.net.getLayerNames()
        unconnected_layers = self.net.getUnconnectedOutLayers()
        if unconnected_layers.ndim == 2:
            self.output_layers = [layer_names[i[0] - 1] for i in unconnected_layers]
        else:
            self.output_layers = [layer_names[i - 1] for i in unconnected_layers]
        
        # Загрузка классов COCO
        with open('coco.names', 'r') as f:
            self.classes = f.read().strip().split('\n')
    
    def detect_objects(self, frame, target_label=None, confidence_threshold=0.3):
        """Обнаружение объектов на кадре"""
        # Конвертация цветового пространства
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        height, width = frame.shape[:2]
        
        # Подготовка изображения для YOLO
        blob = cv2.dnn.blobFromImage(frame, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
        self.net.setInput(blob)
        outs = self.net.forward(self.output_layers)
        
        # Обработка результатов
        class_ids, confidences, boxes = [], [], []
        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > confidence_threshold:
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)
                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)
        
        # Применение Non-Maximum Suppression
        indexes = cv2.dnn.NMSBoxes(boxes, confidences, 0.5, 0.4)
        
        results = []
        if len(indexes) > 0:
            for i in indexes.flatten():
                label = str(self.classes[class_ids[i]])
                confidence = confidences[i]
                box = boxes[i]
                print(f"Обнаружен объект: {label} с уверенностью {confidence:.2f}")
                
                # Если задан целевой лейбл, фильтруем результаты
                if target_label is None or label == target_label:
                    x, y, w, h = box
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    cv2.putText(frame, f"{label} {confidence:.2f}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    cv2.imshow("Object", frame)
                    results.append({
                        'label': label,
                        'confidence': confidence,
                        'box': box
                    })
        
        return results