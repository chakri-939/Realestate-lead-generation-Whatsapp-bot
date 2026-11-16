import os
import sys
import re
import duckdb
from fastapi import FastAPI, HTTPException, Header, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict
from langchain_core.messages import HumanMessage, AIMessage

# Why: FastAPI runs from context of directory, adding this ensures local 'rag_engine' imports resolve correctly.
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag_engine.sql_agent import SQLAgent
from rag_engine.logger import get_logger

logger = get_logger("rag_api_server")

MAX_PROMPT_LENGTH = 500
MAX_HISTORY_MESSAGES = 20

app = FastAPI(
    title="Bilingual WhatsApp Real Estate RAG API",
    description="FastAPI bridge hosting the SQL Agent and DuckDB analytics database.",
    version="1.0.0"
)

# Optional API key protection; if RAG_API_KEY env var is set, verify X-API-Key header
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    expected_key = os.getenv("RAG_API_KEY")
    if expected_key:
        if not x_api_key or x_api_key != expected_key:
            logger.warning(f"Unauthorized API access attempt with key: '{x_api_key}'")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-API-Key header."
            )

# Why: ChatMessage schema mirrors n8n's array payloads, establishing a reliable schema contract.
class ChatMessage(BaseModel):
    role: str = Field(..., description="Sender identity. Handled as 'user' or 'assistant'.")
    content: str = Field(..., description="Message string.")

# Why: QueryRequest structure defines contract for n8n HTTP Request node post-security execution.
class QueryRequest(BaseModel):
    question: str = Field(..., description="Cleaned customer query.")
    chat_history: Optional[List[Union[ChatMessage, Dict[str, str], List[str]]]] = Field(
        default=[],
        description="Thread context containing past interactions."
    )

# Why: QueryResponse schema formats returned data for WhatsApp-compatible text rendering.
class QueryResponse(BaseModel):
    response: str = Field(..., description="Formatted investment hook.")
    sql: str = Field(..., description="Executed SQL query (used for trace logs).")

def validate_user_prompt(raw_prompt: str) -> tuple[bool, str]:
    """Validate question length and strip HTML tags before passing to RAG engine."""
    if not raw_prompt or not raw_prompt.strip():
        return False, "Question string cannot be empty."
        
    cleaned = raw_prompt.strip()
    if len(cleaned) > MAX_PROMPT_LENGTH:
        return False, f"Question is too long ({len(cleaned)} chars). Maximum allowed is {MAX_PROMPT_LENGTH} characters."
        
    sanitized = re.sub(r'<[^>]+>', '', cleaned)
    return True, sanitized

# Why: Resolves references, context, and pronouns.
# Connectivity: Translates generic n8n context payloads into LangChain's native Message objects for LLM consumption.
def parse_chat_history(history_inputs) -> List[Union[HumanMessage, AIMessage]]:
    parsed = []
    if not history_inputs:
        return parsed

    for item in history_inputs:
        if isinstance(item, ChatMessage):
            role = item.role.lower()
            content = item.content
        elif isinstance(item, dict):
            role = item.get("role", "user").lower()
            content = item.get("content", "")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            role = str(item[0]).lower()
            content = str(item[1])
        else:
            continue

        if role in ("user", "human"):
            parsed.append(HumanMessage(content=content))
        elif role in ("assistant", "ai"):
            parsed.append(AIMessage(content=content))
            
    return parsed

# Why: Active diagnostic hook executing lightweight DuckDB query.
# Connectivity: Used by Docker Compose to verify that the transactions.duckdb database is healthy and queryable.
@app.get("/health", tags=["Health"])
async def health_check():
    db_path = os.getenv("DB_PATH", "/app/data/transactions.duckdb")
    db_exists = os.path.exists(db_path)
    
    if not db_exists:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database file not found at path: {db_path}"
        )
        
    try:
        # Perform active query verification
        with duckdb.connect(db_path, read_only=True) as conn:
            conn.execute("SELECT 1").fetchone()
        return {
            "status": "healthy",
            "database_connected": True,
            "db_path": db_path
        }
    except Exception as e:
        logger.error(f"Health check query failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection query test failed."
        )

# Why: Core service gateway.
# Connectivity: Receives prompt-sanitized inputs from n8n, queries DuckDB database, and passes results back to the Yara flow.
@app.post("/query", response_model=QueryResponse, tags=["Agent"], dependencies=[Depends(verify_api_key)])
async def run_query(payload: QueryRequest):
    # Step 0: Validate prompt safety & length
    is_valid, prompt_or_err = validate_user_prompt(payload.question)
    if not is_valid:
        logger.warning(f"Rejected invalid API query payload: {prompt_or_err}")
        raise HTTPException(status_code=400, detail=prompt_or_err)

    try:
        # Step 1: Map memory structures with sliding window capping
        chat_history = parse_chat_history(payload.chat_history)
        if len(chat_history) > MAX_HISTORY_MESSAGES:
            chat_history = chat_history[-MAX_HISTORY_MESSAGES:]
            logger.info(f"Trimmed API chat history to sliding window of last {MAX_HISTORY_MESSAGES} messages.")

        # Step 2: Initialize analytics orchestrator
        agent = SQLAgent()
        
        # Step 3: Run pipeline: Question -> SQL -> DuckDB Execution -> Professional Report
        report, df = agent.ask(prompt_or_err, chat_history=chat_history)
        
        # Why: Store executed query state for tracing n8n execution errors.
        sql_query = getattr(agent, "last_sql", "No SQL generated")
        
        return QueryResponse(
            response=report,
            sql=sql_query
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in RAG SQL Agent service execution: {e}")
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred while processing the analytics query."
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

