from __future__ import division

import json
import struct
import subprocess
import threading
from datetime import datetime
from uuid import getnode
import socket
from time import sleep

import math
import requests
from bluepy.btle import *
from requests.exceptions import ConnectionError, ReadTimeout

REST_WRITE_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

LOGIN_INFO = {
    'login_id': 'nordic',
    'password': 'Samplepw1',
    'api_key': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
}

ENDPOINT = 'https://api-sandbox.mediumone.com'
DEVICE_ADDR = 'ab:cd:ef:gh:ij:kl'
INTERVAL_SECONDS = 10
SLEEP_ON_RESET = 5
DEBUG = False
FIRMWARE_VERSION = '032618a'

BATT_SERVICE = '180F'

HEART_RATE_CHAR = '2A37'
BODY_SENSOR_LOCATION_CHAR = '2A38'
BATTERY_CHAR = "2a19"



ENVIRONMENT_SERVICE = "EF680200-9B35-4933-9B10-52FFA9740042"
MOTION_SERVICE      = "ef680400-9b35-4933-9b10-52ffa9740042"


TEMPERATURE_CHAR    = "EF680201-9B35-4933-9B10-52FFA9740042"
PRESSURE_CHAR       = "EF680202-9B35-4933-9B10-52FFA9740042"
HUMIDITY_CHAR       = "EF680203-9B35-4933-9B10-52FFA9740042"
AIR_QUALITY_CHAR    = "EF680204-9B35-4933-9B10-52FFA9740042"
LIGHT_CHAR          = "EF680205-9B35-4933-9B10-52FFA9740042"

TAP_SENSOR_CHAR          = 'ef680402-9b35-4933-9b10-52ffa9740042'
ORIENTATION_CHAR         = 'ef680403-9b35-4933-9b10-52ffa9740042' #landscape, potrait, etc
PEDOMETER_CHAR           = 'ef680405-9b35-4933-9b10-52ffa9740042'
HEADING_CHAR             = 'ef680409-9b35-4933-9b10-52ffa9740042' # compass
GRAVITY_VECTOR_CHAR      = 'ef68040a-9b35-4933-9b10-52ffa9740042'
EULER_CHAR               = 'ef680407-9b35-4933-9b10-52ffa9740042'
QUATERNION_CHAR          = 'ef680404-9b35-4933-9b10-52ffa9740042'


ORIENT_MAP = {
     0 : 'Portrait',
     1 : 'Landscape',
     2 : 'Reverse Portrait',
     3 : 'Reverse Landscape'
}

TAP_DIRECTION_MAP = {
    1:'X UP',
    2:'X DOWN',
    3:'Y UP',
    4:'Y DOWN',
    5:'Z UP',
    6:'Z DOWN'
}


