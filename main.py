import asyncio, picamera, websockets, requests, json, obd, urllib, serial, os, time, threading
import RPi.GPIO as GPIO
from utils import auth, configs, vehicle, gps, qr, ai
from datetime import datetime, timedelta

connection = obd.OBD('/dev/ttyUSB0')
GPIO.setmode(GPIO.BCM)
button_pin = configs.BUTTON
GPIO.setup(button_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
image_directory = '/home/pi/Pictures/'
max_images = 50

# instantiate the model with the saved image in predict mode
model = ai.PilotNet(640, 480, predict=True)
trained_model = 'sample.h5'

def power_check():
    while True:
        if GPIO.input(button_pin) == GPIO.LOW:
            GPIO.cleanup()
            os.system("sudo shutdown -h now")
        
def register():
    company = input("Enter the brand/make of this car >> ")
    model = input("Enter the model/name of this car >> ")
    payload = {
        "company": company,
        "model": model
    }

    print("\nRegistering. Please wait...\n")
    response = requests.post(f'{configs.PROTOCOLS.get("https")}{configs.SERVER_URL}/vehicle/register', data=json.dumps(payload))
    creds = json.loads(response.content)["id"]["$oid"]
    print("\nRegistration successful! Your one time use pairing code is displayed below...\n")
    qr.print_qr(json.dumps({
        'vid': creds,
        'initial': False
    }))
    print("\nOpen the mobile app & scan this QR code to pair. This is a one time use code. If you want to share this vehicle, use the share option in the app instead.")
    auth.set_creds(creds)

def get_message(message, vid, mode='broadcast', conn_id="", status="success", attachments=[]):
        # Create message in standard format
        return {
            "mode": mode,
            "vid": vid,
            "conn_id": conn_id,
            "status": status,
            "message": message,
            "attachments": attachments
        }

async def send_messages():

    vehicle_id = auth.get_creds()
    uri = f'{configs.PROTOCOLS.get("wss")}{configs.SERVER_URL}/join/vehicle/{vehicle_id}'
    print('Trying to connect...')

    async with picamera.PiCamera() as camera:
        camera.resolution = (640, 480)
        camera.start_preview()
        async with websockets.connect(uri) as websocket:
            print(f'{datetime.now().strftime("%H:%M:%S")}: Connected to server!')
            while True:
                timestamp = time.strftime("%Y%m%d%H%M%S")
                image_path = os.path.join(image_directory, f'image_{timestamp}.jpg')
                camera.capture(image_path)
                # capture the prediction for this scene
                (steering, brake, throttle) = model.predict(image_path, given_model=trained_model)

                # the main job of get_stats() is to just get the current stats of the vehicle
                # however, each time it takes the stats, it immediately also analyses the brake position
                # and compares it with the predicted value to warn the driver
                stats = vehicle.get_stats(connection, brake)
                await websocket.send(json.dumps(get_message(stats, vehicle_id)))
                await asyncio.sleep(0.2)

                # delete images without letting the storage fill up
                image_files = os.listdir(image_directory)
                if len(image_files) > max_images:
                    oldest_image = min(image_files, key=lambda x: os.path.getctime(os.path.join(image_directory, x)))
                    os.remove(os.path.join(image_directory, oldest_image))

if not auth.is_authenticated():
    print("\nHey there, first of all, thanks for deciding to give alpaDrive a try! And yeah congrats on building your device!\nBefore we go any further, set up this device for your car by entering some basic identification details.\n")
    try:
        print("\n\nPress Ctrl + C if you wanna to do this later.")
        register()
    except KeyboardInterrupt:
        print("Okay, we'll do this later. But remember not to enable 'alpadrive.service' before running this once more!")
    quit()

button_thread = threading.Thread(target=power_check, daemon=True)
button_thread.start()
# wait 2 minutes for GPS fix
end_time = datetime.now() + timedelta(minutes=2)
print(f'{datetime.now().strftime("%H:%M:%S")}: Wating for GPS signal...')
while datetime.now() < end_time :
    if gps.has_fix():
        print(f'{datetime.now().strftime("%H:%M:%S")}: Got GPS fix!')
        break

if not gps.has_fix():
    print(f'{datetime.now().strftime("%H:%M:%S")}: GPS signal unavailable at the moment. Starting up system...')

while True:
    try:
        asyncio.run(send_messages())
    except KeyboardInterrupt:
        quit()
    except:
        print(f'{datetime.now().strftime("%H:%M:%S")}: Lost connection with server...')
