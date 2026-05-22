import torch
import gc
from typing import List, Optional
from sentence_transformers import SentenceTransformer
import logging

# Logging Setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Embedder")

class TheologyEmbedder:
    """
    Hardware-adaptive embedding service for Theology AI Lab v4.
    Automatically detects Apple Silicon (MPS), NVIDIA (CUDA), or Intel/AMD (CPU).
    """
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model_name = model_name
        self.device = self._detect_device()
        self.model = None
        logger.info(f"🚀 Initializing TheologyEmbedder on device: {self.device}")

    def _detect_device(self) -> str:
        if torch.backends.mps.is_available():
            return "mps"
        elif torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def load_model(self):
        """Lazy loading of the model to save memory until needed."""
        if self.model is None:
            logger.info(f"🧠 Loading {self.model_name}...")
            self.model = SentenceTransformer(
                self.model_name, 
                device=self.device,
                trust_remote_code=True
            )
            logger.info("✅ Model loaded successfully.")

    def embed_documents(self, texts: List[str], batch_size: int = 16) -> List[List[float]]:
        if self.model is None:
            self.load_model()
            
        # Adjust batch size based on hardware (MPS has limited VRAM)
        if self.device == "mps":
            batch_size = 2  # Very conservative for MPS to prevent OOM
        elif self.device == "cpu":
            batch_size = min(batch_size, 4)  # Safer for Intel/Older Macs
        
        # Clear memory before processing
        self._clear_memory()
        
        # Process in smaller chunks to prevent OOM
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            embeddings = self.model.encode(
                batch, 
                batch_size=batch_size, 
                show_progress_bar=False,
                normalize_embeddings=True
            )
            all_embeddings.extend(embeddings.tolist())
            
            # Clear memory after each batch
            if self.device == "mps":
                self._clear_memory()
        
        # Final memory cleanup
        self._clear_memory()
        return all_embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query - LangChain Embeddings interface compatibility."""
        result = self.embed_documents([text])
        return result[0]

    def _clear_memory(self):
        gc.collect()
        if self.device == "mps":
            torch.mps.empty_cache()
        elif self.device == "cuda":
            torch.cuda.empty_cache()

# Quick Test
if __name__ == "__main__":
    embedder = TheologyEmbedder()
    test_text = ["은혜란 무엇인가?", "Justification by faith."]
    vecs = embedder.embed_documents(test_text)
    print(f"Vector Dimension: {len(vecs[0])}")
    print("Success.")
