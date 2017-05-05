import unittest
import labbot

EMAIL='test@example.com'
ROOM='8517862781'

class TestParseResponse(unittest.TestCase):
    def do_tests(self, test_list):
        for message, desired_func, desired_args in test_list:
            func,args = labbot.find_cmd_func_and_args(message, EMAIL, ROOM)
            self.assertEqual(func, desired_func)
            self.assertDictEqual(args, desired_args)
            
    def test_help(self):
        self.do_tests([
            ("help", labbot.cmd_help, {}),
        ])
    def test_hello(self):
        self.do_tests([
            ("hello", labbot.cmd_hello, {}),
            ("hell", labbot.cmd_hello, {}),
        ])
        
    def test_show_interface(self):
        tests = [
            ("show leaf 111 interface eth1/2", labbot.cmd_show_interface, {'node': '111', 'interface':'eth1/2'}),
            ("sh leaf 111 int eth1/2", labbot.cmd_show_interface, {'node': '111', 'interface':'eth1/2'}),
            ("sh leaf 111 int e1/2", labbot.cmd_show_interface, {'node': '111', 'interface':'e1/2'}),
        ]
        self.do_tests(tests)
        

if __name__ == '__main__':
    unittest.main()