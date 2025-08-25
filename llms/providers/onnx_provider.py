import numpy as np
import onnxruntime as ort
from typing import List, Dict, Optional
from transformers import AutoTokenizer
from .base_provider import OfflineProvider

class ONNXProvider(OfflineProvider):
    """ONNX Runtime provider implementation."""
    
    def __init__(self, model_version: str, model_path: str, tokenizer_path: str = None, **kwargs):
        """Initialize ONNX provider.
        
        Args:
            model_version: Model identifier
            model_path: Path to the ONNX model file
            tokenizer_path: Path to the tokenizer (defaults to model_path directory)
            **kwargs: Additional configuration
        """
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path or model_path.rsplit('/', 1)[0]
        self.session = None
        self.tokenizer = None
        
        if not model_path:
            raise ValueError("model_path is required for ONNX provider")
            
        super().__init__(model_version, **kwargs)
    
    def _initialize(self, **kwargs) -> None:
        """Initialize ONNX Runtime session and tokenizer."""
        try:
            # Initialize ONNX Runtime session
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            
            # Initialize tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.tokenizer_path,
                trust_remote_code=True
            )
            
            # Add pad token if missing
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
        except Exception as e:
            raise RuntimeError(f"Error initializing ONNX provider: {e}")
    
    def _sample_next_token(self, logits: np.ndarray) -> int:
        """Sample next token from logits using temperature and top-p sampling."""
        logits = logits.astype(np.float64)
        
        # Apply temperature
        if self.temperature > 0:
            logits = logits / self.temperature
        else:
            # Greedy sampling
            return np.argmax(logits)
        
        # Apply softmax
        exp_logits = np.exp(logits - np.max(logits))
        probabilities = exp_logits / np.sum(exp_logits)
        
        # Apply top-p (nucleus) sampling
        if self.top_p < 1.0:
            sorted_indices = np.argsort(probabilities)[::-1]
            sorted_probs = probabilities[sorted_indices]
            cumsum_probs = np.cumsum(sorted_probs)
            
            # Find cutoff index
            cutoff_idx = np.searchsorted(cumsum_probs, self.top_p) + 1
            cutoff_idx = min(cutoff_idx, len(sorted_indices))
            
            # Keep only top-p tokens
            top_indices = sorted_indices[:cutoff_idx]
            top_probs = probabilities[top_indices]
            top_probs = top_probs / np.sum(top_probs)  # Renormalize
            
            # Sample from top-p distribution
            choice = np.random.choice(len(top_indices), p=top_probs)
            return top_indices[choice]
        else:
            # Sample from full distribution
            return np.random.choice(len(probabilities), p=probabilities)

    def _run_inference(self, input_ids: np.ndarray, attention_mask: Optional[np.ndarray] = None) -> np.ndarray:
        """Run ONNX model inference."""
        onnx_inputs = {
            'input_ids': input_ids.astype(np.int64)
        }
        
        if attention_mask is not None:
            onnx_inputs['attention_mask'] = attention_mask.astype(np.int64)
            
        # Run inference
        outputs = self.session.run(None, onnx_inputs)
        
        # Return logits (usually the first output)
        return outputs[0]

    def _prepare_inputs(self, prompt: List[Dict[str, str]]) -> tuple:
        """Prepare tokenized inputs for the model."""
        try:
            # Format messages for tokenizer
            text = self.tokenizer.apply_chat_template(
                prompt,
                tokenize=False,
                add_generation_prompt=True
            )

            # Tokenize input
            model_inputs = self.tokenizer(
                text,
                return_tensors="np",
                padding=True,
                truncation=True,
                max_length=2048
            )
            
            input_ids = model_inputs['input_ids']
            attention_mask = model_inputs.get('attention_mask')
            
            return input_ids, attention_mask
            
        except Exception as e:
            raise RuntimeError(f"Error preparing inputs: {e}")

    def _generate_tokens(self, input_ids: np.ndarray, attention_mask: Optional[np.ndarray]) -> List[int]:
        """Generate tokens iteratively."""
        generated_tokens = []
        current_input_ids = input_ids.copy()
        current_attention_mask = attention_mask.copy() if attention_mask is not None else None
        
        try:
            for _ in range(self.max_tokens):
                # Run inference
                logits = self._run_inference(current_input_ids, current_attention_mask)
                
                # Get logits for the last token
                next_token_logits = logits[0, -1, :]
                
                # Sample next token
                next_token = self._sample_next_token(next_token_logits)
                
                # Check for EOS token
                if next_token == self.tokenizer.eos_token_id:
                    break
                    
                generated_tokens.append(next_token)
                
                # Update input for next iteration
                next_token_array = np.array([[next_token]], dtype=np.int64)
                current_input_ids = np.concatenate([current_input_ids, next_token_array], axis=1)
                
                if current_attention_mask is not None:
                    next_attention = np.ones((1, 1), dtype=np.int64)
                    current_attention_mask = np.concatenate([current_attention_mask, next_attention], axis=1)

            return generated_tokens
            
        except Exception as e:
            raise RuntimeError(f"Error during token generation: {e}")

    def _generate_raw_content(self, prompt: List[Dict[str, str]]) -> str:
        """Generate content using ONNX model."""
        if not self.session or not self.tokenizer:
            raise RuntimeError("ONNX session or tokenizer not initialized.")

        try:
            input_ids, attention_mask = self._prepare_inputs(prompt)
            generated_tokens = self._generate_tokens(input_ids, attention_mask)
            
            # Decode generated tokens
            if generated_tokens:
                response_data = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
            else:
                response_data = ""
                
            return response_data

        except Exception as e:
            raise RuntimeError(f"Error during content generation: {e}")