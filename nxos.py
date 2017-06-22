import requests
import json
import requests

"""
Modify these please
"""
username = "admin"
password = "C1sco123"
ip_addr =  "10.67.28.200"




def aaa_login(username, password, ip_addr):
    payload = {
        'aaaUser' : {
            'attributes' : {
                'name' : username,
                'pwd' : password
                }
            }
        }
    url = "http://" + ip_addr + "/api/aaaLogin.json"
    auth_cookie = {}

    response = requests.request("POST", url, data=json.dumps(payload))
    if response.status_code == requests.codes.ok:
        data = json.loads(response.text)['imdata'][0]
        token = str(data['aaaLogin']['attributes']['token'])
        auth_cookie = {"APIC-cookie" : token}

    print
    print "aaaLogin RESPONSE:"
    print json.dumps(json.loads(response.text), indent=2)

    return response.status_code, auth_cookie


def aaa_logout(username, ip_addr, auth_cookie):
    payload = {
        'aaaUser' : {
            'attributes' : {
                'name' : username
                }
            }
        }
    url = "http://" + ip_addr + "/api/aaaLogout.json"

    response = requests.request("POST", url, data=json.dumps(payload),
                                cookies=auth_cookie)

    print
    print "aaaLogout RESPONSE:"
    print json.dumps(json.loads(response.text), indent=2)
    print


def post(ip_addr, auth_cookie, url, payload):
    response = requests.request("POST", url, data=json.dumps(payload),
                                cookies=auth_cookie)

    print
    print "POST RESPONSE:"
    print json.dumps(json.loads(response.text), indent=2)
    
    return response.ok
    
def _get(auth_cookie, url):
    response = requests.request("GET", url, cookies=auth_cookie)
    
    return response.ok, response.json()

def cmd_create_vlan(args):
    vlan = args['vlan']
    status, auth_cookie = aaa_login(username, password, ip_addr)
    if status == requests.codes.ok:
        url = "http://" + ip_addr + "/api/mo/sys.json"
        payload = {
          "topSystem": {
            "children": [
              {
                "ipv4Entity": {
                  "children": [
                    {
                      "ipv4Inst": {
                        "children": [
                          {
                            "ipv4Dom": {
                              "attributes": {
                                "name": "default"
                              },
                              "children": [
                                {
                                  "ipv4If": {
                                    "attributes": {
                                      "id": "vlan%s"%vlan
                                    },
                                    "children": [
                                      {
                                        "ipv4Addr": {
                                          "attributes": {
                                            "addr": "10.%s.%s.1/24"%(vlan, vlan)
                                          }
                                        }
                                      }
                                    ]
                                  }
                                }
                              ]
                            }
                          }
                        ]
                      }
                    }
                  ]
                }
              },
              {
                "bdEntity": {
                  "children": [
                    {
                      "l2BD": {
                        "attributes": {
                          "fabEncap": "vlan-%s"%vlan,
                          "pcTag": "1"
                        }
                      }
                    }
                  ]
                }
              },
              {
                "interfaceEntity": {
                  "children": [
                    {
                      "sviIf": {
                        "attributes": {
                          "adminSt": "up",
                          "id": "vlan%s"%vlan
                        }
                      }
                    }
                  ]
                }
              }
            ]
          }
        }
        if post(ip_addr, auth_cookie, url, payload):
            return "OK, I have created VLAN %s" % vlan
        else:
            return "Sorry, I was unable to create VLAN %s" % vlan
        aaa_logout(username, ip_addr, auth_cookie)
        
def cmd_get_vlans(args):
    url = "http://%s/api/mo/sys/bd.json?query-target=children" % ip_addr
    status, auth_cookie = aaa_login(username, password, ip_addr)
    if status == requests.codes.ok:
        ok, json = _get(auth_cookie, url)
        if ok:
            vlans = []
            for data in json['imdata']:
                vlans.append(data['l2BD']['attributes']['id'])
                
            return "The currently configured VLANs are %s" % (', '.join(vlans))
    
    return "Sorry, I was unable to check the current VLANs"