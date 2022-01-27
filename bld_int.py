from argparse import ArgumentParser
import json
import os
from network import *


# test with 
# python bld_int.py --switchip 192.168.164.102 -su <username> -sp <password> --routerip 192.168.0.2 -ru %CISCO-SRV-ACCOUNT%  -rp %CISCO-SRV-PWD% -rt nxos -st ios

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
    json_object = json.dumps(interfacesData, indent = 4) 
    with open("interface.json", "w") as f:
        f.write(json_object)
