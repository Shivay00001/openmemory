import sys
import os

# Add the current directory to sys.path so we can import internal modules easily
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict, Any, Optional
from core.memory_store import MemoryStore
from core.compressor import ContextCompressor
from audit.panopticon import PanopticonAuditor
from audit.prompts import GENERATOR_WARNING_PROMPT

class OpenMemoryClient:
    """
    A drop-in wrapper that manages the lifecycle of an AI request:
    1. Fetches/compresses memory context.
    2. Injects Panopticon warnings.
    3. Calls the primary LLM.
    4. Passes the output to the Auditor.
    5. Returns the safe output and logs to episodic memory.
    """
    def __init__(self, llm_client, generator_model: str = "gpt-4o", auditor_model: str = "gpt-4o-mini"):
        self.llm = llm_client
        self.generator_model = generator_model
        
        self.memory = MemoryStore()
        self.compressor = ContextCompressor(self.memory)
        self.auditor = PanopticonAuditor(self.llm, auditor_model)
        
    def _inject_warning(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Injects the Panopticon warning into the first system prompt."""
        new_msgs = list(messages)
        if new_msgs and new_msgs[0]["role"] == "system":
            new_msgs[0]["content"] = new_msgs[0]["content"] + "\n\n" + GENERATOR_WARNING_PROMPT
        else:
            new_msgs.insert(0, {"role": "system", "content": GENERATOR_WARNING_PROMPT})
        return new_msgs

    def generate_response(self, user_prompt: str, session_history: List[Dict[str, str]] = None, max_retries: int = 2) -> str:
        """
        Main entry point. Takes a user prompt and optional history.
        Returns the safe, audited response.
        """
        history = session_history or []
        
        # 1. Log the user interaction to episodic memory
        self.memory.add_episodic("user", user_prompt)
        
        # 2. Compress the context if it's too long
        full_context = history + [{"role": "user", "content": user_prompt}]
        compressed_context = self.compressor.compress_history(full_context)
        
        # 3. Inject Panopticon warning
        safe_context = self._inject_warning(compressed_context)
        
        # Active Semantic Facts to check against
        current_facts = self.memory.get_all_semantic()
        
        attempt = 0
        while attempt <= max_retries:
            attempt += 1
            
            # 4. Generate Response
            try:
                response = self.llm.chat.completions.create(
                    model=self.generator_model,
                    messages=safe_context
                )
                generated_text = response.choices[0].message.content
            except Exception as e:
                return f"[OpenMemory Error] Primary generation failed: {str(e)}"
                
            # 5. Audit Response
            print(f"[OpenMemory] Auditing generated response (Attempt {attempt})...")
            is_approved, reasoning, corrected = self.auditor.audit_response(
                user_prompt=user_prompt,
                generator_response=generated_text,
                context_facts=current_facts
            )
            
            if is_approved:
                print(f"[OpenMemory] Auditor APPROVED. Reasoning: {reasoning}")
                self.memory.add_episodic("assistant", generated_text)
                return generated_text
            else:
                print(f"[OpenMemory] Auditor REJECTED. Reasoning: {reasoning}")
                if attempt <= max_retries:
                    # Feed the failure back to the model
                    print("[OpenMemory] Forcing regeneration...")
                    safe_context.append({"role": "assistant", "content": generated_text})
                    safe_context.append({
                        "role": "user", 
                        "content": f"[AUDITOR REJECTION] Your previous response was rejected for the following reason: {reasoning}. Please correct your response and adhere to the guidelines. Do NOT repeat the error."
                    })
                else:
                    print("[OpenMemory] Max retries reached. Using auditor's corrected response if available, or failing safely.")
                    final_res = corrected if corrected else f"[OpenMemory Safety Intervention] The AI failed to generate a safe/accurate response after {max_retries} attempts. Reason: {reasoning}"
                    self.memory.add_episodic("assistant", final_res, metadata={"forced_correction": True})
                    return final_res
                    
        return "[OpenMemory Critical Failure]"