class EnvDelegate(DefaultDelegate):
    def __init__(self, session, tempGatt, pressureGatt, humGatt, airGatt, lightGatt, tapGatt,
                 orientGatt, pedometerGatt, headingGatt, gravityGatt, eulerGatt, quatGatt):
        DefaultDelegate.__init__(self)
        self.session = session
        self.tempGatt = tempGatt
        self.pressureGatt = pressureGatt
        self.humGatt = humGatt
        self.airGatt = airGatt
        self.lightGatt = lightGatt
        self.tapGatt = tapGatt
        self.orientGatt = orientGatt
        self.pedometerGatt = pedometerGatt
        self.headingGatt = headingGatt
        self.gravityGatt = gravityGatt
        self.eulerGatt = eulerGatt
        self.quatGatt = quatGatt
        self.lock = threading.Lock()
        self.current_data = {}
        self.last_data_sent = datetime.utcnow()

    def set_battery(self, value):
        with self.lock:
            self.current_data['battery'] = value

    def handleNotification(self, cHandle, data):
        if cHandle == self.tempGatt and type(data) == str:
            temp_data_value = ord(data[0]) + (ord(data[1]) / 100.)
            with self.lock:
                self.current_data['temperature'] = temp_data_value
        if cHandle == self.pressureGatt and type(data) == str:
            pressure_data_value = (ord(data[3]) << 24 ) + (ord(data[2]) << 16 ) + (ord(data[1]) << 8 )  + ord(data[0]) + (ord(data[4]) / 100. )
            with self.lock:
                self.current_data['pressure'] = pressure_data_value
            # print("presure: {}".format(pressure_data_value))
        if cHandle == self.humGatt and type(data) == str:
            hum_data_value = ord(data[0])
            with self.lock:
                self.current_data['humidity'] = hum_data_value
        if cHandle == self.airGatt and type(data) == str:
            air_data_value = ord(data[0]) + (ord(data[1]) << 8)
            voc_value = ord(data[2]) + (ord(data[3]) << 8)
            with self.lock:
                self.current_data['co2'] = air_data_value
                self.current_data['voc'] = voc_value
        if cHandle == self.lightGatt:
            r = struct.unpack('H', data[:2])[0]
            g = struct.unpack('H', data[2:4])[0]
            b = struct.unpack('H', data[4:6])[0]
            c = struct.unpack('H', data[6:])[0]
            rRatio =  r / (r + b + g)
            gRatio =  g / (r + b + g)
            bRatio =  b / (r + b + g)

            clear_at_black = 300
            clear_at_white = 400
            clear_diff = clear_at_white - clear_at_black
            clear_normalized = (c - clear_at_black) / clear_diff

            if clear_normalized < 0:
                clear_normalized = 0
            red = rRatio * 255.0 * 3 * clear_normalized
            if red > 255:
                red = 255
            green = gRatio * 255.0 * 3 * clear_normalized
            if green > 255:
                green = 255
            blue = bRatio * 255.0 * 3 * clear_normalized
            if blue > 255:
                blue = 255
            color = "rgb({},{},{})".format(int(red), int(green), int(blue))
            with self.lock:
                self.current_data['color'] = color
        if cHandle == self.tapGatt:
            if ord(data[0]) in TAP_DIRECTION_MAP:
                tap_direction = TAP_DIRECTION_MAP[ord(data[0])]
            else:
                tap_direction = "Unknown"
            tap_count = ord(data[1])
            with self.lock:
                if 'tap_direction' in self.current_data:
                    self.current_data['tap_direction'].append(tap_direction)
                else:
                    self.current_data['tap_direction'] = [tap_direction]
                if 'tap_count' in self.current_data:
                    self.current_data['tap_count'].append(tap_count)
                else:
                    self.current_data['tap_count'] = [tap_count]
        if cHandle == self.orientGatt:
            if ord(data[0]) in ORIENT_MAP:
                orient_data = ORIENT_MAP[ord(data[0])]
                with self.lock:
                    if 'orient_data' in self.current_data:
                        self.current_data['orient_data'].append(orient_data)
                    else:
                        self.current_data['orient_data'] = [orient_data]
        if cHandle == self.pedometerGatt:
            steps = struct.unpack('I', data[:4])[0]
            time = struct.unpack('I', data[4:8])[0]
            with self.lock:
                self.current_data['steps_taken'] = steps
                self.current_data['time_walking'] = time
        if cHandle == self.headingGatt:
            heading_data_value = float((ord(data[3]) << 24) + (ord(data[2]) << 16) + (ord(data[1]) << 8) + ord(data[0]))/65536
            with self.lock:
                self.current_data['compass_direction'] = heading_data_value
        if cHandle == self.gravityGatt:
            x_data_value = struct.unpack('f', data[:4])[0]
            y_data_value = struct.unpack('f', data[4:8])[0]
            z_data_value = struct.unpack('f', data[8:])[0]
            with self.lock:
                self.current_data['x_gravity'] = x_data_value
                self.current_data['y_gravity'] = y_data_value
                self.current_data['z_gravity'] = z_data_value
        if cHandle == self.eulerGatt:
            roll = float(struct.unpack('i', data[:4])[0]) / 65536.
            pitch = float(struct.unpack('i', data[4:8])[0]) / 65536.
            yaw = float(struct.unpack('i', data[8:])[0]) / 65536.
            with self.lock:
                self.current_data['roll'] = roll
                self.current_data['pitch'] = pitch
                self.current_data['yaw'] = yaw
        if cHandle == self.quatGatt:
            w = float(struct.unpack('i', data[:4])[0]) / (1 << 30)
            x = float(struct.unpack('i', data[4:8])[0])/ (1 << 30)
            y = float(struct.unpack('i', data[8:12])[0])/ (1 << 30)
            z = float(struct.unpack('i', data[12:])[0]) / (1 << 30)

            magnitude = math.sqrt(math.pow(w,2) + math.pow(x,2) + math.pow(y,2) + math.pow(z,2))

            if magnitude != 0:
                w /= magnitude
                x /= magnitude
                y /= magnitude
                z /= magnitude
            with self.lock:
                self.current_data['w_quaternion'] = w
                self.current_data['x_quaternion'] = x
                self.current_data['y_quaternion'] = y
                self.current_data['z_quaternion'] = z
        with self.lock:
            if (datetime.utcnow() - self.last_data_sent).total_seconds() > INTERVAL_SECONDS:
                try:
                    create_event(self.session, 'sensor_data', self.current_data)
                except ConnectionError as ce:
                    print("Connection error, resetting session: {}\n".format(ce.message))
                    if self.debug:
                        self.debug.write("Connection error, resetting session: {}\n".format(ce.message))
                        self.debug.flush()
                    self.session.close()
                    self.session = requests.session()
                    sleep(SLEEP_ON_RESET)
                except ReadTimeout as re:
                    print("Internet connection lost during read, resetting session: {}\n".format(re.message))
                    if self.debug:
                        self.debug.write("Internet connection lost during read, resetting session: {}\n".format(re.message))
                        self.debug.flush()
                    self.session.close()
                    self.session = requests.session()
                    sleep(SLEEP_ON_RESET)
                self.last_data_sent = datetime.utcnow()
                self.current_data = {}



