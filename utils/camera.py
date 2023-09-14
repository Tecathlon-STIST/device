import time
import picamera
import os

# Directory to store captured images
image_directory = '/home/pi/Desktop/'

# Maximum number of images to keep
max_images = 50

# Create a PiCamera object
with picamera.PiCamera() as camera:
    camera.resolution = (640, 480)
    camera.start_preview()

    try:
        while True:
            # Capture an image
            timestamp = time.strftime("%Y%m%d%H%M%S")
            image_path = os.path.join(image_directory, f'image_{timestamp}.jpg')
            camera.capture(image_path)

            # Process the captured image here
            # You can use OpenCV or other libraries for image processing

            # Delete old images if the maximum count is exceeded
            image_files = os.listdir(image_directory)
            if len(image_files) > max_images:
                oldest_image = min(image_files, key=lambda x: os.path.getctime(os.path.join(image_directory, x)))
                os.remove(os.path.join(image_directory, oldest_image))

            # Sleep for 200ms
            time.sleep(0.2)

    except KeyboardInterrupt:
        pass

    camera.stop_preview()
