#!/usr/bin/python
#This python client is intended to control the Dune media player through IP messages.  Obviously this can be easily edited to control any IP controlled media player.  The code is heavily borrowed from the excellent XBMB3C client.  This client is controllable ONLY from another client.  If you start or stop a movie from the Dune remote the MediaBrowser server will not know about it.
import urllib
import httplib
import os
import time
import requests

import threading
import json
from datetime import datetime
import xml.etree.ElementTree as xml

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import mimetypes
from threading import Thread
from SocketServer import ThreadingMixIn
from urlparse import parse_qs
from urllib import urlretrieve

from random import randint
import random
import urllib2


import websocket
from uuid import getnode as get_mac

#Edit these values!
duneIP='192.168.0.104'  #IP of dune player
serverIP='192.168.0.106'  #IP of computer where media is stored
MBIP='192.168.0.100'    #IP of computer that is running MediaBrowser
MBPort='8096' #port for MediaBrowser
smbuser='user' #user name to access computer where media is stored
smbpsswd='psswd'  #password to access computer where media is stored
#End edit


link1="http://"+MBIP+":"+MBPort+"/mediabrowser/Users/Public?format=json" 
urlresponse1=urllib2.urlopen(link1)
dt1=json.load(urlresponse1)
its1=dt1[0]["Id"]
print its1
userid = its1

def getMachineId():
    return "%012X"%get_mac()
    
def getVersion():
    return "0.8.5"

def getAuthHeader():
   deviceName="DunePlayer"
   txt_mac = getMachineId()
   version = getVersion()  
   authString = "MediaBrowser UserId=\"" + userid + "\",Client=\"Dune\",Device=\"" + deviceName + "\",DeviceId=\"" + txt_mac + "\",Version=\"" + version + "\""
   headers = {'Accept-encoding': 'gzip', 'Authorization' : authString}
   return headers 

#################################################################################################
# WebSocket Client thread
#################################################################################################

