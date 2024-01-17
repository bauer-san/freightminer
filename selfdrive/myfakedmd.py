import cereal.messaging as messaging

from common.realtime import Ratekeeper, DT_DMON

RATE = 1./DT_DMON

class FakeDM:
  """Simulates the dm state to OpenPilot"""

  def __init__(self):
    self.rk = Ratekeeper(RATE)
    self.pm = messaging.PubMaster(['driverStateV2','driverMonitoringState'])
    self.last_dmon_update = 0
    
  def update(self):
    # dmonitoringmodeld output
    dat = messaging.new_message('driverStateV2')
    dat.driverStateV2.leftDriverData.faceOrientation = [0., 0., 0.]
    dat.driverStateV2.leftDriverData.faceProb = 1.0
    dat.driverStateV2.rightDriverData.faceOrientation = [0., 0., 0.]
    dat.driverStateV2.rightDriverData.faceProb = 1.0
    self.pm.send('driverStateV2', dat)

    # dmonitoringd output
    dat = messaging.new_message('driverMonitoringState')
    dat.driverMonitoringState = {
      "faceDetected": True,
      "isDistracted": False,
      "awarenessStatus": 1.,
    }
    self.pm.send('driverMonitoringState', dat)
    self.rk.keep_time()

  def mydrivermonitor_thread(self):
    while True:
      self.update()

def main():
  mydrivermonitor = FakeDM()
  mydrivermonitor.mydrivermonitor_thread()

if __name__ == "__main__":
  main()      
