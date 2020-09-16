"""
Scripts to drive a triton racer car

Usage:
    manage.py (drive) [--model=<model>] [--js]
    manage.py (train) (--tub=<tub1,tub2,..tubn>) (--model=<model>) [--transfer=<model>]
    manage.py (generateconfig)
"""

import sys
sys.path.append('/home/haoru/Projects/Triton-Racer-Sim/')
from docopt import docopt
from os import path
from TritonRacerSim.core.car import Car
from TritonRacerSim.core.datapool import DataPool
from TritonRacerSim.utils.types import ModelType

def get_joystick_by_name(joystick_name):
    from TritonRacerSim.components.controller import JoystickType, G28DrivingWheel, PS4Joystick, XBOXJoystick
    joysitck_type = JoystickType(joystick_name)
    if joysitck_type == JoystickType.PS4:
        return PS4Joystick()
    elif joysitck_type == JoystickType.G28:
        return G28DrivingWheel()
    elif joysitck_type == JoystickType.XBOX:
        return XBOXJoystick()
    else:
        raise Exception(f'Unsupported joystick type: {joysitck_type}. Could be still under development.')

def assemble_car(cfg = {}, model_path = None):
    car = Car(loop_hz=20)

    from TritonRacerSim.components.controlmultiplexer import ControlMultiplexer
    from TritonRacerSim.components.gyminterface import GymInterface
    from TritonRacerSim.components.img_preprocessing import ImgPreprocessing
    from TritonRacerSim.components.datastorage import  DataStorage
    from TritonRacerSim.components.track_data_process import LocationTracker

    # Autopilot
    if model_path is not None:
        from TritonRacerSim.components.keras_pilot import KerasPilot
        pilot = KerasPilot(cfg, model_path, ModelType(cfg['model_type']))
        if cfg['preprocessing_enabled']:
            pilot.step_inputs[0] = 'cam/processed_img'
        car.addComponent(pilot)

    # Joystick
    joystick = get_joystick_by_name(cfg['joystick_type'])
    car.addComponent(joystick)

    # Control Signal Multiplexer
    mux = ControlMultiplexer(cfg)
    car.addComponent(mux)

    # Interface with donkeygym
    gym = GymInterface(poll_socket_sleep_time=0.01,gym_config=cfg)
    car.addComponent(gym)

    #Image preprocessing
    if cfg['preprocessing_enabled']:
        preprocessing = ImgPreprocessing(cfg)
        car.addComponent(preprocessing)

    # Location tracker (for mountain track)
    if cfg['use_location_tracker']:
        tracker = LocationTracker(track_data_path=cfg['track_data_file'])
        car.addComponent(tracker)

    # Data storage
    storage = DataStorage()
    if cfg['preprocessing_enabled']:
        storage.step_inputs[0] = 'cam/processed_img'
    car.addComponent(storage)

    return car

if __name__ == '__main__':
    args = docopt(__doc__)
    if args['generateconfig']:
        from TritonRacerSim.core.config import generate_config
        generate_config('./myconfig.json')

    else:
        from TritonRacerSim.core.config import read_config
        cfg = read_config(path.abspath('./myconfig.json'))

        if args['drive']:
            
            model_path =None
            if args['--model']:
                model_path = path.abspath(args['--model'])
                assemble_car(cfg, model_path).start()
            else:
                assemble_car(cfg).start()

        elif args['train']:
            tub = args['--tub']
            data_paths = []
            for folder_path in tub.split(','):
                data_paths.append(path.abspath(folder_path))

            model_path = path.abspath(args['--model'])
            # assert path.exists(model_path)

            from TritonRacerSim.components.keras_train import train
            transfer_path=None
            if (args['--transfer']):
                transfer_path = args['--transfer']
            train(cfg, data_paths, model_path, transfer_path)
