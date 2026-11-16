import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from rag_engine.logger import get_logger
from rag_engine.exceptions import LLMConnectionError

# Why: Loads environment configurations (API keys) when running locally during diagnostics.
load_dotenv()
logger = get_logger(__name__)

class LLMEngine:
    """
    The Brain Connection Hub.
    Wraps LangChain's connection wrapper to feed inputs directly into OpenAI's API.
    """
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0.0, request_timeout: int = 30):
        # Why: Resolves connection credential from the environment.
        # Connectivity: Passed down from the host OS via docker-compose configuration.
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            logger.error("OPENAI_API_KEY environment variable is missing.")
            raise LLMConnectionError("❌ OPENAI_API_KEY not found in environment!")
            
        try:
            # Why: Instantiates the LangChain OpenAI client wrapper with zero temperature for reliable SQL structure.
            self.llm = ChatOpenAI(
                openai_api_key=api_key,
                model_name=model_name,
                temperature=temperature,
                request_timeout=request_timeout,
                max_retries=2,
            )
            logger.info(f"LLMEngine initialized with model: {model_name} (timeout: {request_timeout}s)")
        except Exception as e:
            logger.error(f"Failed to initialize ChatOpenAI adapter: {e}")
            raise LLMConnectionError(f"Failed to initialize OpenAI client: {str(e)}") from e
        
    def test_connection(self) -> str:
        """
        Simple network handshake diagnostic.
        """
        try:
            response = self.llm.invoke("Hello, are you ready to compile some SQL?")
            return response.content
        except Exception as e:
            logger.error(f"LLM connection test failed: {e}")
            return f"❌ Connection Error: {str(e)}"

if __name__ == "__main__":
    # Why: Quick local trace debugging.
    engine = LLMEngine()
    print("Initiating OpenAI Handshake...")
    print(f"Handshake response: {engine.test_connection()}")
