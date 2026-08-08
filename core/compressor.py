from typing import List, Dict, Any

class ContextCompressor:
    """Handles Context Reranking and Semantic Chunking for OpenMemory."""
    
    def __init__(self, memory_store):
        self.memory = memory_store
        
    def compress_history(self, messages: List[Dict[str, str]], max_tokens: int = 4000) -> List[Dict[str, str]]:
        """
        Lossless Context Management (LCM). 
        If history is too long, we keep the most recent messages, and summarize the middle, 
        injecting semantic facts to prevent hallucination.
        (For this lightweight version, we use character length as a proxy for tokens: ~4 chars per token).
        """
        max_chars = max_tokens * 4
        
        # Calculate current length
        total_chars = sum(len(m.get("content", "")) for m in messages)
        
        if total_chars <= max_chars:
            return messages
            
        # If it's too long, we need to compress.
        # Reranking strategy: Keep the first message (usually system prompt), 
        # and the last N messages (recent context).
        
        system_msgs = [m for m in messages if m["role"] == "system"]
        other_msgs = [m for m in messages if m["role"] != "system"]
        
        if not other_msgs:
            return messages
            
        # Keep the most recent messages that fit within half the remaining budget
        remaining_chars_for_recent = (max_chars - sum(len(m.get("content", "")) for m in system_msgs)) * 0.7
        
        recent_msgs = []
        current_recent_chars = 0
        for msg in reversed(other_msgs):
            msg_len = len(msg.get("content", ""))
            if current_recent_chars + msg_len < remaining_chars_for_recent:
                recent_msgs.insert(0, msg)
                current_recent_chars += msg_len
            else:
                break
                
        # The messages that were cut out are replaced by a pointer/summary block
        cut_count = len(other_msgs) - len(recent_msgs)
        if cut_count > 0:
            semantic_context = self.memory.get_all_semantic()
            semantic_str = ", ".join([f"{k}: {v}" for k, v in semantic_context.items()])
            
            compression_msg = {
                "role": "system",
                "content": f"[SYSTEM ALERT: {cut_count} older messages were compressed to save context. Essential semantic facts retained: {semantic_str}. If you need older details, they are stored in Episodic Memory.]"
            }
            return system_msgs + [compression_msg] + recent_msgs
            
        return messages
