import requests
import os
import re
from conversation import Conversation


APIC_URL = os.environ.get('APIC_URL', None)
APIC_USERNAME = os.environ.get('APIC_USERNAME', None)
APIC_PASSWORD = os.environ.get('APIC_PASSWORD', None)

session = requests.Session()
session.verify = False

def _apic_login():
    login_resp = session.post(APIC_URL+"/api/aaaLogin.json", json={'aaaUser': {'attributes': {'name':APIC_USERNAME, 'pwd':APIC_PASSWORD}}})

def apic_api_call(method, endpoint, json=None):
    resp = session.request(method, APIC_URL+endpoint, json=json)
    if resp.status_code==403:
        _apic_login()
        
        resp = session.request(method, APIC_URL+endpoint, json=json)
    
    return resp
    
def resp_ok(resp):
    return resp.status_code >= 200 and resp.status_code < 300
    
def cmd_show_interface(args):
    "Show EPGs configured on  the interface"
    node = args['node']
    interface = args['interface']
    query = "/api/mo/uni.json?query-target=subtree&target-subtree-class=fvRsPathAtt&query-target-filter=eq(fvRsPathAtt.tDn,\"topology/pod-1/paths-%s/pathep-[%s]\")" % (node, interface)
    
    res = apic_api_call('GET', query).json()
    
    encaps=[]
    for path in res['imdata']:
        attrs = path['fvRsPathAtt']['attributes']
        m = re.match(r'(.*)/rspathAtt', attrs['dn'])
        epg_dn = m.group(1)
        encap = attrs['encap']
        encaps.append("%s: %s" % (encap, epg_dn))
    
    reply = "Encaps on leaf %s interface %s: \n\n%s" % (node, interface, '\n'.join(encaps))
    
    return reply
    
def cmd_fabric_health(args):
    "Show the fabric health score"
    query = '/api/node/mo/topology/health.json'
    res = apic_api_call('GET', query).json()
    
    try:
        health = res['imdata'][0]['fabricHealthTotal']['attributes']['cur']
    except:
        health = 'unknown'
        
    return "Current fabric health score is %s %%"%health
    
def _create_option_list(query, class_name, attribute_name):
    res = apic_api_call('GET', query).json()
    result_list = []
    try:
        for result in res['imdata']:
            result_list.append(result[class_name]['attributes'][attribute_name])
            
        return result_list
    except:
        return None
        
def _extract_interface(interface_name):
    """
        Takes an interface name (e.g. eth101/1/20 or e1/2) and returns a dict with 'fex', 'mod' and 'int' keys. 
    """
    return re.match(r'e(th?)?((?P<fex>\d+)/)?(?P<mod>\d+)/(?P<int>\d+)', interface_name).groupdict()
    
def _extract_vlan(vlan):
    """
        e.g. Takes vlan='vlan-28', returns 28 or None if invalid
    """
    try:
        return re.match(r'vlan-(\d+)', vlan).group(1)
    except:
        return None
        
def _extract_leaf(leaf):
    """
        e.g. Takes leaf='leaf-121', returns 121 or None if invalid
    """
    try:
        return re.match(r'leaf-(\d+)', leaf).group(1)
    except:
        return None

