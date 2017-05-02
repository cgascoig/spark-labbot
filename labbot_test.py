import unittest
import labbot

class TestParseResponse(unittest.TestCase):
    def test_show_interface(self):
        tests = [
            ("show leaf 111 interface eth1/2", labbot.cmd_show_interface, {'node': '111', 'interface':'eth1/2'}),
            ("sh leaf 111 int eth1/2", labbot.cmd_show_interface, {'node': '111', 'interface':'eth1/2'}),
        ]
        for message, desired_func, desired_args in tests:
            func,args = labbot.find_cmd_func_and_args(message, 'test@example.com', '8517862781')
            self.assertEqual(func, desired_func)
            self.assertDictEqual(args, desired_args)
        

if __name__ == '__main__':
    unittest.main()