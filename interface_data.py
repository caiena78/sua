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
from argparse import ArgumentParser
import os


def nxos(ip,user,password): 
    return {
        'device_type': 'cisco_nxos',
        'host':   ip,
        'username': user,
        'password': password,
        'port' : 22,          # optional, defaults to 22   
        'conn_timeout' : 15
    }


def ios(ip,user,password):    
    return {
        'device_type': 'cisco_ios',
        'host':   ip,
        'username': user,
        'password': password,
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
            int['ip_access'].append(arptable['arp'][arptable['idx'][mac]]['address'])                
        if len(int['mac_voice']) > 0:
            for mac in int['mac_voice']:
                int['ip_voice'].append(arptable['arp'][arptable['idx'][mac]]['address'])            
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
    





if __name__ == '__main__':

    parser = ArgumentParser(description='Select options.')

    # Input parameters
    parser.add_argument('--switchip', type=str, required=True,
                        help='The device IP or DN. Required')
    parser.add_argument('-su','--switchuser', type=str, required=False,
                        help='Username for the switch. Required')
    parser.add_argument('-sp','--switchpassword', type=str, required=False,
                        help='Password for the switch. Required')
    parser.add_argument('--routerip', type=str, required=True,
                        help='The device IP or DN. Required')                     
    parser.add_argument('-ru','--routeruser', type=str, required=False,
                        help='Username for the router. Required')
    parser.add_argument('-rp','--routerpassword', type=str, required=True,
                        help='Password for the router. Required')
    parser.add_argument('-rt','--routertype', type=str,default='nxos', required=False,
                        help='Router OS nxos/iso. Default nxos')
    parser.add_argument('-st','--switchtype', type=str,default='ios', required=False,
                        help='switch OS nxos/ios. Default ios')                      
    

    args = parser.parse_args()


switchuser=""
switchpassword=""
routeruser=""
routerpassword=""

if len(args.switchuser)>0 and len(args.switchpassword)>0:
    switchuser=args.switchuser
    switchpassword=args.switchpassword
else:
    print("user and password must be set for the switch")
    quit()

if len(args.routeruser)>0 and len(args.routerpassword)>0:
    routeruser=args.routeruser
    routerpassword=args.routerpassword
else:
    print("user and password must be set for the router")
    quit()


if args.routertype.lower() == "nxos":
    router=nxos(args.routerip,routeruser,routerpassword)
elif args.routertype.lower()== "ios":
    router=ios(args.routerip,routeruser,routerpassword)
else:
    print("Type has to be set to nxos/ios")
    quit()

if args.switchtype.lower() == "nxos":
    switch=nxos(args.switchip,switchuser,switchpassword)
elif args.switchtype.lower()== "ios":
    switch=ios(args.switchip,switchuser,switchpassword)
else:
    print("Type has to be set to nxos/ios")
    quit()



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


intConfig=getRunningConfig(switch)
interfaces['interfaces']=interfaceparse(intConfig)
interfaces['idx']=buildInterfaceIDX(interfaces)
macdata=getMacTable(switch)
mactable=macTableParse(macdata)
interfacesData=combineDate(mactable,arpTable,interfaces)
with open("interface.csv","w") as f:
    f.write("interface,description,mode,access_vlan,voice_vlan,state,mac_access,mac_voice,ip_acces,ip_voice\r\n")
    for int in interfacesData:
      ip_access=int['ip_access'][0]
      ip_voice=int['ip_voice'][0]
      mac_access=int['mac_access'][0]
      mac_voice=int['mac_voice'][0]
      for i in range(1,len(int['ip_access'])):
          ip_access=ip_access+","+int['ip_access'][i]
          mac_access=mac_access+","+int["mac_access"][i]
      for i in range(1,len(int['ip_access'])):
          ip_voice=ip_voice+","+int['ip_voice'][i]
          mac_voice=mac_voice+","+int['mac_voice'][i]      
      f.write("%s,%s,%s,%s,%s,%s,%s,%s" % int['interface'],int['descripton'],int['mode'],int['access_vlan'],int['voice_vlan'],)


#  "interface": "Gi1/0/12",
#             "description": "",
#             "access_vlan": "1164",
#             "mode": "access",
#             "voice_vlan": "1165",
#             "state": "enabled",
#             "mac_access": [
#                 "c8d9.d27f.7bdb"
#             ],
#             "mac_voice": [
#                 "f8b7.e295.6b71"
#             ],
#             "ip_access": [
#                 "192.168.164.81"
#             ],
#             "ip_voice": [
#                 "192.168.165.155"
#             ]
#         },



# json_object = json.dumps(interfacesData, indent = 4) 
# with open("interface.json", "w") as f:
#     f.write(json_object)

