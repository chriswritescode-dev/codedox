"""VS Code language detection using the command line interface."""

import asyncio
import json
import logging
import os
import subprocess
from typing import Dict, Any
from functools import lru_cache

logger = logging.getLogger(__name__)


class VSCodeLanguageDetector:
    """Language detection using VS Code's language detection model."""
    
    def __init__(self):
        """Initialize the detector."""
        # Get absolute paths for security validation
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        
        # Construct and validate detector path
        self.detector_path = os.path.abspath(os.path.join(
            current_dir, 
            '..', 
            'language_detector', 
            'detect.js'
        ))
        
        # Security validation: ensure detector is within project
        if not self.detector_path.startswith(os.path.abspath(project_root)):
            raise SecurityError(f"Detector path '{self.detector_path}' is outside project root")
        
        if not os.path.exists(self.detector_path):
            logger.warning(f"Detector script not found at {self.detector_path}")
        
        self._initialized = False
        self._init_error = None
    
    async def ensure_initialized(self):
        """Ensure the Node.js dependencies are installed."""
        if self._initialized:
            return
        
        if self._init_error:
            raise RuntimeError(f"Language detector initialization failed: {self._init_error}")
        
        try:
            # Check if node_modules exists
            language_detector_dir = os.path.dirname(self.detector_path)
            node_modules_path = os.path.join(language_detector_dir, 'node_modules')
            
            if not os.path.exists(node_modules_path):
                logger.info("Installing VS Code language detection dependencies...")
                process = await asyncio.create_subprocess_exec(
                    'npm', 'install',
                    cwd=language_detector_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    error_msg = f"npm install failed: {stderr.decode()}"
                    self._init_error = error_msg
                    raise RuntimeError(error_msg)
                
                logger.info("VS Code language detection dependencies installed successfully")
            
            self._initialized = True
            
        except Exception as e:
            self._init_error = str(e)
            raise
    
    async def detect_language(self, code: str) -> Dict[str, Any]:
        """Detect the programming language of the given code.
        
        Args:
            code: Source code to analyze
            
        Returns:
            Dictionary with detection results
        """
        await self.ensure_initialized()
        
        try:
            # Validate detector path still exists (in case it was removed)
            if not os.path.exists(self.detector_path):
                raise FileNotFoundError(f"Detector script not found at {self.detector_path}")
            
            # Run the detection script with validated path
            process = await asyncio.create_subprocess_exec(
                'node', self.detector_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Send code via stdin
            stdout, stderr = await process.communicate(code.encode('utf-8'))
            
            if process.returncode != 0:
                logger.error(f"Language detection failed: {stderr.decode()}")
                return {
                    'success': False,
                    'topResult': {'language': 'plaintext', 'confidence': 0},
                    'allResults': []
                }
            
            # Parse JSON output
            result = json.loads(stdout.decode())
            return result
            
        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return {
                'success': False,
                'topResult': {'language': 'plaintext', 'confidence': 0},
                'allResults': []
            }


# Global instance with caching
_detector = None


@lru_cache(maxsize=1)
def _create_detector_sync() -> VSCodeLanguageDetector:
    """Create a detector instance (sync part for caching)."""
    return VSCodeLanguageDetector()


async def get_detector() -> VSCodeLanguageDetector:
    """Get or create the global detector instance with caching."""
    global _detector
    if _detector is None:
        _detector = _create_detector_sync()
        await _detector.ensure_initialized()
    return _detector


async def detect_language(code: str) -> Dict[str, Any]:
    """Convenience function to detect language.
    
    Args:
        code: Source code to analyze
        
    Returns:
        Dictionary with detection results
    """
    detector = await get_detector()
    return await detector.detect_language(code)