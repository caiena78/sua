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
import os
from argparse import ArgumentParser





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


def pattern_match(pattern,data,none=False):
    match=re.findall(pattern,data)
    if match:
        return match[0].strip()
    if none == True:    
        return None
    return ""
    

def interfaceparse(data):
    data=data.split('\n')
    interfaces=[]
    cnt=-1
    for line in data:
        if "interface " in line:
            pattern=r'^interface (.+$)'
            matchdata=pattern_match(pattern,line,False)
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
    parser.add_argument('--switchip', type=str, required=True,help='The device IP or DN. Required')
    parser.add_argument('-su','--switchuser', type=str, required=False,help='Username for the switch. Required')
    parser.add_argument('-sp','--switchpassword', type=str, required=False,help='Password for the switch. Required')
    parser.add_argument('--routerip', type=str, required=True,help='The device IP or DN. Required')                     
    parser.add_argument('-ru','--routeruser', type=str, required=False,help='Username for the router. Required')
    parser.add_argument('-rp','--routerpassword', type=str, required=True, help='Password for the router. Required')
    parser.add_argument('-rt','--routertype', type=str,default='nxos', required=False,help='Router OS nxos/iso. Default nxos')
    parser.add_argument('-st','--switchtype', type=str,default='ios', required=False, help='switch OS nxos/ios. Default ios')                      
    # parser.add_argument('-env','--setenv',type=str,default="0",required=False,help='Save paramerters as enviroment variables' )

    args = parser.parse_args()

    ip_address_reg='^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$'
    

    switchip=args.switchip
    switchuser=""
    switchpassword=""
    switchtype=args.switchtype.lower()
    routerip=args.routerip
    routeruser=""
    routerpassword=""
    routertype=args.routertype.lower()



    
    if len(args.switchuser)>0 and len(args.switchpassword)>0:
        switchuser=args.switchuser
        switchpassword=args.switchpassword
    elif os.environ.get("CISCO-SWITCH-USER") is not None and os.environ.get("CISCO-SWITCH-PASSWORD") is not None:
        switchuser=os.environ["CISCO-SWITCH-USER"]
        switchpassword=os.environ["CISCO-SWITCH-PASSWORD"]
    else:
        print("user and password must be set for the switch")
        quit()

    if switchtype is not None or len(switchtype)>=3:
        pass
    elif os.environ.get("CISCO-SWITCH-TYPE") is not None:
       switchtype= os.environ["CISCO-SWITCH-TYPE"].lower()
    else:
        print("Switch type must be set to NXOS/IOS")
        quit()   
    #ip_address_reg
    if pattern_match(ip_address_reg,args.switchip,True) is not None:
        pass
    elif os.environ.get("CISCO-SWITCH-IP") is not None:
       switchip=os.environ["CISCO-SWITCH-IP"] 
    else:
        print("Switch Ip must be set")
        quit()    


    

    if switchtype == "nxos":
        switch=nxos(switchip,switchuser,switchpassword)
    elif switchtype== "ios":
        switch=ios(switchip,switchuser,switchpassword)
    else:
        print("Type has to be set to nxos/ios")
        quit()




    if len(args.routeruser)>0 and len(args.routerpassword)>0:
        routeruser=args.routeruser
        routerpassword=args.routerpassword
    elif os.environ.get("CISCO-ROUTER-USER") is not None and os.environ.get("CISCO-ROUTER-PASSWORD") is not None:
        routeruser=os.environ["CISCO-ROUTER-USER"]
        routerpassword=os.environ["CISCO-ROUTER-PASSWORD"]    
    else:
        print("user and password must be set for the router")
        quit()
        
    
    
    if pattern_match(ip_address_reg,args.routerip,True) is not None:
       pass
    elif os.environ.get("CISCO-ROUTER-IP") is not None and pattern_match(ip_address_reg,os.environ.get("CISCO-ROUTER-IP")) is not None:
       routerip=os.environ["CISCO-ROUTER-IP"]    
    else:
        print("Router IP MUST BE SET")



    if routertype is None or len(routertype)<3:
        routertype= os.environ["CISCO-ROUTER-TYPE"].lower() 
    
    if routertype == "nxos":
        router=nxos(routerip,routeruser,routerpassword)
    elif routertype== "ios":
        router=ios(routerip,routeruser,routerpassword)
    else:
        print("Type has to be set to nxos/ios")
        quit()

    
    if routertype is None or len(routertype)<3:
       routertype= os.environ["CISCO-ROUTER-TYPE"].lower() 
    
    


    if routertype == "nxos":
        router=nxos(args.routerip,routeruser,routerpassword)
    elif routertype== "ios":
        router=ios(args.routerip,routeruser,routerpassword)
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
    json_object = json.dumps(interfacesData['interfaces'], indent = 4) 
    with open("interface.json", "w") as f:
        f.write(json_object)
