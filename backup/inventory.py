# steps needed to complete the migration
# 1. connect to the old switch. ssh
# 2. collect mac address table
# 3. get the running config
# 4. get the ip address of the gateway for arp lookup
# 5. connect the the new switch
# 6. check the mac address table for new entried
# 7. compare the mac address from the new switch to the old switch to gather vlan and
#    any description on the port 


from netmiko import ConnectHandler 
import re
import json
import copy
import csv
import os


def nxos(ip):
    return {
        'device_type': 'cisco_nxos',
        'host':   ip,
        'username': "<user>",
        'password': "<password>",
        'port' : 22,          # optional, defaults to 22   
        'conn_timeout' : 15
    }


def ios(ip):    
    return {
        'device_type': 'cisco_ios',
        'host':   ip,
        'username': "<user>",
        'password': "<password>",
        'port' : 22,          # optional, defaults to 22   
        'conn_timeout' : 15
    }
    


def showArp(device):
    with  ConnectHandler(**device) as net_connect:
          command=f"show ip arp"
          arpTable = net_connect.send_command(command,use_textfsm=True)
    return arpTable 

def getMacTable(device):
    with  ConnectHandler(**device) as net_connect:
        command="show mac address-table | exclude CPU|---|Address"
        intData = net_connect.send_command(command,use_textfsm=True)
    return intData

def getRunningConfig(device):
    with  ConnectHandler(**device) as net_connect:
        command="show run | section interface"
        Data = net_connect.send_command(command,use_textfsm=True)
    return Data    


def pattern_match(pattern,data):
    match=re.findall(pattern,data)
    if match:
        return match[0].strip()
    return ""
    

def interfaceparse(data):
    data=data.split('\n')
    interfaces=[]
    cnt=-1
    for line in data:
        if "interface " in line:
            pattern=r'^interface (.+$)'
            matchdata=pattern_match(pattern,line)
            if len(data) < 2:
                continue
            interfaces.append(interfaceDict())
            cnt = cnt + 1             
            interfaces[cnt]['interface']=matchdata.replace("GigabitEthernet","Gi").replace("TenGigabitEthernet","Te").replace("Port-channel","Po")
        if "description" in line:
            pattern=r'description(.+$)'
            interfaces[cnt]['description']=pattern_match(pattern,line)
        if  "switchport access vlan" in line:
            pattern=r'switchport access vlan(.+$)'
            interfaces[cnt]['access_vlan']=pattern_match(pattern,line)
        if "switchport mode" in line:
            pattern=r' switchport mode(.+$)'
            interfaces[cnt]['mode']=pattern_match(pattern,line)
        if "switchport voice vlan" in line:
            pattern=r' switchport voice vlan (.+$)'
            interfaces[cnt]['voice_vlan']=pattern_match(pattern,line)
        if "shutdown" in line:    
            pattern=r'^  shutdown'
            matchdata=pattern_match(pattern,line)
            if matchdata:        
                interfaces[cnt]['state']="disabled"
            else: 
                interfaces[cnt]['state']="enabled"
    return interfaces



def interfaceDict():
    return {
        "interface":"",
        "description":"",
        "access_vlan": "",
        "mode":"access",
        "voice_vlan":"",
        "state":"enabled",
        "mac_access":[],
        "mac_voice":[],
        "ip_access":[],
        "ip_voice":[]
    }

def buildInterfaceIDX(interface):
    idx={}
    cnt=0
    for int in interface['interfaces']:
        idx[int["interface"]]=cnt
        cnt=cnt+1
    return idx


def macTableParse(data):
    mactable=[]
    for line in data.split("\n"):
        if line.count("/") == 2:
            if line.count("Fa")==1:
                pattern=r"([0-9]{1,4}).+([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}).+(Fa[0-9]/[0-9]/[0-9]{1,2})"
            else:
                pattern=r"([0-9]{1,4}).+([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}).+(Gi[0-9]/[0-9]/[0-9]{1,2})"       
        else:
            if line.count("Fa")==1:
                pattern=r"([0-9]{1,4}).+([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}).+(Fa[0-9]/[0-9]{1,2})"
            else:
                pattern=r"([0-9]{1,4}).+([0-9a-f]{4}\.[0-9a-f]{4}\.[0-9a-f]{4}).+(Gi[0-9]/[0-9]{1,2})" 
        match=re.findall(pattern,line)        
        if match:
            mactable.append({"vlan":match[0][0],"mac":match[0][1],"port":match[0][2]})
    return mactable        




