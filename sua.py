import requests
import json
from pprint import pprint
import os
from argparse import ArgumentParser
import copy

from requests.models import Response

interfaceTemplet={
    "oldinterface":"",
    "oldDescription":"",
    "oldip":"0.0.0.0",
    "oldvlan":"",
    "interface":"",
    "mac":[],
    "vlan":"",
    "description":"",
    "ip" :"0.0.0.0",
    "updateUrl":"",
    "updateHTTPverb":"POST",
    "updateHTTPBody":"",    
}

def crud(router):
    # set REST API headers
    headers = {"Accept": "application/yang-data+json",
               "Content-Type": "application/yang-data+json"}    
    if router['httpVerb']=="GET":
        print(router['url'])
        response = requests.get(router['url'], headers=headers, auth=(router['user'], router['password']), verify=False)
    return response.json()

def getInterfaces(router):
    router["httpVerb"]="GET"
    #router['url']=f"https://{router['ip']}:{router['port']}/restconf/data/Cisco-IOS-XE-interfaces-oper:interfaces/interface/GigabitEthernet"
    router['url']=f"https://{router['ip']}:{router['port']}/restconf/data/Cisco-IOS-XE-native:native/interface/GigabitEthernet"    
    return crud(router)

def getMacAddressTable(router):
    router["httpVerb"]="GET"
    router['url'] = f"https://{router['ip']}:{router['port']}/restconf/data/Cisco-IOS-XE-matm-oper:matm-oper-data"   
    return crud(router)


# this gathers the information from the new switch
def setInterfaceData(ifaces,mactable):
    interfaces=[]
    idx={}
    cnt=0  
    #interfaceData['Cisco-IOS-XE-native:GigabitEthernet']
    for entry in mactable['Cisco-IOS-XE-matm-oper:matm-oper-data']['matm-table']:
        # print(entry)
        if 'matm-mac-entry' in entry:
            for item in entry['matm-mac-entry']:                                
                key=item['port']
                if key not in idx:                
                    idx[key]=cnt
                    interfaces.append(copy.deepcopy(interfaceTemplet))                
                    interfaces[cnt]['interface']=item['port']
                    interfaces[cnt]['mac'].append(item['mac'])
                    interfaces[cnt]['vlan']=item['vlan-id-number']
                    cnt = cnt+1
                else:
                   interfaces[idx[key]]['mac'].append(item['mac'])
    for iface in ifaces['Cisco-IOS-XE-native:GigabitEthernet']:
        if 'shutdown' in iface:
            continue
        if "Gi"+iface['name'] in idx:
            key = "Gi"+iface['name']
            if "description" in iface:
                interfaces[idx[key]]['description']=iface['description']       
    return interfaces






if __name__ == '__main__':

    print("You are running the Cisco Upgrade Assistant")    
    parser = ArgumentParser(description='Select options.')

    # Input parameters
    parser.add_argument('--host', type=str, required=True,
                        help='The device IP or DN. Required')
    parser.add_argument('-u', '--username', type=str, required=True,
                        help='Username on the device. Required')
    parser.add_argument('-p', '--password', type=str, required=True,
                        help='Password for the username. Required')
    parser.add_argument('--port', type=int, default=443,
                        help='Specify this if you want a non-default port. Default: 830')

    args = parser.parse_args()


    # set up connection parameters in a dictionary
    router = {"ip": args.host, "port": args.port, "user": args.username, "password": args.password,"url":"","httpVerb":"GET","httpBody":""}
    interfaceData=getInterfaces(router)
    macTable=getMacAddressTable(router)
    interfacecfg=setInterfaceData(interfaceData,macTable)
    # so far interface config has been updated with the new switch data desc,vlan and mactable
    for item in interfacecfg:
        print(item)
    
        
        
    # #print(getMacAddressTable(router))
