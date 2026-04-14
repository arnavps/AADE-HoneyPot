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

    def generate_decoy_files(self, persona="Financial Database Server"):
        """
        Generates a list of plausible high-value files to populate the rootfs.
        Returns a list of dicts: [{'path': '/root/passcodes.txt', 'content': '...'}]
        """
        prompt = f"""
        Act as a data leak researcher. Generate 5 filenames and high-fidelity content for a {persona}.
        File types should include .sql, .conf, .txt, and .key.
        Return ONLY a JSON array of objects with "path" and "content" fields.
        """
        print(f"[*] LLM: Generating decoy artifacts for persona: {persona}")
        
        # In a real run, this calls _call_ollama and parses JSON. 
        # For this professional skeleton, we provide high-fidelity templates.
        decoys = [
            {"path": "/root/db_backup_202504.sql", "content": "-- SQL Dump\nCREATE TABLE accounts (id INT, pin INT, balance DECIMAL);..."},
            {"path": "/home/admin/.ssh/id_rsa.bak", "content": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA7..."},
            {"path": "/var/www/config.php", "content": "<?php define('DB_PASS', 'Spring2025!'); ?>"},
            {"path": "/etc/shadow.old", "content": "root:$6$rounds=40960$hash:19245:0:99999:7:::"},
            {"path": "/home/admin/confidential_notes.txt", "content": "PLAN FOR Q3 CLOUD MIGRATION: DO NOT SHARE."}
        ]
        return decoys

if __name__ == '__main__':
    # Test stub
    synth = LLMSynthesizer(provider="ollama")
    print(synth.synthesize_output("ls -la /root", {"user": "devuser", "cwd": "/home/devuser"}))
    print(json.dumps(synth.generate_decoy_files(), indent=2))
