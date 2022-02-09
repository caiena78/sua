from argparse import ArgumentParser
import json
import os
from network import *
import time
import signal
import sys

# step 1 build interface.json output with bld_int.py
# import the interface.json
# build and hastable of mac address from the interface.json 
# build a interface map of the new switch
# build a hastable of new switch mac address
# skip any ports that are set to trunk
# compare the 2 and change description and vlan's as required

def GetSwitchData(router,switch):
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
    new_switch=combineDate(mactable,arpTable,interfaces)    
    return new_switch

def signal_handler(sig, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)



if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
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
    parser.add_argument('-json','--json_file',type=str,default='interface.json', required=False, help='the location and file name of the interface.json file')

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
    

    # need to use the json_file arg

    with open(args.json_file) as json_file:
        old_switch = json.load(json_file)
          
       
    #new_switch={
    #    "interfaces":{},
    #    "mac_idx":{}
    #     "idx"
    #}
    # interface {
    #   "interface":"",
    #   "description":"",
    #   "access_vlan": "",
    #   "mode":"access",
    #   "voice_vlan":"",
    #   "state":"enabled",
    #   "mac_access":[],
    #   "mac_voice":[],
    #   "ip_access":[],
    #   "ip_voice":[]
    #   }



    cnt=0

    while True: 
        cleanPortSecurity(switch)        
        print("processing") 
        new_switch=GetSwitchData(router,switch)
        print("Cleaning up descriptions")
        updateCMD=cleanUpDescription(new_switch)
        if len(updateCMD)>0:
            sw_data=sendConfig(switch,updateCMD)
            print(sw_data)    
        print("Finished Cleaning up descriptions")
        print("got switch data")
        for i, (mac,interface) in enumerate(new_switch['mac_idx'].items()):
            try:
                old_interface=old_switch['mac_idx'][mac]
            except:
                print("skipping mac:%s" % (mac))
                continue
            new_idx=new_switch['idx'][interface]
            new_interface=new_switch['interfaces'][new_idx]
            old_idx=old_switch['idx'][old_interface]
            old_interface=old_switch['interfaces'][old_idx]
            ## I have the old and new interfaces now i have to figure out if the mac is in access or voice and set the vlan on the new switch and set the description
            update_access_vlan=False
            update_voice_vlan=False
            updateCMD=[]
            updateCMD.append("int %s" % new_interface["interface"])
            if old_interface['description'] != new_interface['description']:
                print("Desc don't match")
                if len(old_interface['description'].strip())==0:
                    print("removing desc")
                    updateCMD.append("no description")
                else:
                    print("setting desc to %s" % old_interface['description'])
                    updateCMD.append("description %s" % old_interface['description'] )   
            # check if the mac address is listed in the voice vlan and set the vlan if nessary    
            if mac in  old_interface["mac_voice"] and  new_interface["voice_vlan"] !=  old_interface["voice_vlan"]:   
                print("changing voice vlan for mac:%s to vlan:%s" % (mac,old_interface["voice_vlan"]))                
                updateCMD.append("switchport voice vlan %s " % old_interface["voice_vlan"])
            if mac in old_interface["mac_access"] and  new_interface["access_vlan"] !=  old_interface["access_vlan"]:    
                print("changing access vlan for mac:%s to vlan:%s" % (mac,old_interface["access_vlan"]))
                updateCMD.append("switchport access vlan %s " % old_interface["access_vlan"])
                update_access_vlan=True
            if len(updateCMD)>1:              
                if update_access_vlan:
                    updateCMD.append("shut") 
                    updateCMD.append("no shut")
                print(updateCMD)                               
                sw_data=sendConfig(switch,updateCMD)
                print(sw_data)    
                time.sleep(5)            
            for ip in old_interface["ip_access"]:     
                if ping(ip):
                    print("Pingable")
                else:
                    print("not pingable")    
                
                             
            # ping device to verify its online


            #time.sleep(30)
            #write log file

            #send command
            #sendCMD(switch,updateCMD)
    


   # json_object = json.dumps(interfacesData, indent = 4) 
   # with open("interface.json", "w") as f:
   #     f.write(json_object)




    

    