import time
from typing import Dict, List, Optional
import tiktoken
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, 
                 tokens_per_minute: int = 5000,  # More conservative limit
                 max_tokens_per_request: int = 2000,  # Further reduced per-request limit
                 model: str = "llama3-8b-8192"):
        """
        Initialize rate limiter for Groq API calls.
        
        Args:
            tokens_per_minute: Maximum tokens allowed per minute
            max_tokens_per_request: Maximum tokens allowed per request
            model: The model being used (for token counting)
        """
        self.tokens_per_minute = tokens_per_minute
        self.max_tokens_per_request = max_tokens_per_request
        self.model = model
        self.token_usage: List[Dict] = []  # List of {timestamp, tokens} dicts
        # Use cl100k_base tokenizer which is compatible with most modern LLMs
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.last_request_time = datetime.now()
        # Reserve some tokens for system prompt and response
        self.reserved_tokens = 1000

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string."""
        return len(self.encoding.encode(text))

    def get_available_tokens(self) -> int:
        """Get available tokens for the current minute."""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        
        # Remove old token usage records
        self.token_usage = [usage for usage in self.token_usage 
                          if usage['timestamp'] > minute_ago]
        
        # Calculate used tokens in the last minute
        used_tokens = sum(usage['tokens'] for usage in self.token_usage)
        
        return max(0, self.tokens_per_minute - used_tokens)

    def can_make_request(self, text: str) -> bool:
        """Check if a request can be made with the given text."""
        tokens = self.count_tokens(text)
        # Account for reserved tokens in the request size check
        return (tokens <= (self.max_tokens_per_request - self.reserved_tokens) and 
                tokens <= self.get_available_tokens())

    def record_token_usage(self, tokens: int):
        """Record token usage for rate limiting."""
        self.token_usage.append({
            'timestamp': datetime.now(),
            'tokens': tokens
        })
        self.last_request_time = datetime.now()

    def split_text_into_chunks(self, text: str) -> List[str]:
        """
        Split text into chunks that fit within token limits.
        """
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        # Split text into sentences (rough approximation)
        sentences = text.split('. ')
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            # If a single sentence is too large, split it into smaller parts
            if sentence_tokens > (self.max_tokens_per_request - self.reserved_tokens):
                words = sentence.split()
                current_words = []
                current_word_tokens = 0
                
                for word in words:
                    word_tokens = self.count_tokens(word)
                    if current_word_tokens + word_tokens > (self.max_tokens_per_request - self.reserved_tokens):
                        if current_words:
                            chunks.append(' '.join(current_words))
                        current_words = [word]
                        current_word_tokens = word_tokens
                    else:
                        current_words.append(word)
                        current_word_tokens += word_tokens
                
                if current_words:
                    chunks.append(' '.join(current_words))
                continue
            
            if current_tokens + sentence_tokens > (self.max_tokens_per_request - self.reserved_tokens):
                # Current chunk is full, save it and start a new one
                if current_chunk:
                    chunks.append('. '.join(current_chunk) + '.')
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        # Add the last chunk if it exists
        if current_chunk:
            chunks.append('. '.join(current_chunk) + '.')
        
        return chunks

    def wait_if_needed(self, required_tokens: int):
        """
        Wait if necessary to respect rate limits.
        """
        while not self.can_make_request(" " * required_tokens):
            # Calculate how long to wait
            now = datetime.now()
            time_since_last_request = (now - self.last_request_time).total_seconds()
            
            # Ensure at least 1 second between requests
            if time_since_last_request < 1:
                time.sleep(1 - time_since_last_request)
            else:
                time.sleep(1)  # Wait for 1 second before checking again 