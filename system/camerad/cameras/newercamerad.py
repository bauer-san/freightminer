#!/usr/bin/env python3
import os
import time
import subprocess

import numpy as np
import pyopencl as cl
import pyopencl.array as cl_array

import cereal.messaging as messaging
from cereal.visionipc.visionipc_pyx import VisionIpcServer, VisionStreamType  # pylint: disable=no-name-in-module, import-error
from common.basedir import BASEDIR
from common.realtime import Ratekeeper
from selfdrive.test.helpers import set_params_enabled

import cv2

RATE_HZ = 30

#W, H = 1928, 1208
#W, H = 640, 480
W, H =1920,1080

pm = messaging.PubMaster(['roadCameraState', 'wideRoadCameraState'])

startTime = time.time()

class Camerad:
  def __init__(self):
    self.rk = Ratekeeper(RATE_HZ, 10000)

    self.frame_id = 0
    self.vipc_server = VisionIpcServer("camerad")

    self.vipc_server.create_buffers(VisionStreamType.VISION_STREAM_ROAD, 5, False, W, H)
    self.vipc_server.create_buffers(VisionStreamType.VISION_STREAM_WIDE_ROAD, 5, False, W, H)
    self.vipc_server.start_listener()

    # set up for pyopencl rgb to yuv conversion
    self.ctx = cl.create_some_context()
    self.queue = cl.CommandQueue(self.ctx)
    cl_arg = f" -DHEIGHT={H} -DWIDTH={W} -DRGB_STRIDE={W * 3} -DUV_WIDTH={W // 2} -DUV_HEIGHT={H // 2} -DRGB_SIZE={W * H} -DCL_DEBUG "

    # TODO: move rgb_to_yuv.cl to local dir once the frame stream camera is removed
    #kernel_fn = os.path.join(BASEDIR, "selfdrive", "came1rad", "transforms", "rgb_to_yuv.cl")
    kernel_fn = os.path.join(BASEDIR, "tools/sim/rgb_to_nv12.cl")
    with open(kernel_fn) as f:
      prg = cl.Program(self.ctx, f.read()).build(cl_arg)
      self.krnl = prg.rgb_to_nv12
    self.Wdiv4 = W // 4 if (W % 4 == 0) else (W + (4 - W % 4)) // 4
    self.Hdiv4 = H // 4 if (H % 4 == 0) else (H + (4 - H % 4)) // 4

    #These parameters come from 'v4l2-ctl --all'
    cam_props = {
                 'backlight_compensation':1, #1 = turn off         
                 'sharpness':200, #nice resolution
                 'focus_automatic_continuous':0, #0 = turn off
                 'focus_absolute':5,                 
                 'auto_exposure':1, #manual mode
#                 'exposure_time_absolute':700, # ???                 
                }
    for key in cam_props:
      subprocess.call(['v4l2-ctl -d /dev/video0 -c {}={}'.format(key, str(cam_props[key]))], shell=True)

    self.camcapdevice=cv2.VideoCapture(0)
    self.camcapdevice.set(cv2.CAP_PROP_FPS, 30)
    self.camcapdevice.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'mjpg'))
    self.camcapdevice.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))    
    self.camcapdevice.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    self.camcapdevice.set(cv2.CAP_PROP_FRAME_HEIGHT, H)

#    self.camcapdevice.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1) #1=off
#    self.camcapdevice.set(cv2.CAP_PROP_EXPOSURE, 666)
##    self.camcapdevice.set(cv2.CAP_PROP_AUTO_WB, 1) #1=on

#    self.camcapdevice.set(cv2.CAP_PROP_AUTOFOCUS, 0) #turn off
#    self.camcapdevice.set(cv2.CAP_PROP_FOCUS, 5)

#    self.camcapdevice.set(cv2.CAP_PROP_SHARPNESS, 200)

  def cam_callback(self, image, pub_type, yuv_type):

    img=image

    # # convert RGB frame to YUV    
    rgb = np.reshape(img, (H, W * 3))
    rgb_cl = cl_array.to_device(self.queue, rgb)
    yuv_cl = cl_array.empty_like(rgb_cl)
    self.krnl(self.queue, (np.int32(self.Wdiv4), np.int32(self.Hdiv4)), None, rgb_cl.data, yuv_cl.data).wait()
    yuv = np.resize(yuv_cl.get(), rgb.size // 2)
    #eof = int(frame_id * 0.05 * 1e9)
    eof = int((time.time() - startTime) * 1e9)


    for idxCam in range(len(pub_type)):
        self.vipc_server.send(yuv_type[idxCam], yuv.data.tobytes(), self.frame_id, eof, eof)

        dat = messaging.new_message(pub_type[idxCam])
        msg = {
          #"frameId": image.frame,
          "frameId": self.frame_id,
          "transform": [1.0, 0.0, 0.0,
                        0.0, 1.0, 0.0,
                        0.0, 0.0, 1.0]
        }

        setattr(dat, pub_type[idxCam], msg)
        pm.send(pub_type[idxCam], dat)

  def update(self):
    result,image = self.camcapdevice.read()
    if result:
      self.cam_callback(image, ['roadCameraState', 'wideRoadCameraState'],[VisionStreamType.VISION_STREAM_ROAD,VisionStreamType.VISION_STREAM_WIDE_ROAD])
      self.frame_id += 1

    self.rk.keep_time()

  def camera_thread(self):
    while True:
      self.update()

def main():  
  cameradaemon = Camerad()
  cameradaemon.camera_thread()

if __name__ == "__main__":
  main()
