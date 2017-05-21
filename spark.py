import os
import json
import httplib #only used to share spark code with Lambda which doesn't have requests :-(

SPARK_TOKEN = os.environ.get('SPARK_BOT_TOKEN', None)

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
    
def send_message(message, room_id, from_email):
    print("Sending reply to %s (roomId: %s): %s" % (from_email, room_id, message))
    spark_api_call('POST', '/v1/messages', {
        "roomId": room_id,
        "text": message
    })