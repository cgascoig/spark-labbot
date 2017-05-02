
import httplib
import os
import json
import boto3
from base64 import b64decode

# SQS_QUEUE_NAME = boto3.client('kms').decrypt(CiphertextBlob=b64decode(os.environ['SQS_QUEUE_NAME']))['Plaintext']
SQS_QUEUE_NAME = os.environ['SQS_QUEUE_NAME']
SPARK_BOT_TOKEN = boto3.client('kms').decrypt(CiphertextBlob=b64decode(os.environ['SPARK_BOT_TOKEN']))['Plaintext']
BOT_EMAIL = os.environ['BOT_EMAIL']

def response(status, body, headers={'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}):
    return  {
        'statusCode': str(status),
        'body': str(body),
        'headers': headers,
    }
    
def spark_api_call(method, endpoint, body=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer "+SPARK_BOT_TOKEN, 
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
    
def create_or_update_spark_webhook(url, resource):
    res = spark_api_call('GET', '/v1/webhooks')
    for hook in res['items']:
        print "Removing hook with id %s"%hook['id']
        spark_api_call('DELETE', "/v1/webhooks/%s"%hook['id'])
        
    request_body = {
        "name" : "Lambda Webhook",
        "targetUrl" : url,
        "resource" : resource,
        "event" : "all",
    }
        
    res = spark_api_call('POST', '/v1/webhooks', request_body)
        
    return response(200, json.dumps(res))

def dispatch_to_queue(queue_name, spark_data):
    sqs = boto3.resource('sqs')
    print "Finding queue %s by name" % queue_name
    queue = sqs.get_queue_by_name(QueueName=queue_name)
    response = queue.send_message(MessageBody=spark_data)
    
def lambda_handler(event, context):
    print "Got request with event: %s" % str(event)  
    
    if event['httpMethod']=='GET' and 'check_webhook' in event['queryStringParameters'].keys():
        return create_or_update_spark_webhook("https://%s%s" % (event['headers']['Host'], event['requestContext']['path']), "messages")
        
    if event['httpMethod']=='POST':
        #received POST - this should be webhook from spark
        print "Received POST - assume this is webhook from spark"
        spark_body = json.loads(event['body'])
        print "Message from %s" % spark_body['data']['personEmail']
        if spark_body['data']['personEmail'] == BOT_EMAIL:
            return
        
        message = spark_api_call('GET', "/v1/messages/%s" % spark_body['data']['id'])
        dispatch_to_queue(SQS_QUEUE_NAME, json.dumps(message))
        
        return response(200, '')
        
    return response(200, '{"res":"' + str(event) + '"}')