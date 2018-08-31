import subprocess
import time
import logging
import paho.mqtt.client as mqtt
import yaml
import codecs

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    global scan_mac
    logging.info("Connected with result code "+str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    # client.subscribe("device_tracker/#")
    scan_mac.Start()

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    logging.info(msg.topic+" "+str(msg.payload))
    print(msg.topic+" "+str(msg.payload))

def on_disconnect(client, userdata, rc):
    global scan_mac
    if rc != 0:
        logging.error("Unexpected MQTT disconnection. Will auto-reconnect")
        scan_mac.Stop()

class BaseRouter:
  def __init__(self, ip, args):
    self.ip = ip
  def GetAllMACs(self):
    return None


command=" \"for k in \$(iwinfo | grep -Eo wlan[0-9]-?[0-9]?); do iwinfo \$k assoclist ;done | grep -Eo [0-9a-fA-F]{2}:.*:[0-9a-fA-F]{2}\""
class OpenWRTRouter(BaseRouter):
  def __init__(self, ip, args):
    self.ip = ip
  def GetAllMACs(self):
#    print "OpenWRTRoute:", self.ip
    wholecmd = 'ssh root@' + self.ip + command
    p = subprocess.Popen(wholecmd, stdout=subprocess.PIPE, shell=True)
    ret = p.communicate()[0].split()
    print ret
    return ret

class TPLinkRouter(BaseRouter):
  def __init__(self, ip, args):
    self.ip = ip
    self.args = args
  def GetAllMACs(self):
#    print "TPLinkRouter:", self.ip, "Args:", self.args
    wholecmd = 'ssh root@' + self.ip + self.args
    p = subprocess.Popen(wholecmd, stdout=subprocess.PIPE, shell=True)
    ret = p.communicate()
    return ret[0].split()


f = codecs.open(r'config.yaml', 'r',  encoding="utf-8")
conf = yaml.load(f)
f.close()
#print(conf)
all_routers=[]
for host in conf['hosts']:
  ip=host.values()[0]['ip']
  cls=host.values()[0]['class']
  try:
    args=host.values()[0]['args']
  except KeyError:
    args=''
  router_class=globals()[cls]
  router=router_class(ip, args = args)
  all_routers.append(router)

class MacScaner:
  def __init__(self):
    seq = ('incoming', 'leaving')
    self.__handlers = dict.fromkeys(seq)
    self.__active = False
  def Start(self):
    self.__active = True

  def Stop(self):
    self.__active = False

  def Run(self):
    last_macs = list()
    while True:
      if self.__active == True:
        cur_macs=[]
        for router in all_routers:
          cur_macs += router.GetAllMACs()
        print "all:", cur_macs
        intersection_list = list(set(cur_macs).intersection(set(last_macs)))
        incoming_list = list(set(cur_macs).difference(set(intersection_list)))
        leaving_list = list(set(last_macs).difference(set(intersection_list)))
        self.ProcessEvent('incoming', incoming_list)
        self.ProcessEvent('leaving', leaving_list)
        last_macs = cur_macs
      time.sleep(3)

  def AddEventListener(self, type_, handler):
    handlerList = self.__handlers[type_] 
    if handlerList == None:
      handlerList = []
      self.__handlers[type_] = handlerList
    if handler not in handlerList:
      handlerList.append(handler)

  def RemoveEventListener(self, type_, handler):
    try:
      handlerList = self.__handler[type_]
    except KeyError:
      handlerList = []
    handlerList.remove(handler)

  def ProcessEvent(self, type_, event_list):
    if len(event_list) > 0 and type_ in self.__handlers:
      for handler in self.__handlers[type_]:
          handler(event_list)

def OnIncoming(event_list):
    global mqttc
    for mac in event_list:
        topic = "device_tracker/" + mac.replace(':','')
        mqttc.publish(topic, "home", True)
        logging.info("published " + topic + "  home")
#    print 'OnIncoming:'
#    print event_list
 
def OnLeaving(event_list):
    global mqttc
    for mac in event_list:
        topic = "device_tracker/" + mac.replace(':','')
        mqttc.publish(topic, "not_home", True)
        logging.info("published " + topic + "  away")
#    print 'OnLeaving:'
#    print event_list

mqttc = mqtt.Client()
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.on_disconnect = on_disconnect
try:
  mqttc.username_pw_set(username=conf['mqtt']['user'], password = conf['mqtt']['pass'])
  mqttc.connect(conf['mqtt']['host'], conf['mqtt']['port'], 60)
except KeyError:
  print "Failed to get mqtt config"
  exit(-1)
mqttc.loop_start()

scan_mac = MacScaner()
scan_mac.AddEventListener('incoming', OnIncoming)
scan_mac.AddEventListener('leaving', OnLeaving)
scan_mac.Run()
