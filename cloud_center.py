import requests
import os
import re
from conversation import Conversation
import threading
import time

session = requests.Session()
session.verify = False

class CloudCenterBackgroundTask(threading.Thread):
    def run(self):
        print "thread sleeping for 10 seconds"
        time.sleep(10)
        print "thread finished sleeping"

class CloudCenterLaunchVM(Conversation):
    "Launch a new VM in CloudCenter"
    def __init__(self):
        super(CloudCenterLaunchVM, self).__init__()
        self.required_args = ['type']
        self.confirm_before_action = False
        
    def execute_final_action(self):
        background_task = CloudCenterBackgroundTask()
        background_task.start()