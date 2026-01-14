import os
from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger("Router")

class ArchiveRouter:
    """
    Routes document processing based on file location and nomenclature.
    Separates 'Dictionary/Lexicon' from 'Dogmatics/General' texts.
    """
    
    # Enhanced keywords for dictionary detection
    DICT_KEYWORDS = [
        "dictionary", "lexicon", "사전", "주석", "wörterbuch", 
        "commentary", "kommentar", "tdnt", "twot", "nidntt", "lex"
    ]

    @staticmethod
    def get_chunk_config(file_path: str) -> Tuple[int, int, str]:
        """
        Returns (chunk_size, chunk_overlap, doc_type) based on path.
        """
        path_lower = file_path.lower()
        filename = os.path.basename(path_lower)
        
        # Check parent folder name explicitly for safety
        parent_folder = os.path.basename(os.path.dirname(path_lower))
        
        # 1. Folder Priority (Safer)
        if any(k in parent_folder for k in ArchiveRouter.DICT_KEYWORDS):
            logger.info(f"📚 Routed as Dictionary (Folder match): {filename}")
            return 400, 50, "dictionary"
            
        # 2. Filename Fallback (Only specific strong keywords)
        STRONG_KEYWORDS = ["tdnt", "nidntt", "lexicon", "wörterbuch"]
        if any(k in filename.lower() for k in STRONG_KEYWORDS):
            logger.info(f"📚 Routed as Dictionary (Strong filename match): {filename}")
            return 400, 50, "dictionary"
        
        # Default to Dogmatics
        logger.info(f"📜 Routed as Dogmatics: {filename}")
        return 1200, 150, "dogmatics"

    @staticmethod
    def extract_theological_metadata(file_path: str) -> Dict[str, Any]:
        """
        Extracts author or series info from filename if possible.
        Example: 'Barth_KD_I_1.pdf' -> author: 'Barth', series: 'KD'
        """
        filename = os.path.basename(file_path)
        metadata = {"source": filename}
        
        # Basic heuristic for common authors
        if "barth" in filename.lower():
            metadata["author"] = "Karl Barth"
        elif "bonhoeffer" in filename.lower():
            metadata["author"] = "Dietrich Bonhoeffer"
        elif "calvin" in filename.lower():
            metadata["author"] = "John Calvin"
        else:
            metadata["author"] = "Unknown"
            
        return metadata
