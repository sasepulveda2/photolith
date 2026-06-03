import re

with open('mixins/file_management_mixin.py', 'r', encoding='utf-8') as f:
    content = f.read()

new_method = '''
    def _load_image_as_numpy(self, file_path):
        import numpy as np
        if file_path.lower().endswith('.svg'):
            from PyQt5.QtSvg import QSvgRenderer
            from PyQt5.QtGui import QPainter, QImage
            
            renderer = QSvgRenderer(file_path)
            default_size = renderer.defaultSize()
            width = default_size.width()
            height = default_size.height()
            
            if width <= 0 or height <= 0:
                width = 1024
                height = 1024
            
            # Scale up small SVGs to prevent pixelation loss
            if width < 512 and height < 512:
                scale = 512 / max(width, height)
                width = int(width * scale)
                height = int(height * scale)
                
            image = QImage(width, height, QImage.Format_ARGB32)
            image.fill(0xFFFFFFFF)  # Fill white
            
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            
            image = image.convertToFormat(QImage.Format_Grayscale8)
            ptr = image.bits()
            ptr.setsize(image.height() * image.width())
            arr = np.array(ptr).reshape(image.height(), image.width())
            return arr.copy() / 255.0
        else:
            import cv2
            img = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)
            if img is None: return None
            return img / 255.0
'''

# insert new method after save_grid_config
content = content.replace('def dragEnterEvent', new_method + '\n\n    def dragEnterEvent')

# 2. Update dropEvent
content = content.replace('.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff")):', '.endswith((".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".svg")):')
content = content.replace('image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)\\n                self.pattern = image / 255.0', 'self.pattern = self._load_image_as_numpy(file_path)')

# 3. Update load_pattern
content = content.replace('"Imágenes (*.png *.jpg *.bmp *.tiff)"', '"Imágenes (*.png *.jpg *.bmp *.tiff *.svg)"')
content = content.replace('image = cv2.imread(file_path, cv2.IMREAD_GRAYSCALE)\\n            self.pattern = image / 255.0', 'self.pattern = self._load_image_as_numpy(file_path)')

# 4. Update load_from_tree
content = content.replace('(".png", ".jpg", ".bmp", ".tiff")', '(".png", ".jpg", ".bmp", ".tiff", ".svg")')
content = content.replace('image = cv2.imread(item_path, cv2.IMREAD_GRAYSCALE)\\n            self.pattern = image / 255.0', 'self.pattern = self._load_image_as_numpy(item_path)')

# 5. Update create_thumbnail
thumbnail_logic = '''
            if image_path.lower().endswith('.svg'):
                from PyQt5.QtSvg import QSvgRenderer
                from PyQt5.QtGui import QPainter, QImage, QPixmap
                from PyQt5.QtCore import Qt, QRectF
                renderer = QSvgRenderer(image_path)
                image = QImage(size, size, QImage.Format_ARGB32)
                image.fill(0x00000000)
                painter = QPainter(image)
                ds = renderer.defaultSize()
                if ds.width() > 0 and ds.height() > 0:
                    scaled = ds.scaled(size, size, Qt.KeepAspectRatio)
                    x = (size - scaled.width()) / 2
                    y = (size - scaled.height()) / 2
                    renderer.render(painter, QRectF(x, y, scaled.width(), scaled.height()))
                else:
                    renderer.render(painter)
                painter.end()
                return QPixmap.fromImage(image)
            
            img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
'''
content = content.replace('img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)', thumbnail_logic, 1)

with open('mixins/file_management_mixin.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Rewrite complete')
