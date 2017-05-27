#!/usr/bin/env python
import boto3
import json
import os
import re

from conversation import ConversationManager, Conversation
import aci
import spark

#Time to wait for new messages every loop (long SQS polling). 
# must be 0 <= WAIT_TIME <= 20
WAIT_TIME=20


if 'SQS_QUEUE_NAME_BASE' in os.environ:
    QUEUE_NAME_BASE = os.environ['SQS_QUEUE_NAME_BASE']
    QUEUE_NAME_RECV = QUEUE_NAME_BASE+'-recv'
    QUEUE_NAME_SEND = QUEUE_NAME_BASE+'-send'
else:
    try:
        cf = boto3.client('cloudformation')
        stack = cf.describe_stacks(StackName='chat-ops-prod')
        for out in stack['Stacks'][0]['Outputs']:
            if out['OutputKey'] == 'recvQueue':
                QUEUE_NAME_RECV = out['OutputValue']
            if out['OutputKey'] == 'sendQueue':
                QUEUE_NAME_SEND = out['OutputValue']
    except:
        QUEUE_NAME_RECV=""
        QUEUE_NAME_SEND=""


def cmd_help(args):
    return "just send commands ... it's not that hard"
    
def cmd_hello(args):
    return "yeah?"
    
def cmd_error(args):
    return "Sorry, an error occurred: %s" % str(args['exception']), args['from_email'], args['room_id']
    


def find_cmd_func_and_args(message, room_id, from_email):
    tokens = message.split()
    cmd_tree_ptr = COMMANDS
    collected_args={}
    
    while len(tokens)>0:
        tok = tokens.pop(0)
        matched_tokens=[]
        for cmd_token, func_or_subcmd in cmd_tree_ptr:
            if cmd_token[0]=='(':
                # This is a regex that should match an arg
                m = re.match(cmd_token, tok)
                if m:
                    collected_args.update(m.groupdict())
                    matched_tokens.append((cmd_token, func_or_subcmd))
            # TODO - need to sanitise token before using it as RE?
            elif re.match(tok, cmd_token):
                print "matched token '%s'"%cmd_token
                matched_tokens.append((cmd_token,func_or_subcmd))
                
        if len(matched_tokens)>1:
            print "multiple matches"
            break
        
        if len(matched_tokens)==1:
            func_or_subcmd = matched_tokens[0][1]
            if isinstance(func_or_subcmd, list):
                cmd_tree_ptr = func_or_subcmd
                continue
            return (func_or_subcmd, collected_args)
                
    # Didn't find a command - return help
    return (cmd_help, {})
    
def generate_response(message, room_id, from_email):
    func, args = find_cmd_func_and_args(message, room_id, from_email)
    
    try:
        is_conv = issubclass(func, Conversation)
    except:
        is_conv = False
    
    if is_conv:
        # The command parsing has led us to a Conversation class
        #  instantiate it and get an initial reply from the conv
        conv_class = func
        conv = conv_class()
        
        conversation_manager.create_conversation(room_id, from_email, conv)
        return conv.process_message(None)
    
    
    return func(args)
    
def process_message(conversation_manager, message, room_id, from_email):
    #check if there is an existing conversation
    conv = conversation_manager.get_existing_conversation(room_id, from_email)
    if conv is None:
        reply = generate_response(message, room_id, from_email)
    else:
        finished, reply = conv.process_message(message)
        if finished is True:
            conversation_manager.delete_conversation(room_id, from_email)
            if reply is None:
                return
        
    spark.send_message(reply, room_id, from_email)
    
COMMANDS = [
    ("help", cmd_help),
    ("hello", cmd_hello),
    ("show", [
        ("health", aci.cmd_fabric_health),
        ("leaf", [
            (r'(?P<node>\d+)', [
                ('interface', [
                    (r'(?P<interface>et?h?\d+/\d+)', aci.cmd_show_interface)
                ]),
            ])
        ]),
    ]),
    ("set", [
        ("vlan", [
            (r'(?P<vlan>\d+)', [
                ('leaf', [
                    (r'(?P<leaf>\d+)', [
                        'interface', [
                            (r'(?P<interface>et?h?\d+/\d+)', [
                                ('tenant', [(r'(?P<tenant>\w+)')])
                            ])
                        ]
                    ])
                ])
            ])
        ]
        )
    ]),
    ("configure", [
        ("vlan", [
            ("on", [
                ("port", aci.ConfigureVlanPort)
            ])
        ])
    ]),
    ("interface", [
        ("description", aci.InterfaceDescription)
    ])
]


if __name__ == '__main__':
    print("Starting labbot server ...")
    
    sqs = boto3.resource('sqs')
    
    
    print "Finding queue %s by name" % QUEUE_NAME_RECV
    queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME_RECV)
    send_queue = sqs.get_queue_by_name(QueueName=QUEUE_NAME_SEND)
    
    conversation_manager = ConversationManager()
    
    while True:
        conversation_manager.timeout_conversations()
        print("Waiting %d seconds for new messages" % WAIT_TIME)
        messages = queue.receive_messages(WaitTimeSeconds=WAIT_TIME)
        for message in messages:
            print("Message received: %s"%message.body)
            message.delete()
            
            try:
                message_json = json.loads(message.body)
            except:
                message_json = None
                print "Unable to decode message - invalid JSON, ignoring."
                
            if message_json:
                if 'roomId' in message_json:
                    print("Message from %s: %s" % (message_json['personEmail'], message_json['text']))
                    
                    try:
                        process_message(conversation_manager, message_json['text'], message_json['roomId'], message_json['personEmail'])
                    except Exception as e:
                        print("An exception occurred while processing message: %s"%e)
                        
                elif 'type' in message_json and message_json['type']=='alexa':
                    print("Received alexa request: %s" % message_json['text'])
                    
                    try:
                        response = generate_response(message_json['text'], None, None)
                    except Exception as e:
                        print("An exception occurred while processing message: %s"%e)
                        
                    print("Proposed response: %s" % response)
                    send_queue.send_message(MessageBody=json.dumps({
                        'type': 'alexa',
                        'text': response,
                    }))