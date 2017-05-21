import time
import spark

class ConversationManager(object):
    def __init__(self):
        self.conversations = {}

    def get_conversation_id(self, room_id, from_email):
        return (room_id, from_email)

    def get_existing_conversation(self, room_id, from_email):
        conv_id = self.get_conversation_id(room_id, from_email)
        conv = self.conversations.get(conv_id) # conv will be None if there is no existing conversation
        return conv
    
    def timeout_conversations(self, timeout=30):
        """
        Find any conversations older than timeout and remove them
        """
        for conv_id in self.conversations.keys():
            conv = self.conversations[conv_id]
            if conv.get_age() > timeout:
                print("Timing out conversation with %s" % conv_id[1])
                spark.send_message(conv.generate_timeout(), conv_id[0], conv_id[1])
                del self.conversations[conv_id]
    
    def create_conversation(self, room_id, from_email, conv):
        self.conversations[self.get_conversation_id(room_id, from_email)] = conv
    
    def delete_conversation(self, room_id, from_email):
        del self.conversations[self.get_conversation_id(room_id, from_email)]


class Conversation(object):
    def __init__(self):
        self.required_args = []
        self.args = {}
        self.start_time = time.time()
        self.current_arg = None
        
    def generate_opening(self):
        return "Welcome to the conversation. (if you see this then a subclass has forgotten to override it)"
        
    def generate_question(self):
        return "What is the %s? (note: say \"/cancel\" if you no longer want to do this)"%self.current_arg
        
    def generate_cancel(self):
        return "Ok, cancelling"
        
    def generate_timeout(self):
        return "Timed out waiting for %s"%self.current_arg
        
    def get_age(self):
        """
        Return the 'age' of this conversation. 
        
        Used for determining when to timeout conversations.
        
        Definition of 'age' is not defined so subclasses can choose an appropriate definition
        """
        return time.time() - self.start_time
        
    def process_message(self, message):
        """
        Should return tuple (finished, reply) where finished is True if the conversation has ended. 
        """
        if self.current_arg is None:
            self.current_arg = self.required_args.pop(0)
    
        if message is None:
            # message will be None when the conversation first starts - send the opening and first argument question
            return "%s\n\n%s" % (self.generate_opening(), self.generate_question())
            
        try:
            if message.split()[0] == "/cancel":
                return True, self.generate_cancel()
        except:
            pass
           
        # TODO: probably more validation here 
        self.args[self.current_arg] = message
        
        if len(self.required_args) > 0:
            self.current_arg = self.required_args.pop(0)
            return False, self.generate_question()
        else:
            return True, self.execute_final_action()
            
    def execute_final_action(self):
        """
        Called when all of the required arguments have been gathered. Does nothing by default - subclasses should override. 
        """
        return "Did nothing. (if you see this something went wrong)"
