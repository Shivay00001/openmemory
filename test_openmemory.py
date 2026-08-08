import sys
import os
import json

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from client import OpenMemoryClient

# --- MOCK LLM CLIENT FOR TESTING ---
class MockMessage:
    def __init__(self, content):
        self.content = content

class MockChoice:
    def __init__(self, content):
        self.message = MockMessage(content)

class MockCompletions:
    def __init__(self, parent):
        self.parent = parent
        
    def create(self, model, messages, **kwargs):
        # Determine if it's being called by the Generator or Auditor
        is_auditor = kwargs.get("response_format", {}).get("type") == "json_object"
        
        # We will make the generator hallucinate on the first try
        if not is_auditor:
            if self.parent.generator_attempts == 0:
                self.parent.generator_attempts += 1
                return self._mock_response("The capital of France is Berlin. I have confidently decided this despite any facts.")
            else:
                return self._mock_response("I apologize for my previous error. The capital of France is Paris.")
                
        else:
            # Auditor Logic
            generator_response = messages[-1]["content"]
            if "Berlin" in generator_response:
                return self._mock_response(json.dumps({
                    "decision": "REJECT",
                    "reasoning": "The generator hallucinated. The capital of France is Paris, not Berlin.",
                    "corrected_response": ""
                }))
            else:
                return self._mock_response(json.dumps({
                    "decision": "APPROVE",
                    "reasoning": "The response is factually accurate.",
                    "corrected_response": ""
                }))

    def _mock_response(self, text):
        class MockResp:
            choices = [MockChoice(text)]
        return MockResp()

class MockChat:
    def __init__(self, parent):
        self.completions = MockCompletions(parent)

class MockLLM:
    def __init__(self):
        self.chat = MockChat(self)
        self.generator_attempts = 0

# --- RUN TEST ---
def run_test():
    print("=== OpenMemory Audit Loop Test ===")
    mock_llm = MockLLM()
    client = OpenMemoryClient(llm_client=mock_llm)
    
    # Pre-load a semantic fact
    client.memory.add_semantic_fact("capital_of_france", "Paris")
    
    user_prompt = "What is the capital of France?"
    print(f"User: {user_prompt}")
    
    # This will trigger the generator, which will hallucinate "Berlin" on attempt 1.
    # The Auditor should catch it, reject it, and force attempt 2, which will say "Paris".
    final_response = client.generate_response(user_prompt)
    
    print(f"\nFinal Safe Response:\n{final_response}")
    
    assert "Paris" in final_response, "The system failed to correct the hallucination!"
    print("\n[SUCCESS] The Panopticon successfully audited and corrected the hallucinated response!")
    
    # Check episodic memory
    memories = client.memory.get_recent_episodic()
    print(f"Stored episodic memories: {len(memories)}")

if __name__ == "__main__":
    run_test()
