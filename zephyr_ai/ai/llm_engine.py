"""
Local LLM Engine using Ollama
"""

import requests
import json


class OllamaEngine:
    def __init__(self, model="deepseek-coder:6.7b"):
        self.endpoint = "http://localhost:11434/api/generate"
        self.model = model

    def generate_patch(self, context: str, issue: str):
        prompt = f"""
You are an embedded systems security expert.
Fix the issue below in the given C/C++ code.

Issue:
{issue}

Code:
{context}

Provide corrected full code only.
"""

        response = requests.post(
            self.endpoint,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }
        )

        return response.json()["response"]
