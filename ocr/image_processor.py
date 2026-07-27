import cv2
import numpy as np

class ImageProcessor:
    @staticmethod
    def preprocess_image(image_bytes: bytes):
        """Preprocess image for better OCR"""
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Resize
        img = cv2.resize(img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        
        # Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        
        # Sharpen
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        
        # Denoise
        denoised = cv2.medianBlur(sharpened, 3)
        
        # Threshold
        binary = cv2.adaptiveThreshold(denoised, 255,
                                       cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
        
        # Crop top portion (where symbol and price are)
        height, width = binary.shape[:2]
        roi = binary[0:int(height*0.15), 0:width]
        
        return roi, img
