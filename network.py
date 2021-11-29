from netmiko import ConnectHandler 
import re
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

def cleanPortSecurity(device):
    print("clearning PortSecurity")
    command="clear port-security sticky"
    print(sendCMD(device,command))


def sendCMD(device,command):
    with  ConnectHandler(**device) as net_connect:        
        Data = net_connect.send_command(command,use_textfsm=True)        
    return Data    

def sendConfig(device,commands):
    print("Sending Update")
    with  ConnectHandler(**device) as net_connect:  
        net_connect.enable()      
        Data = net_connect.send_config_set(commands)               
    return Data  

def pattern_match(pattern,data,none=False):
    match=re.findall(pattern,data)
    if match:
        return match[0].strip()
    if none == True:    
        return None
    return ""

def ping(hostname):  
    print("Pinging %s" % hostname)  
    response = os.popen("ping -n 1 %s " % hostname).read()   
    # and then check the response...
    pingpattern=r'Reply from .+: bytes=32 time.+ TTL=[0-9]{1,3}'
    if pattern_match(pingpattern,response,True) is not None:
        return True
    return False

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
        "access_vlan": "1",
        "mode":"access",
        "voice_vlan":"1",
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



#remove this unused function
def combineDate2(mactable,arptable,interfaces):
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


def combineDate(mactable,arptable,interfaces):
    out_interfaces={
        "interfaces":{},
        "mac_idx":{},
        "idx":{}
    }    
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
            out_interfaces['mac_idx'][mac]=int['interface']
            try:
                int['ip_access'].append(arptable['arp'][arptable['idx'][mac]]['address'])                          
            except:
                int['ip_access'].append("NO_IP")            
        if len(int['mac_voice']) > 0:
            for mac in int['mac_voice']:
                int['ip_voice'].append(arptable['arp'][arptable['idx'][mac]]['address'])            
    out_interfaces['interfaces']= interfaces['interfaces']
    out_interfaces['idx']=interfaces['idx']           
    return out_interfaces



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
    