def run(ble, debug=None):
    """
    Once connected to the nordic board, tries to connect to Medium One through the internet. If it cannot connect,
    it will maintain the connection with the nordic board and keep trying to connect to the cloud until it is successful.
    After that, it collects the data and sends it to the cloud as long as the connection is maintained
    :param ble:
    :param debug:
    :return:
    """
    session = requests.session()
    while True: # Keep trying to send init event until you can connect
        try:
            send_initialization_event(session)
            break
        except ConnectionError as ce:
            print("Connection error, resetting session: {}\n".format(ce.message))
            if debug:
                debug.write("Connection error, resetting session: {}\n".format(ce.message))
                debug.flush()
            session.close()
            session = requests.session()
            sleep(INTERVAL_SECONDS)
        except ReadTimeout as re:
            print("Internet connection lost during read, resetting session: {}\n".format(re.message))
            if debug:
                debug.write("Internet connection lost during read, resetting session: {}\n".format(re.message))
                debug.flush()
            session.close()
            session = requests.session()
            sleep(SLEEP_ON_RESET)
    envService = ble.getServiceByUUID(ENVIRONMENT_SERVICE)
    battService = ble.getServiceByUUID(BATT_SERVICE)
    motionService = ble.getServiceByUUID(MOTION_SERVICE)

    temp_chars = envService.getCharacteristics(forUUID=TEMPERATURE_CHAR)
    pressure_chars = envService.getCharacteristics(forUUID=PRESSURE_CHAR)
    hum_chars = envService.getCharacteristics(forUUID=HUMIDITY_CHAR)
    air_chars = envService.getCharacteristics(forUUID=AIR_QUALITY_CHAR)
    light_chars = envService.getCharacteristics(forUUID=LIGHT_CHAR)

    bat_chars = battService.getCharacteristics(forUUID=BATTERY_CHAR)

    tap_chars = motionService.getCharacteristics(forUUID=TAP_SENSOR_CHAR)
    orient_chars = motionService.getCharacteristics(forUUID=ORIENTATION_CHAR)
    pedometer_chars = motionService.getCharacteristics(forUUID=PEDOMETER_CHAR)
    heading_chars = motionService.getCharacteristics(forUUID=HEADING_CHAR)
    gravity_chars = motionService.getCharacteristics(forUUID=GRAVITY_VECTOR_CHAR)
    euler_chars = motionService.getCharacteristics(forUUID=EULER_CHAR)
    quaternion_chars = motionService.getCharacteristics(forUUID=QUATERNION_CHAR)

    delegate = EnvDelegate(requests.session(), temp_chars[0].getHandle(), pressure_chars[0].getHandle(),
                                hum_chars[0].getHandle(), air_chars[0].getHandle(), light_chars[0].getHandle(),
                                tap_chars[0].getHandle(), orient_chars[0].getHandle(), pedometer_chars[0].getHandle(),
                                heading_chars[0].getHandle(), gravity_chars[0].getHandle(), euler_chars[0].getHandle(),
                                quaternion_chars[0].getHandle())
    ble.setDelegate(delegate)

    for temp_char in temp_chars:
        if 'NOTIFY' in temp_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = temp_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for pressure_char in pressure_chars:
        if 'NOTIFY' in pressure_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = pressure_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for hum_char in hum_chars:
        if 'NOTIFY' in hum_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = hum_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for air_char in air_chars:
        if 'NOTIFY' in air_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = air_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for light_char in light_chars:
        if 'NOTIFY' in light_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = light_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for tap_char in tap_chars:
        if 'NOTIFY' in tap_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = tap_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for orient_char in orient_chars:
        if 'NOTIFY' in orient_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = orient_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for pedometer_char in pedometer_chars:
        if 'NOTIFY' in pedometer_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = pedometer_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for heading_char in heading_chars:
        if 'NOTIFY' in heading_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = heading_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for gravity_char in gravity_chars:
        if 'NOTIFY' in gravity_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = gravity_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for euler_char in euler_chars:
        if 'NOTIFY' in euler_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = euler_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)

    for quaternion_char in quaternion_chars:
        if 'NOTIFY' in quaternion_char.propertiesToString():
            setup_data = b"\x01\x00"
            notify_handle = quaternion_char.getHandle() + 1
            ble.writeCharacteristic(notify_handle, setup_data, withResponse=True)
    current_battery = None
    while True:
        for bat_char in bat_chars:
            if bat_char.supportsRead():
                bat_data = bat_char.read()
                if type(bat_data) == str:
                    bat_data_value = ord(bat_data[0])
                    if bat_data_value != current_battery:
                        current_battery = bat_data_value
                        delegate.set_battery(current_battery) # Only change the battery value if it is new
        sleep(.01)


