#!/usr/bin/python2.7

import subprocess
import time
import logging
import paho.mqtt.client as mqtt
import yaml
import codecs
import sys, getopt
import socket, errno

def MyWrite(log_info):
#    sys.stdout.write(log_info)
    sys.stderr.write(log_info + "\n")

def main(argv):
    global config_file
    global payload_home
    config_file = "config.yaml"
    payload_home = "home"
    try:
        opts, args = getopt.getopt(argv, "hc:n:")
    except getopt.GetoptError:
        sys.exit(2)
    for opt, arg in opts:
        if opt in ("-h"):
            #print "(command) -c <config file> -n <home payload name>"
            sys.exit(0)
        elif opt in ("-c"):
            config_file = arg
        elif opt in ("-n"):
            payload_home = arg
        print 'Config file:', config_file
#    sys.exit(0)

if __name__ == "__main__":
    main(sys.argv[1:])

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
  def __init__(self, ip, args, port='22'):
    self.ip = ip
    if port == '':
      self.port = 22
    else:
      self.port = port
  def GetAllMACs(self):
    wholecmd = 'ssh root@' + self.ip + ' -p ' + str(self.port) + ' ' + command
    #print "OpenWRTRoute:", wholecmd
    p = subprocess.Popen(wholecmd, stdout=subprocess.PIPE, shell=True)
    ret = p.communicate()[0].split()
    print ret
    return ret

class TPLinkRouter(BaseRouter):
  def __init__(self, ip, args, port):
    self.ip = ip
    self.args = args
  def GetAllMACs(self):
    wholecmd = 'ssh root@' + self.ip + self.args
    #print "TPLinkRouter:", self.ip, "Args:", self.args
    p = subprocess.Popen(wholecmd, stdout=subprocess.PIPE, shell=True)
    ret = p.communicate()
    return ret[0].split()


f = codecs.open(config_file, 'r',  encoding="utf-8")
conf = yaml.load(f)
f.close()
#print(conf)
all_routers=[]
for host in conf['hosts']:
  ip=host.values()[0]['ip']
  print('ip:' + ip)
  cls=host.values()[0]['class']
  try:
    args=host.values()[0]['args']
  except KeyError:
    args=''
  try:
    port=host.values()[0]['port']
  except KeyError:
    port=''
  router_class=globals()[cls]
  router=router_class(ip, args = args, port = port)
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
    MyWrite("Test!")
    last_macs = list()
    while True:
      if self.__active == True:
        cur_macs=[]
        for router in all_routers:
          MyWrite("Getting!")
          cur_macs += router.GetAllMACs()
          MyWrite("End for one")
        MyWrite("all" + str(cur_macs))
        print "all:", cur_macs
        intersection_list = list(set(cur_macs).intersection(set(last_macs)))
        incoming_list = list(set(cur_macs).difference(set(intersection_list)))
        leaving_list = list(set(last_macs).difference(set(intersection_list)))
        self.ProcessEvent('incoming', incoming_list)
        self.ProcessEvent('leaving', leaving_list)
        last_macs = cur_macs
        time.sleep(60)
      MyWrite("Waiting!")
      time.sleep(1)

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
        mqttc.publish(topic, payload_home, True)
        logging.info("published " + topic + "  home")
    MyWrite('OnIncoming:')
    MyWrite(str(event_list))
 
def OnLeaving(event_list):
    global mqttc
    for mac in event_list:
        topic = "device_tracker/" + mac.replace(':','')
        mqttc.publish(topic, "not_home", True)
        logging.info("published " + topic + "  away")
    MyWrite('OnLeaving:')
    MyWrite(str(event_list))

mqttc = mqtt.Client()
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.on_disconnect = on_disconnect
try:
  mqttc.username_pw_set(username=conf['mqtt']['user'], password = conf['mqtt']['pass'])
  mqttc.connect(conf['mqtt']['host'], conf['mqtt']['port'], 60)
except socket.error as e:
  print "mqtt error"
  exit(-1)
mqttc.loop_start()

scan_mac = MacScaner()
scan_mac.AddEventListener('incoming', OnIncoming)
scan_mac.AddEventListener('leaving', OnLeaving)
scan_mac.Run()
