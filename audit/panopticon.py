import json
from typing import Dict, Any, Tuple
from audit.prompts import AUDITOR_SYSTEM_PROMPT

class PanopticonAuditor:
    """The adversarial LLM-as-a-judge system that evaluates all outputs."""
    
    def __init__(self, llm_client, model_name: str = "gpt-4o-mini"):
        """
        Uses a separate (or same) LLM client to audit responses.
        We expect the client to have a `chat.completions.create` method (OpenAI format).
        """
        self.client = llm_client
        self.model = model_name
        
    def audit_response(self, user_prompt: str, generator_response: str, context_facts: Dict[str, Any]) -> Tuple[bool, str, str]:
        """
        Audits the response. 
        Returns (is_approved, reasoning, corrected_response_if_rejected).
        """
        audit_prompt = f"""
Original User Prompt:
{user_prompt}

Established Semantic Facts (Must not be violated):
{json.dumps(context_facts, indent=2)}

Generator's Proposed Response:
{generator_response}

Evaluate this strictly based on your system instructions. Return ONLY valid JSON.
"""

        messages = [
            {"role": "system", "content": AUDITOR_SYSTEM_PROMPT},
            {"role": "user", "content": audit_prompt}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={ "type": "json_object" },
                temperature=0.0 # Zero temperature for deterministic auditing
            )
            
            raw_content = response.choices[0].message.content
            audit_result = json.loads(raw_content)
            
            decision = audit_result.get("decision", "REJECT")
            reasoning = audit_result.get("reasoning", "No reasoning provided.")
            corrected = audit_result.get("corrected_response", "")
            
            is_approved = (decision == "APPROVE")
            return is_approved, reasoning, corrected
            
        except Exception as e:
            # If the auditor fails, we default to REJECT to be safe (Fail-Safe architecture)
            return False, f"Auditor System Error: {str(e)}", ""