def login(session, login_id, user_pass, api_key, debug = None):
    """
    Logs in to the sandbox as the user passed in
    :param session: Requests session to log in from
    :param login_id: API user to log in as
    :param user_pass: Password
    :param api_key: API key
    :param debug: Optional file to write to if you are in debug mode
    :return: nothing
    """
    user_dict = {
        "login_id": login_id,
        "password": user_pass,
        "api_key": api_key
    }
    if debug:
        debug.write("{}: Logging in. login ID {}, api key {}\n".format(datetime.utcnow(), login_id, api_key))

    session.post('{}/v2/login'.format(ENDPOINT), data=json.dumps(user_dict),
                 headers=REST_WRITE_HEADERS, timeout=30)


def create_event(session, stream, data, add_ip=False, debug = None):
    """
    Sends an event to the sandbox
    :param session: Requests session to post to
    :param stream: Stream to send the data to
    :param data: JSON data
    :param add_ip: String of an IP address. If included, is sent along with the data
    :param debug: Optional file to write to if you are in debug mode
    :return: nothing
    """
    all_data = {"event_data": data}
    if add_ip:
        all_data['add_client_ip'] = add_ip

    data = json.dumps(all_data)
    if debug:
        debug.write("{}: Sending event. data: {}".format(datetime.utcnow(), data))
    response = session.post('{}/v2/events/{}/'.format(ENDPOINT, stream) + LOGIN_INFO['login_id'], data=data,
                            headers=REST_WRITE_HEADERS, timeout = 30)
    if response.status_code != 200:
        login(session, LOGIN_INFO['login_id'], LOGIN_INFO['password'], LOGIN_INFO['api_key'])
        if debug:
            debug.write("{}: Sending event after logging in. data: {}".format(datetime.utcnow(), data))
        response = session.post('{}/v2/events/{}/'.format(ENDPOINT, stream) + LOGIN_INFO['login_id'], data=data,
                                headers=REST_WRITE_HEADERS, timeout = 30)
        if response.status_code != 200:
            print(response.content)
            if debug:
                debug.write("{}: Problem posting to cloud. response: {}".format(datetime.utcnow(), response.content))
            raise ConnectionError("Could not send to cloud, restarting\n")


