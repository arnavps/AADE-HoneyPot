import os
import requests
import json

class LLMSynthesizer:
    """
    Ghost in the Machine: Generates human-like terminal responses using LLMs.
    Supports OpenAI (Cloud) and Ollama (Local) for offline Kali environments.
    """
    def __init__(self, provider="openai", model=None):
        self.provider = provider.lower()
        self.api_key = os.getenv("OPENAI_API_KEY", "your-api-key-here")
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = model or ("gpt-4" if provider == "openai" else "llama3")

    def synthesize_output(self, command, context=None):
        """
        Generates a fake terminal output for a given command.
        Context can include 'cwd', 'user', 'last_cmds'.
        """
        prompt = f"""
        You are a seasoned Linux administrator. You are currently logged into a Debian server.
        The user just executed the following command: '{command}'
        Context: {json.dumps(context)}
        
        Generate ONLY the realistic terminal output for this command. 
        - Do NOT include any explanations or meta-talk.
        - If the command is reconnaissance (ls, pwd, id, netstat), provide high-fidelity fake data.
        - If the command is a download (wget, curl), simulate the progress bar and a successful save to /tmp.
        - Match the formatting of a standard bash shell.
        """
        
        if self.provider == "openai":
            return self._call_openai(prompt)
        elif self.provider == "ollama":
            return self._call_ollama(prompt)
        return "Internal Shell Error: segmentation fault (core dumped)"

    def _call_openai(self, prompt):
        try:
            # Mocking the actual call for Windows environment
            # In production, use: openai.ChatCompletion.create(...)
            print(f"[*] LLM (OpenAI): Requesting synthesis for '{prompt[:50]}...'")
            return "[+] Mocked OpenAI Response: Success."
        except Exception as e:
            return f"bash: command not found: {e}"

    def _call_ollama(self, prompt):
        try:
            url = f"{self.ollama_host}/api/generate"
            data = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
            # response = requests.post(url, json=data, timeout=10)
            # return response.json().get('response', '')
            print(f"[*] LLM (Ollama): Requesting local synthesis for model {self.model}")
            return "[+] Mocked Ollama Response: Success."
        except Exception as e:
            return f"error: {e}"

if __name__ == '__main__':
    # Test stub
    synth = LLMSynthesizer(provider="ollama")
    print(synth.synthesize_output("ls -la /root", {"user": "devuser", "cwd": "/home/devuser"}))