def combineDate(mactable,arptable,interfaces):
    for mac in mactable:
        if  interfaces['interfaces'][interfaces['idx'][mac['port']]]['access_vlan'] == mac['vlan']:            
            interfaces['interfaces'][interfaces['idx'][mac['port']]]['mac_access'].append(mac['mac'])
        elif interfaces['interfaces'][interfaces['idx'][mac['port']]]['voice_vlan'] == mac['vlan']:            
            interfaces['interfaces'][interfaces['idx'][mac['port']]]['mac_voice'].append(mac['mac'])    

    interfaces=cleanupDupMacAddress(interfaces)

    for int in interfaces['interfaces']:
        if int['state']=="disabled":
           continue
        if len(int["mac_access"])==0 and len(int["mac_voice"])==0:
            continue       
        for mac in int['mac_access']:
                try:
                    int['ip_access'].append(arptable['arp'][arptable['idx'][mac]]['address'])                          
                except:
                     int['ip_access'].append("NO_IP")  
        if len(int['mac_voice']) > 0:
            for mac in int['mac_voice']:
                try:
                    int['ip_voice'].append(arptable['arp'][arptable['idx'][mac]]['address'])            
                except:
                    print("")    
    return interfaces


def cleanupDupMacAddress(interfaces):
    for int in interfaces['interfaces']:
        if  len(int['mac_access']) >0:            
            for mac in int['mac_access']:
                if mac in int['mac_voice']:
                    int['mac_access'].remove(mac)
    return interfaces



def buildArpIDX(arpTable):
    idx={}
    cnt=0
    for item in arpTable:                   
        idx[item['mac']]=cnt
        cnt=cnt+1
    return idx    
    



def process(switchip,switchtype,routerip,routertype):
    if routertype == "nxos":
        router=nxos(routerip)
    elif routertype=="ios":
        router=ios(routerip)

    arpTable={
        "arp":{},
        "idx":{}
    }

    interfaces={
        "interfaces":{},
        "idx":{}
    }
    arpTable['arp']=showArp(router)
    arpTable['idx']=buildArpIDX(arpTable['arp'])

    if switchtype=="ios":
        device=ios(switchip)
    elif switchtype=="nxos":
        device=nxos(switchip)


    intConfig=getRunningConfig(device)
    interfaces['interfaces']=interfaceparse(intConfig)
    interfaces['idx']=buildInterfaceIDX(interfaces)
    macdata=getMacTable(device)
    mactable=macTableParse(macdata)
    interfacesData=combineDate(mactable,arpTable,interfaces)
    
#   return {
#         "interface":"",
#         "description":"",
#         "access_vlan": "",
#         "mode":"access",
#         "voice_vlan":"",
#         "state":"enabled",
#         "mac_access":[],
#         "mac_voice":[],
#         "ip_access":[],
#         "ip_voice":[]
#     }

    #switchip,interface,voice_mac,access_mac,voiceip,accessip
    with open("output.csv","a") as f:
        for int in interfacesData['interfaces']:
            enabled=False
            interface=int["interface"]
            if len(int["mac_voice"])>0:
                mac_voice=int["mac_voice"][0]
                enabled=True
            else:
                mac_voice="N/A"
            if len(int["mac_access"])>0:     
                mac_access= int["mac_access"][0]
                enabled=True
            else:
                mac_access="N/A"
            if    len(int["ip_voice"])>0:         
                ip_voice=int["ip_voice"][0]
                enabled=True
            else:    
                ip_voice="N/A"
            if  len(int["ip_access"])>0:
                ip_access=int["ip_access"][0]
                enabled=True
            else:
                ip_access="N/A"
            if enabled:    
                f.write("%s,%s,%s,%s,%s,%s\n" % (switchip,int["interface"],mac_voice,mac_access,ip_voice,ip_access))
           
        

    #json_object = json.dumps(interfacesData["interfaces"], indent = 4) 
    #print(json_object)

    # with open("interface.json", "w") as f:
    #     f.write(json_object)




csv=csv.DictReader(open("host.csv"))
#switchip,switchtype,routerip,routertype
with open("output.csv","w") as f:
    f.write("switch_ip,interface,mac_voice,mac_access,ip_voice,ip_access\n")

for row in csv:
  print(row["switchip"])  
  process(row["switchip"],row["switchtype"],row["routerip"],row["routertype"])
   