def twos_comp(val, bits):
    if (val & (1 << (bits - 1))) != 0:
        val -= 1 << bits
    return val


def get_lan_addr():
    """
    This gets the LAN address from ifconfig on a raspberry pi running full rasbian
    :return: String lap address if exists, else None
    """
    p1 = subprocess.Popen("/sbin/ifconfig", stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["grep", "inet addr:"], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(["grep", "-v", "127.0.0.1"], stdin=p2.stdout, stdout=subprocess.PIPE)
    p1.stdout.close()
    p2.stdout.close()
    result = p3.communicate()[0]
    p1.wait()
    p2.wait()
    split = result.split('inet addr:')
    if len(split) >=2 :
        addr = split[1].split(' ')
        if len(addr) >= 1:
            return addr[0]
    return None


def get_lan_addr_rpi_lite():
    """
    This gets the LAN address from ifconfig on a raspberry pi running rasbpian lite.
    :return: String lap address if exists, else None
    """
    p1 = subprocess.Popen("/sbin/ifconfig", stdout=subprocess.PIPE)
    p2 = subprocess.Popen(["grep", "inet"], stdin=p1.stdout, stdout=subprocess.PIPE)
    p3 = subprocess.Popen(["grep", "-v", "127.0.0.1"], stdin=p2.stdout, stdout=subprocess.PIPE)
    p4 = subprocess.Popen(["grep", "-v", "inet6"], stdin=p3.stdout, stdout=subprocess.PIPE)
    p1.stdout.close()
    p2.stdout.close()
    p3.stdout.close()
    result = p4.communicate()[0]
    p1.wait()
    p2.wait()
    p3.wait()
    split = result.split('inet ')
    if len(split) >=2 :
        addr = split[1].split(' ')
        if len(addr) >= 1:
            return addr[0]
    return None


def send_initialization_event(session):
    """
    Sends the initialization event to Medium One once the pi has paired with the thundersense.
    :param session:
    :return:
    """
    print(socket.gethostname())
    lan = get_lan_addr()
    if not lan:
        lan = get_lan_addr_rpi_lite()
    initial_event = {
        'connected' : True,
        'lan_ip_address' : lan,
        'mac_address' : getnode(),
        'firmware_version' : FIRMWARE_VERSION,
        'device_id' : DEVICE_ADDR,
    }
    print(initial_event)
    create_event(session, 'device_data', initial_event, add_ip= True)

while True:
    f = open('/m1/debug.txt', 'a') if DEBUG else None
    with open('/m1/login.txt', 'r') as config:
        login_info = config.read().splitlines()
        if len(login_info) >= 2:
            LOGIN_INFO['login_id'] = login_info[0]
            LOGIN_INFO['password'] = login_info[1]
            LOGIN_INFO['api_key'] = login_info[2]
            DEVICE_ADDR = login_info[3]
    ble = Peripheral()

    try:
        while True:
            try:
                ble.connect(DEVICE_ADDR, 'random')
                break
            except BTLEException as be:
                print("Could not connect to device : " + be.message)
                if DEBUG:
                    f.write("{}: Could not connect to device : {}\n".format(datetime.utcnow(), be.message))
                    f.flush()
                sleep(SLEEP_ON_RESET)
        run(ble, debug=f)
    except BTLEException as be:
        print("BTLE Exception: {}. Reconnecting to the board".format(be.message))
        try:
            ble.disconnect()
        except BTLEException as be2:
            print("{}: BTLE exception while disconnecting: {}. Continuing...".format(datetime.utcnow(), be2.message))
        if DEBUG:
            f.write("{}: BTLE Exception: {}. Reconnecting to the board\n".format(datetime.utcnow(), be.message))
            f.flush()
            f.close()
        sleep(SLEEP_ON_RESET)
    except Exception as e:
        err_type = type(e).__name__
        print("Unexpected error of type {}: {}".format(err_type, e.message))
        try:
            ble.disconnect()
        except BTLEException as be2:
            print("{}: BTLE exception while disconnecting after unexepcted error: {}. Continuing...".format(datetime.utcnow(), be2.message))
        if DEBUG:
            f.write("{}: Unexpected error of type {}: {}\n".format(datetime.utcnow(), err_type, e.message))
            f.flush()
            f.close()
        sleep(SLEEP_ON_RESET)