class ConfigureVlanPort(Conversation):
    "Configure a legacy VLAN on an interface"
    def __init__(self):
        super(ConfigureVlanPort, self).__init__()
        self.required_args = ['leaf', 'interface', 'vlan']
        self.confirm_before_action = True
        
    
        
    def generate_question(self):
        if self.current_arg == 'leaf':
            leaf_list = _create_option_list(
                '/api/mo/topology/pod-1.json?query-target=subtree&target-subtree-class=fabricNode&query-target-filter=eq(fabricNode.role,"leaf")',
                'fabricNode',
                'name'
            )
            
            if leaf_list:
                return "Which leaf are you configuring? Available leaf switches are %s. " % ', '.join(leaf_list)
                
            return "Which leaf are you configuring? "
        elif self.current_arg == 'interface':
            res = re.match(r'leaf-(\d+)', self.args['leaf'])
            node_id = res.groups(0)
            interface_list = _create_option_list(
                "/api/mo/topology/pod-1/node-%s/sys.json?query-target=subtree&target-subtree-class=l1PhysIf" % node_id,
                'l1PhysIf',
                'id'
            )
            
            if interface_list:
                return "Which interface are you configuring? Available interfaces are: \n%s" % '\n'.join(interface_list)
                
            return "Which interface are you configuring?"
        elif self.current_arg == 'vlan':
            query = '/api/mo/uni/tn-legacy-lab/ap-legacy-lab.json?query-target=subtree&target-subtree-class=fvAEPg'
            res = apic_api_call('GET', query).json()
            vlan_list = []
            try:
                for fvaepg in res['imdata']:
                    vlan_list.append(fvaepg['fvAEPg']['attributes']['name'])
                    
                return "Which VLAN would you like to add? VLANs that exist are %s. " % ', '.join(vlan_list)
            except:
                return "Which VLAN would you like to add? "
        
        return "What is the %s? (note: say \"/cancel\" if you no longer want to do this)"%self.current_arg
        
    def generate_opening(self):
        return "OK, lets add a legacy VLAN to an interface. (note: say \"/cancel\" at any time if you no longer want to do this)"
        
    def execute_final_action(self):
        vlan_id = _extract_vlan(self.args['vlan'])
        leaf_id = _extract_leaf(self.args['leaf'])
        int_dict = _extract_interface(self.args['interface'])
        
        if vlan_id is None or leaf_id is None or int_dict is None:
            return "Configuration failed - unable to parse arguments"
        
        if int_dict['fex']:
            query = "/api/mo/uni/tn-legacy-lab/ap-legacy-lab/epg-vlan-%s/rspathAtt-[topology/pod-1/paths-%s/extpaths-%s/pathep-[eth%s/%s]].json" % (
                vlan_id,
                leaf_id,
                int_dict['fex'],
                int_dict['mod'],
                int_dict['int']
            )
            tdn = "topology/pod-1/paths-%s/extpaths-%s/pathep-[eth%s/%s]" % (
                leaf_id,
                int_dict['fex'],
                int_dict['mod'],
                int_dict['int']
            )
        else:
            query = "/api/mo/uni/tn-legacy-lab/ap-legacy-lab/epg-vlan-%s/rspathAtt-[topology/pod-1/paths-%s/pathep-[eth%s/%s]].json" % (
                vlan_id,
                leaf_id,
                int_dict['mod'],
                int_dict['int']
            )
            tdn = "topology/pod-1/paths-%s/pathep-[eth%s/%s]" % (
                leaf_id,
                int_dict['mod'],
                int_dict['int']
            )
        
        json = {
            "fvRsPathAtt": {
                "attributes": {
                    "descr": "",
                    "encap": "vlan-%s" % vlan_id,
                    "instrImedcy": "lazy",
                    "mode": "native",
                    "primaryEncap": "unknown",
                    "tDn": tdn
                }
            }
        }
        
        res = apic_api_call('POST', query, json)
        if resp_ok(res):
            return "Configuration successful"
        else:
            print "APIC API call failed: %s" % res
            return "Configuration failed"
        
        
class InterfaceDescription(Conversation):
    "Set the description on an interface"
    def __init__(self):
        super(InterfaceDescription, self).__init__()
        self.required_args = ['leaf', 'interface', 'description']
        self.confirm_before_action = True
        
    def generate_question(self):
        if self.current_arg == 'leaf':
            leaf_list = _create_option_list(
                '/api/mo/topology/pod-1.json?query-target=subtree&target-subtree-class=fabricNode&query-target-filter=eq(fabricNode.role,"leaf")',
                'fabricNode',
                'name'
            )
            if leaf_list:
                return "Which leaf are you configuring? Available leaf switches are %s. " % ', '.join(leaf_list)
            return "Which leaf are you configuring? "
            
        elif self.current_arg == 'interface':
            res = re.match(r'leaf-(\d+)', self.args['leaf'])
            node_id = res.groups(0)
            interface_list = _create_option_list(
                "/api/mo/topology/pod-1/node-%s/sys.json?query-target=subtree&target-subtree-class=l1PhysIf" % node_id,
                'l1PhysIf',
                'id'
            )
            if interface_list:
                return "Which interface are you configuring? Available interfaces are: \n%s" % '\n'.join(interface_list)
            return "Which interface are you configuring?"
        
        return "What is the %s? (note: say \"/cancel\" if you no longer want to do this)"%self.current_arg
        
    def generate_opening(self):
        return "OK, lets add a description to an interface. "
        
    def execute_final_action(self):
        leaf_id = _extract_leaf(self.args['leaf'])
        res = _extract_interface(self.args['interface'])
        if res is None or leaf_id is None:
            return "Configuration failed - unable to parse arguments"
        
        if res['fex']:
            query = "/api/mo/uni/infra/hpaths-leaf-%s-f%s-e-%s-%s-intOvrd.json" % (leaf_id, res['fex'], res['mod'], res['int'])
            tdn =  "topology/pod-1/paths-%s/extpaths-%s/pathep-[eth%s/%s]" % (leaf_id, res['fex'], res['mod'], res['int'])
        else:
            query = "/api/mo/uni/infra/hpaths-leaf-%s-e-%s-%s-intOvrd.json" % (leaf_id, res['mod'], res['int'])
            tdn =  "topology/pod-1/paths-%s/pathep-[eth%s/%s]" % (leaf_id, res['mod'], res['int'])
        
        json = {
            "infraHPathS": {
                "attributes": {
                    "descr": self.args['description']
                },
                "children": [
                    {
                        "infraRsHPathAtt": {
                            "attributes": {
                                "tDn": tdn
                            }
                        }
                    }
                ]
            }
        }
        
        res = apic_api_call('POST', query, json)
        if resp_ok(res):
            return "Configuration successful"
        else:
            return "Configuration failed"
