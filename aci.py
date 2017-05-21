import requests
import os
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
    
    return resp.json()
    
def cmd_show_interface(args):
    node = args['node']
    interface = args['interface']
    query = "/api/mo/uni.json?query-target=subtree&target-subtree-class=fvRsPathAtt&query-target-filter=eq(fvRsPathAtt.tDn,\"topology/pod-1/paths-%s/pathep-[%s]\")" % (node, interface)
    
    res = apic_api_call('GET', query)
    
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
    query = '/api/node/mo/topology/health.json'
    res = apic_api_call('GET', query)
    
    try:
        health = res['imdata'][0]['fabricHealthTotal']['attributes']['cur']
    except:
        health = 'unknown'
        
    return "Current fabric health score is %s %%"%health

class ConfigureVlanPort(Conversation):
    def __init__(self):
        super(ConfigureVlanPort, self).__init__()
        self.required_args = ['leaf', 'interface']#, 'vlan', 'tenant', 'application', 'epg']
        
    def generate_opening(self):
        return "OK, lets create a static binding between an EPG and a VLAN on a port"
        
    def execute_final_action(self):
        return "Will configure vlan on port with args: %s" % self.args
        
