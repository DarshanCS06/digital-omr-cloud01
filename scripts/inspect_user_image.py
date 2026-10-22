import cv2

img_path = r"C:/Users/rahul/.gemini/antigravity/brain/f9891136-5e91-4fcb-baf2-cf8007c6bf8c/.user_uploaded/media_1792586422683_60e028f8.jpg"
img = cv2.imread(img_path)
h, w = img.shape[:2]
print(f"Image dimensions: width={w}, height={h}, aspect ratio={h/w:.4f} (A4 standard is ~1.414)")
