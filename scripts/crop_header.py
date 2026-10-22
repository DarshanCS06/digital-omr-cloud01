import cv2

img_path = r"C:/Users/rahul/.gemini/antigravity/brain/f9891136-5e91-4fcb-baf2-cf8007c6bf8c/.user_uploaded/media_1792586422683_60e028f8.jpg"
img = cv2.imread(img_path)
h, w = img.shape[:2]

# Crop header banner (y: 35 to 175)
header_crop = img[35:175, 20:w-20]
cv2.imwrite(r"C:\Users\rahul\.gemini\antigravity\scratch\digital-omr-cloud\generated\vidyakashi_header.png", header_crop)
print("Saved header banner crop.")
