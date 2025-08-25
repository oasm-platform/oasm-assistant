import torch
from typing import List, Dict
from transformers import AutoModelForCausalLM, AutoTokenizer
from .base_provider import OfflineProvider

class HuggingFaceProvider(OfflineProvider):
    """HuggingFace transformers provider implementation."""
    
    def __init__(self, model_version: str, **kwargs):
        """Initialize HuggingFace provider.
        
        Args:
            model_version: HuggingFace model name/path
            **kwargs: Additional configuration
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = None
        self.model = None
        super().__init__(model_version, **kwargs)
    
    def _initialize(self, **kwargs) -> None:
        """Initialize HuggingFace model and tokenizer."""
        try:
            print(f"Loading HuggingFace model '{self.model_version}' on {self.device}...")
            
            # Initialize tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_version,
                trust_remote_code=True,
            )
            
            # Add pad token if missing
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
                
            # Initialize model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_version,
                torch_dtype="auto",
                device_map="auto",
                trust_remote_code=True,
                low_cpu_mem_usage=True,
            )
            
            if hasattr(self.model, 'to'):
                self.model = self.model.to(self.device)
                
            self.model.eval()
            print(f"Model loaded successfully on {self.device}")
            
        except Exception as e:
            raise RuntimeError(f"Error initializing HuggingFace model: {e}")
    
    def _prepare_input(self, prompt: List[Dict[str, str]]) -> torch.Tensor:
        """Prepare input for HuggingFace model."""
        try:
            text = self.tokenizer.apply_chat_template(
                prompt,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False  # Disable thinking mode
            )

            model_inputs = self.tokenizer([text], return_tensors="pt")
            return model_inputs.to(self.device)
            
        except Exception as e:
            raise RuntimeError(f"Error preparing model input: {e}")
    
    def _generate_tokens(self, model_inputs: torch.Tensor) -> List[int]:
        """Generate tokens using the model."""
        try:
            with torch.no_grad():
                generated_ids = self.model.generate(
                    **model_inputs,
                    max_new_tokens=self.max_tokens,
                    do_sample=True,
                    temperature=self.temperature,
                    top_p=self.top_p,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    use_cache=True
                )
            
            # Extract only the new tokens
            input_length = len(model_inputs.input_ids[0])
            output_ids = generated_ids[0][input_length:].tolist()
            return output_ids
            
        except Exception as e:
            raise RuntimeError(f"Error during token generation: {e}")
    
    def _decode_tokens(self, tokens: List[int]) -> str:
        """Decode tokens to text."""
        try:
            return self.tokenizer.decode(tokens, skip_special_tokens=True)
        except Exception as e:
            raise RuntimeError(f"Error decoding tokens: {e}")
    
    def _generate_raw_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using HuggingFace transformers."""
        if not self.model or not self.tokenizer:
            raise RuntimeError("Model or tokenizer not initialized.")

        print(f"Generating content with HuggingFace model '{self.model_version}'...")

        try:
            model_inputs = self._prepare_input(prompt)
            output_tokens = self._generate_tokens(model_inputs)
            response_data = self._decode_tokens(output_tokens)
            return response_data

        except Exception as e:
            raise RuntimeError(f"Error during content generation: {e}")