#!/usr/bin/env python3
# set up wheel
import array
import os
import struct
from fcntl import ioctl
from typing import NoReturn

# Iterate over the joystick devices.
print('Available devices:')
for fn in os.listdir('/dev/input'):
  if fn.startswith('js'):
    print(f'  /dev/input/{fn}')

# We'll store the states here.
axis_states = {}
button_states = {}

# These constants were borrowed from linux/input.h
axis_names = {
  0x00 : 'x', # Logitech Extreme 3D pro
  0x01 : 'y', # Logitech Extreme 3D pro
  0x02 : 'z',
  0x03 : 'rx',
  0x04 : 'ry',
  0x05 : 'rz', # Logitech Extreme 3D pro
  0x06 : 'throttle', # Logitech Extreme 3D pro
  0x07 : 'rudder',
  0x08 : 'wheel',
  0x09 : 'gas',
  0x0a : 'brake',
  0x10 : 'hat0x', # Logitech Extreme 3D pro
  0x11 : 'hat0y', # Logitech Extreme 3D pro
  0x12 : 'hat1x',
  0x13 : 'hat1y',
  0x14 : 'hat2x',
  0x15 : 'hat2y',
  0x16 : 'hat3x',
  0x17 : 'hat3y',
  0x18 : 'pressure',
  0x19 : 'distance',
  0x1a : 'tilt_x',
  0x1b : 'tilt_y',
  0x1c : 'tool_width',
  0x20 : 'volume',
  0x28 : 'misc',
}

button_names = {
  0x120 : 'trigger', # Logitech Extreme 3D pro
  0x121 : 'thumb', # Logitech Extreme 3D pro
  0x122 : 'thumb2', # Logitech Extreme 3D pro
  0x123 : 'top', # Logitech Extreme 3D pro
  0x124 : 'top2', # Logitech Extreme 3D pro
  0x125 : 'pinkie', # Logitech Extreme 3D pro
  0x126 : 'base', # Logitech Extreme 3D pro
  0x127 : 'base2', # Logitech Extreme 3D pro
  0x128 : 'base3', # Logitech Extreme 3D pro
  0x129 : 'base4', # Logitech Extreme 3D pro
  0x12a : 'base5', # Logitech Extreme 3D pro
  0x12b : 'base6', # Logitech Extreme 3D pro
  0x12f : 'dead',
  0x130 : 'a',
  0x131 : 'b',
  0x132 : 'c',
  0x133 : 'x',
  0x134 : 'y',
  0x135 : 'z',
  0x136 : 'tl',
  0x137 : 'tr',
  0x138 : 'tl2',
  0x139 : 'tr2',
  0x13a : 'select',
  0x13b : 'start',
  0x13c : 'mode',
  0x13d : 'thumbl',
  0x13e : 'thumbr',

  0x220 : 'dpad_up',
  0x221 : 'dpad_down',
  0x222 : 'dpad_left',
  0x223 : 'dpad_right',

  # XBox 360 controller uses these codes.
  0x2c0 : 'dpad_left',
  0x2c1 : 'dpad_right',
  0x2c2 : 'dpad_up',
  0x2c3 : 'dpad_down',
}

axis_map = []
button_map = []

def wheel_poll_thread(q: 'Queue[str]') -> NoReturn:
  # Open the joystick device.
  fn = '/dev/input/js0'
  print(f'Opening {fn}...')
  jsdev = open(fn, 'rb')

  # Get the device name.
  #buf = bytearray(63)
  buf = array.array('B', [0] * 64)
  ioctl(jsdev, 0x80006a13 + (0x10000 * len(buf)), buf)  # JSIOCGNAME(len)
  js_name = buf.tobytes().rstrip(b'\x00').decode('utf-8')
  print(f'Device name: {js_name}')

  # Get number of axes and buttons.
  buf = array.array('B', [0])
  ioctl(jsdev, 0x80016a11, buf)  # JSIOCGAXES
  num_axes = buf[0]

  buf = array.array('B', [0])
  ioctl(jsdev, 0x80016a12, buf)  # JSIOCGBUTTONS
  num_buttons = buf[0]

  # Get the axis map.
  buf = array.array('B', [0] * 0x40)
  ioctl(jsdev, 0x80406a32, buf)  # JSIOCGAXMAP

  for _axis in buf[:num_axes]:
    axis_name = axis_names.get(_axis, f'unknown(0x{_axis:02x})')
    axis_map.append(axis_name)
    axis_states[axis_name] = 0.0

  # Get the button map.
  buf = array.array('H', [0] * 200)
  ioctl(jsdev, 0x80406a34, buf)  # JSIOCGBTNMAP

  for btn in buf[:num_buttons]:
    btn_name = button_names.get(btn, f'unknown(0x{btn:03x})')
    button_map.append(btn_name)
    button_states[btn_name] = 0

  print('%d axes found: %s' % (num_axes, ', '.join(axis_map)))
  print('%d buttons found: %s' % (num_buttons, ', '.join(button_map)))

  # Enable FF
  import evdev
  from evdev import ecodes, InputDevice
  device = evdev.list_devices()[0]
  evtdev = InputDevice(device)
  val = 24000
  evtdev.write(ecodes.EV_FF, ecodes.FF_AUTOCENTER, val)
#  print("queue size %d" % q.qsize())
  
  while True:
#    print("queue size %d" % q.qsize())
    evbuf = jsdev.read(8)
    value, mtype, number = struct.unpack('4xhBB', evbuf)
    # print(mtype, number, value)
    if mtype & 0x02:  # wheel & paddles
      axis = axis_map[number]
      #Set vehicle control according to https://carla.readthedocs.io/en/latest/python_api/#instance-variables_73
      if axis == "y":  # throttle
        if value < 0:
            fvalue = 30.0
            if q.qsize() < 5:
              q.put(f"throttle_{fvalue:f}")

      if axis == "x":  # steer angle
        fvalue = 0.0
        if value < -1:
          fvalue = 0.07
        if value > 1:
          fvalue = -0.07
        if q.qsize() < 5:
            q.put(f"steer_{fvalue:f}")        

#        if value < -1.: #left
#            q.put(f"steer_{fvalue:f}")
#        elif value > +1: #right
#            q.put(f"steer_{fvalue:f}")

        #axis_states[axis] = fvalue
        #normalized = fvalue
        #q.put(f"steer_{normalized:f}")

      if axis == "throttle":
        if value > 0:
            fvalue = 10.0
            if q.qsize() < 5:
              q.put(f"brake_{fvalue:f}")
	

    elif mtype & 0x01:  # buttons
      if value == 1: # press down
        if number in [0, 1]: #[0, 19]:  # trigger
          #fvalue = 1.0
          #q.put(f"throttle_{fvalue:f}")
          #print("throttle button %d" % number)
          q.put("brake_%f" % 1.0)
          print("brake button %d" % number)
          
        elif number in [2]: #[0, 19]:  # X
          q.put("cruise_down")

        elif number in [4]: #[3, 18]:  # triangle
          q.put("cruise_up")

        elif number in [5]: #[1, 6]:  # square
          q.put("cruise_cancel")

        elif number in [6]: #[10, 21]:  # R3
          q.put("reverse_switch")
         
        else:
            print("Detected unused button number: %2d" % number)

if __name__ == '__main__':
  from multiprocessing import Process, Queue
  q: Queue[str] = Queue()
  p = Process(target=wheel_poll_thread, args=(q,))
  p.start()


