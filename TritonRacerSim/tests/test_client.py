import os
import random
import json
import time
from io import BytesIO
import base64
import logging

from PIL import Image
import numpy as np
from gym_donkeycar.core.sim_client import SDClient

from tensorflow.python.keras.models import load_model
import tensorflow as tf
from os import path
from PIL import Image
import numpy as np



###########################################

class SimpleClient(SDClient):

    def __init__(self, address, poll_socket_sleep_time=0.01):
        super().__init__(*address, poll_socket_sleep_time=poll_socket_sleep_time)
        self.last_image = None
        self.car_loaded = False
        model_path = path.abspath('car_templates/try.h5')
        self.model = load_model(model_path, compile=False)
        tf.keras.backend.set_learning_phase(0)

    def on_msg_recv(self, json_packet):
        if json_packet['msg_type'] == "need_car_config":
            self.send_config()

        if json_packet['msg_type'] == "car_loaded":
            self.car_loaded = True
        
        if json_packet['msg_type'] == "telemetry":
            imgString = json_packet["image"]
            image = Image.open(BytesIO(base64.b64decode(imgString)))
            image.save("test.png")
            self.last_image = np.asarray(image)
            # print("img:", self.last_image.shape)

            #don't have to, but to clean up the print, delete the image string.
            del json_packet["image"]

        # print("got:", json_packet)

    def send_config(self):
        '''
        send three config messages to setup car, racer, and camera
        '''
        racer_name = "Your Name"
        car_name = "Car"
        bio = "I race robots."
        country = "Neverland"

        # Racer info
        msg = {'msg_type': 'racer_info',
            'racer_name': racer_name,
            'car_name' : car_name,
            'bio' : bio,
            'country' : country }
        self.send_now(json.dumps(msg))

        
        # Car config
        # body_style = "donkey" | "bare" | "car01" choice of string
        # body_rgb  = (128, 128, 128) tuple of ints
        # car_name = "string less than 64 char"

        msg = '{ "msg_type" : "car_config", "body_style" : "car01", "body_r" : "255", "body_g" : "0", "body_b" : "255", "car_name" : "%s", "font_size" : "100" }' % (car_name)
        self.send_now(msg)

        #this sleep gives the car time to spawn. Once it's spawned, it's ready for the camera config.
        time.sleep(0.1)

        # Camera config
        # set any field to Zero to get the default camera setting.
        # this will position the camera right above the car, with max fisheye and wide fov
        # this also changes the img output to 255x255x1 ( actually 255x255x3 just all three channels have same value)
        # the offset_x moves camera left/right
        # the offset_y moves camera up/down
        # the offset_z moves camera forward/back
        # with fish_eye_x/y == 0.0 then you get no distortion
        # img_enc can be one of JPG|PNG|TGA        
        msg = '{ "msg_type" : "cam_config", "fov" : "150", "fish_eye_x" : "0.0", "fish_eye_y" : "0.0", "img_w" : "320", "img_h" : "160", "img_d" : "3", "img_enc" : "JPG", "offset_x" : "0.0", "offset_y" : "0.0", "offset_z" : "0.0", "rot_x" : "0.0" }'
        self.send_now(msg)


    def send_controls(self, steering, throttle):
        msg = { "msg_type" : "control",
                "steering" : steering.__str__(),
                "throttle" : throttle.__str__(),
                "brake" : "0.0" }
        self.send(json.dumps(msg))

        #this sleep lets the SDClient thread poll our message and send it out.
        time.sleep(self.poll_socket_sleep_sec)

    def update(self):
        # just random steering now
        # st = random.random() * 2.0 - 1.0
        # th = 0.3
        img_arr = self.last_image
        img_arr = img_arr.reshape((1,) + img_arr.shape)
        #start_time = time.time()
        steering, throttle = self.model(img_arr)
        #print(f'Prediction time: {time.time() - start_time}')
        st = steering.numpy()[0][0] * 2 - 1
        tr = throttle.numpy()[0][0] * 2 - 1
        self.send_controls(st, tr)



###########################################
## Make some clients and have them connect with the simulator

def test_clients():
    # logging.basicConfig(level=logging.DEBUG)

    # test params
    host = "127.0.0.1" # "trainmydonkey.com" for virtual racing server
    port = 9091
    num_clients = 1
    clients = []
    time_to_drive = 100.0


    # Start Clients
    for _ in range(0, num_clients):
        c = SimpleClient(address=(host, port))
        clients.append(c)

    time.sleep(1)

    # Load Scene message. Only one client needs to send the load scene.
    msg = '{ "msg_type" : "load_scene", "scene_name" : "mountain_track" }'
    clients[0].send_now(msg)


    # Send random driving controls
    start = time.time()
    do_drive = True
    while time.time() - start < time_to_drive and do_drive:
        for c in clients:
            c.update()
            if c.aborted:
                print("Client socket problem, stopping driving.")
                do_drive = False

    time.sleep(3.0)

    # Exit Scene - optionally..
    # msg = '{ "msg_type" : "exit_scene" }'
    # clients[0].send_now(msg)

    # Close down clients
    print("waiting for msg loop to stop")
    for c in clients:
        c.stop()

    print("clients to stopped")



if __name__ == "__main__":
    test_clients()