import cereal.messaging as messaging
import time

def main():
  pm = messaging.PubMaster(['pandaStates'])
  while 1:
    dat = messaging.new_message('pandaStates', 1)
    dat.valid = True
    dat.pandaStates[0] = {
      'ignitionLine': True,
      'pandaType': "blackPanda",
      'controlsAllowed': True,
      'safetyModel': 'hondaNidec'
    }
    pm.send('pandaStates', dat)
    time.sleep(0.5)


if __name__ == "__main__":
  main()