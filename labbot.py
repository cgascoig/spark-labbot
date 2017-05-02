#!/usr/bin/env python
import boto3
import json
import os
import re
import requests
import httplib #only used to share spark code with Lambda which doesn't have requests :-(

#Time to wait for new messages every loop (long SQS polling). 
# must be 0 <= WAIT_TIME <= 20
WAIT_TIME=20

SPARK_TOKEN = os.environ.get('SPARK_BOT_TOKEN', None)
APIC_URL = os.environ.get('APIC_URL', None)
APIC_USERNAME = os.environ.get('APIC_USERNAME', None)
APIC_PASSWORD = os.environ.get('APIC_PASSWORD', None)
if 'SQS_QUEUE_NAME' in os.environ:
    QUEUE_NAME = os.environ['SQS_QUEUE_NAME']
else:
    cf = boto3.client('cloudformation')
    stack = cf.describe_stacks(StackName='chat-ops-prod')
    for out in stack['Stacks'][0]['Outputs']:
        if out['OutputKey'] == 'recvQueue':
            QUEUE_NAME = out['OutputValue']

def spark_api_call(method, endpoint, body=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + SPARK_TOKEN, 
    }
    
    conn=httplib.HTTPSConnection("api.ciscospark.com", 443)
    conn.request(method,endpoint, json.dumps(body), headers)
    
    print "About to send spark API request"
    resp = conn.getresponse()
    print "Got response from spark: %s %s" % (resp.status, resp.reason)
    
    resp_data = resp.read()
    print "Response data: %s"%resp_data
    
    try:
        json_data = json.loads(resp_data)
    except:
        json_data=None
        
    return json_data
    
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
    

def cmd_help(args):
    return "just send commands ... it's not that hard"
    
def cmd_hello(args):
    return "yeah?"
    
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
    
def cmd_error(args):
    return "Sorry, an error occurred: %s" % str(args['exception']), args['from_email'], args['room_id']
    
def find_cmd_func_and_args(message, from_email, room_id):
    for regex_list, func in COMMANDS:
        for regex in regex_list:
            m = re.match(regex, message)
            if m:
                try:
                    return (func, m.groupdict())
                except Exception as e:
                    return (cmd_error, {'from_email':from_email, 'room_id':room_id, 'exception': e})
                return
                
    # Didn't find a command - return help
    return (cmd_help, {})
    
def generate_response(message, from_email, room_id):
    func, args = find_cmd_func_and_args(message, from_email, room_id)
    
    return func(args)
    
def process_message(message, from_email, room_id):
    reply = generate_response(message, from_email, room_id)
    send_reply(reply, from_email, room_id)

def send_reply(message, from_email, room_id):
    print("Sending reply to %s (roomId: %s): %s" % (from_email, room_id, message))
    spark_api_call('POST', '/v1/messages', {
        "roomId": room_id,
        "text": message
    })
    
COMMANDS = [
    ([r'^help$'], cmd_help),
    ([r'^hello|hey|hi$'], cmd_hello),
    ([r'^show leaf (?P<node>\d+) interface (?P<interface>eth\d+/\d+)$'], cmd_show_interface)
]

if __name__ == '__main__':
    print("Starting labbot server ...")
    
    sqs = boto3.resource('sqs')
    
    
    print "Finding queue %s by name" % QUEUE_NAME
    queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME)
    
    while True:
        print("Waiting %d seconds for new messages" % WAIT_TIME)
        messages = queue.receive_messages(WaitTimeSeconds=WAIT_TIME)
        for message in messages:
            print("Message received: %s"%message.body)
            message.delete()
            
            message_json = json.loads(message.body)
            print("Message from %s: %s" % (message_json['personEmail'], message_json['text']))
            
            process_message(message_json['text'], message_json['personEmail'], message_json['roomId'])