class WebSocketThread(threading.Thread):
    isstop=True
    logLevel = 0
    client = None
    itemID=None
    notPause=True
    def playbackStarted(self, itemId):
        if(self.client != None):
            self.isstop=False
            print "PlayBack Started!"
            link='http://'+MBIP+':'+MBPort+'/mediabrowser/Users/'+userid+'/PlayingItems/'+itemId[0]
            print link
            resp = requests.post(link, data='', headers=getAuthHeader())
        else:
            print "errorStart"
    def playbackStopped(self, ticks):
        if(self.client != None):
            self.isstop=True
            link='http://'+MBIP+':'+MBPort+'/mediabrowser/Users/'+userid+'/PlayingItems/'+self.itemID[0]+'?PositionTicks=0'
            resp = requests.delete(link, data='', headers=getAuthHeader())
        else:
            print "errorStopped"
    def sendProgressUpdate(self, ticks):
        if(self.client != None):
            link='http://'+MBIP+':'+MBPort+'/mediabrowser/Users/'+userid+'/PlayingItems/'+self.itemID[0]+'/Progress?PositionTicks='+str(ticks)
            print link
            resp = requests.post(link, data='', headers=getAuthHeader())
        else:
            print "errorUpdate"
    def stopClient(self):
        # stopping the client is tricky, first set   to false and then trigger one 
        # more message by requesting one SessionsStart message, this causes the 
        # client to receive the message and then exit
        if(self.client != None):
            self.client.keep_running = False
            messageData = {}
            messageData["MessageType"] = "SessionsStart"
            messageData["Data"] = "300,0"
            messageString = json.dumps(messageData)
            self.client.send(messageString)
        else:
            print "errorstop"
    def on_message(self, ws, message):
        result = json.loads(message)
        messageType = result.get("MessageType")
        playCommand = result.get("PlayCommand")
        data = result.get("Data")
        
        if(messageType != None and messageType == "Play" and data != None):
            self.itemID = data.get("ItemIds")
            playCommand = data.get("PlayCommand")
            if(playCommand != None and playCommand == "PlayNow"):
                self.playbackStarted(self.itemID)
                startPositionTicks = data.get("StartPositionTicks")
                link="http://"+MBIP+":"+MBPort+"/mediabrowser/Items?Ids="+self.itemID[0]+"&Fields=path&format=json"
                urlresponse=urllib2.urlopen(link)
                dt=json.load(urlresponse)
                its=dt.get("Items")
                url=its[0]['Path']
                type=its[0]['VideoType']
                url=url.replace('\\\\', '')
                url=url[url.find('\\'):]
                url=url.replace('\\', '/')
                print url
                playUrl = str(url)
                self.openmedia(duneIP, serverIP, playUrl, type)
                
        elif(messageType != None and messageType == "Playstate"):
            
            command = data.get("Command")
            print command
            if(command != None and command == "Stop"):
                self.playbackStopped(0)
                link='http://'+duneIP+'/cgi-bin/do?cmd=main_screen'
                urllib2.urlopen(link)
            if(command != None and command == "NextTrack"):
                url_response=urllib2.urlopen('http://'+duneIP+'/cgi-bin/do?cmd=ir_code&ir_code=E21DBF00')
            if(command != None and command == "PreviousTrack"):    
                url_response=urllib2.urlopen('http://'+duneIP+'/cgi-bin/do?cmd=ir_code&ir_code=B649BF00')
            if(command != None and command == "Pause"):
                if self.notPause:
                    link='http://'+duneIP+'/cgi-bin/do?cmd=set_playback_state&speed=0'
                    url_response=urllib2.urlopen(link)
                    self.notPause=False
                else:
                    link='http://'+duneIP+'/cgi-bin/do?cmd=set_playback_state&speed=256'
                    url_response=urllib2.urlopen(link)
                    self.notPause=True
                
    def openmedia(self, ipdune, ipserver,  file, type):
        if type=='BluRay':            
            link='http://'+ipdune+'/cgi-bin/do?cmd=start_bluray_playback&media_url=smb://'+smbuser+':'+smbpsswd+'@'+ipserver+file
            link=link.replace(' ', '%20')
            print link
            url_response = urllib2.urlopen(link)
        elif type=='Dvd':
            link='http://'+ipdune+'/cgi-bin/do?cmd=start_dvd_playback&media_url=smb://'+smbuser+':'+smbpsswd+'@'+ipserver+file
            link=link.replace(' ', '%20')
            print link
            url_response = urllib2.urlopen(link)
        else:
            link='http://'+ipdune+'/cgi-bin/do?cmd=start_file_playback&media_url=smb://'+smbuser+':'+smbpsswd+'@'+ipserver+file
            link=link.replace(' ', '%20')
            print link
            url_response = urllib2.urlopen(link)
    def on_error(self, ws, error):
        print error
    def on_close(self, ws):
        print "close"
    def on_open(self, ws):
        machineId = getMachineId()
        version = getVersion()
        messageData = {}
        messageData["MessageType"] = "Identity"
        deviceName = "DunePlayer"
        messageData["Data"] = "Dune|" + machineId + "|" + version + "|" + deviceName #does this do anything?
        messageString = json.dumps(messageData)
        ws.send(messageString)

    def run(self):
        level = 0 #addonSettings.getSetting('logLevel')
        self.logLevel = 0
        if(level != None):
            self.logLevel = int(level)
        if(self.logLevel >= 1):
            websocket.enableTrace(True)        
     
        #Make a call to /System/Info. WebSocketPortNumber is the port hosting the web socket.
        webSocketUrl = "ws://" +  MBIP + ":" + MBPort + "/mediabrowser"
        self.client = websocket.WebSocketApp(webSocketUrl,
                                    on_message = self.on_message,
                                    on_error = self.on_error,
                                    on_close = self.on_close)
        self.client.on_open = self.on_open
        self.client.run_forever()

newWebSocketThread = WebSocketThread()
newWebSocketThread.start()

class managePlayback(): 
    def __init__(self):   
        self.isStopped=True
    def getTime(self):
        url_response=urllib2.urlopen('http://'+duneIP+'/cgi-bin/do?cmd=status')
        url_response=url_response.read()  
        actualTime=0
        if 'stopped' in url_response:
            self.isStopped=True
        elif 'playback_position' in url_response:
            self.isStopped=False
            url_responsePos=url_response[url_response.find('playback_position')+17:]
            url_responsePos=url_responsePos[url_responsePos.find('value="'):]	
            url_responsePos=url_responsePos[:url_responsePos.find('"/>')]
            url_responsePos=url_responsePos.replace('value="', '')
            actualTime=float(url_responsePos)
        return actualTime

monitor = managePlayback()
       
while True:
    try:
        playTime = monitor.getTime()
        playTimeOld=playTime
        print playTime
        print newWebSocketThread.isstop
        if(newWebSocketThread.itemID!=None and newWebSocketThread.isstop!=True):
            newWebSocketThread.sendProgressUpdate(str(int(playTime * 10000000)))
      
        time.sleep(.5)
    except Exception, e:
        print str(e)
        pass

    
# stop the WebSocket client
newWebSocketThread.stopClient()