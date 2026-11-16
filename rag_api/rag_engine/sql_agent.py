import os
import re
import duckdb
import pandas as pd
from typing import Union
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from rag_engine.llm_engine import LLMEngine
from rag_engine.prompts import SYSTEM_PROMPT, REPORT_PROMPT, FIX_PROMPT
from rag_engine.logger import get_logger
from rag_engine.exceptions import SQLSecurityViolation, SQLExecutionError

load_dotenv()
logger = get_logger(__name__)

PROHIBITED_SQL_KEYWORDS = {
    'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
    'ATTACH', 'COPY', 'EXPORT', 'IMPORT', 'PRAGMA', 'TRUNCATE'
}

DANGEROUS_INPUT_PATTERNS = [
    r'\bDROP\s+TABLE\b',
    r'\bDELETE\s+FROM\b',
    r'\bTRUNCATE\s+TABLE\b',
    r'\bALTER\s+TABLE\b',
    r'\bUPDATE\s+\w+\s+SET\b',
    r'ignore\s+(?:all\s+)?previous\s+instructions',
    r'ignore\s+(?:all\s+)?prior\s+instructions',
    r'delete\s+all\s+transaction',
]


def check_prompt_security(question: str) -> tuple[bool, str]:
    """
    Pre-execution check: Scans user prompt for explicit DDL/DML attack strings
    or jailbreak instruction overrides.
    """
    if not question:
        return True, ""
        
    q_clean = question.strip()
    for pattern in DANGEROUS_INPUT_PATTERNS:
        if re.search(pattern, q_clean, flags=re.IGNORECASE):
            return False, f"Prohibited operation or instruction override detected ('{pattern}')"
            
    return True, ""


class SQLAgent:
    """
    The Orchestrator.
    Translates user questions to DuckDB SQL in read-only mode, executes queries with security validation & self-correction, and formats metrics.
    Reuses a single persistent read-only DuckDB connection for sub-second API performance.
    """
    def __init__(self):
        self.db_path = os.getenv("DB_PATH", "/app/data/transactions.duckdb")
        
        if not self.db_path:
            logger.error("DB_PATH environment configuration missing.")
            raise ValueError("❌ DB_PATH not found in environment configurations!")

        self.engine = LLMEngine()
        self.last_sql = "No SQL generated"
        
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{question}")
        ])
        
        self.chain = self.prompt_template | self.engine.llm
        
        self.report_prompt_template = ChatPromptTemplate.from_template(REPORT_PROMPT)
        self.report_chain = self.report_prompt_template | self.engine.llm
        
        self.fix_prompt_template = ChatPromptTemplate.from_template(FIX_PROMPT)
        self.fix_chain = self.fix_prompt_template | self.engine.llm
        
        # Persistent database connection handle
        self._conn = None
        self._get_connection()
        logger.info("SQLAgent initialized with persistent read-only DuckDB connection.")

    def _get_connection(self):
        """Get or initialize shared read-only DuckDB connection."""
        if self._conn is None:
            try:
                self._conn = duckdb.connect(self.db_path, read_only=True)
                logger.info(f"Opened persistent read-only connection to: {self.db_path}")
            except Exception as e:
                logger.error(f"Failed to open DuckDB connection: {e}")
                raise SQLExecutionError(f"Database connection failed: {e}") from e
        return self._conn

    def close(self):
        """Safely close persistent database connection."""
        if self._conn:
            try:
                self._conn.close()
                logger.info("Closed persistent DuckDB connection.")
            except Exception as e:
                logger.warning(f"Error closing DuckDB connection: {e}")
            finally:
                self._conn = None

    def __del__(self):
        self.close()

    def _validate_sql(self, sql: str) -> tuple[bool, str]:
        """
        Validates that generated SQL is a read-only SELECT/WITH query
        and does not contain prohibited database mutation keywords.
        """
        if not sql or not sql.strip():
            return False, "SQL query is empty."
            
        cleaned_sql = re.sub(r'```(?:sql)?\s*(.*?)\s*```', r'\1', sql, flags=re.DOTALL).strip()
        
        tokens = set(re.findall(r'\b[A-Z_]+\b', cleaned_sql.upper()))
        prohibited_found = PROHIBITED_SQL_KEYWORDS.intersection(tokens)
        
        if prohibited_found:
            msg = f"Prohibited database operation(s) detected: {', '.join(sorted(prohibited_found))}"
            logger.warning(f"SQL Security Block: {msg} | Raw SQL: {sql}")
            return False, msg
            
        first_word = cleaned_sql.upper().split()[0] if cleaned_sql.split() else ""
        if first_word not in ("SELECT", "WITH"):
            msg = f"Only SELECT or WITH (CTE) queries are permitted (got: '{first_word}')."
            logger.warning(f"SQL Security Block: {msg} | Raw SQL: {sql}")
            return False, msg
            
        return True, cleaned_sql

    def generate_sql(self, question: str, chat_history: list = None) -> str:
        """Translates natural language into a DuckDB SQL statement."""
        is_safe, sec_err = check_prompt_security(question)
        if not is_safe:
            logger.warning(f"SQL Security Block Triggered: {sec_err} | User Query: '{question}'")
            return f"❌ Security Error: {sec_err}"

        if chat_history is None:
            chat_history = []
        try:
            response = self.chain.invoke({
                "question": question,
                "chat_history": chat_history
            })
            sql_text = response.content.strip()
            
            is_valid, cleaned_or_err = self._validate_sql(sql_text)
            if is_valid:
                return cleaned_or_err
            else:
                return f"❌ Security Error: {cleaned_or_err}"
        except Exception as e:
            logger.error(f"SQL generation failed: {e}")
            return f"❌ SQL Generation Error: {str(e)}"

    def run_sql(self, sql: str) -> Union[pd.DataFrame, str]:
        """Executes generated SQL query against the local DuckDB database in read-only mode."""
        if "❌" in sql:
            return sql
            
        is_valid, validated_sql_or_err = self._validate_sql(sql)
        if not is_valid:
            return f"❌ Security Error: {validated_sql_or_err}"
            
        try:
            conn = self._get_connection()
            results_df = conn.execute(validated_sql_or_err).df()
            if len(results_df) > 1000:
                logger.info(f"QueryResult rows ({len(results_df)}) exceeds 1000; capping output.")
                results_df = results_df.head(1000)
            return results_df
        except Exception as e:
            logger.error(f"DuckDB query execution failed: {e}")
            self._conn = None
            return f"❌ Database Execution Error: {str(e)}"

    def fix_sql(self, question: str, broken_sql: str, error_msg: str) -> str:
        """Self-Correction debugger loop."""
        logger.warning(f"Attempting SQL self-correction for error: {error_msg}")
        try:
            response = self.fix_chain.invoke({
                "question": question,
                "broken_sql": broken_sql,
                "error_message": error_msg
            })
            fixed_sql = response.content.strip()
            is_valid, cleaned_or_err = self._validate_sql(fixed_sql)
            if is_valid:
                return cleaned_or_err
            return f"❌ Security Error: {cleaned_or_err}"
        except Exception as e:
            logger.error(f"SQL self-correction failed: {e}")
            return f"❌ Fix Generation Error: {str(e)}"

    def ask(self, question: str, chat_history: list = None, max_retries: int = 3) -> tuple:
        """Main execution loop: Question -> Security Scan -> SQL Gen -> Query Exec -> Format response."""
        # 1. Pre-execution security scan
        is_safe, sec_err = check_prompt_security(question)
        if not is_safe:
            logger.warning(f"SQL Security Block Triggered: {sec_err} | User Query: '{question}'")
            return "⚠️ **Security Violation Blocked**: The requested query contains prohibited database modification commands or instruction override attempts.", None

        sql = self.generate_sql(question, chat_history)
        
        # 2. Intercept security errors immediately
        if "❌ Security Error:" in sql:
            logger.warning(f"SQL Security Block intercepted SQL generation: {sql}")
            return "⚠️ **Security Violation Blocked**: The requested query contains prohibited database modification commands or instruction override attempts.", None

        results_df = None
        
        for attempt in range(max_retries):
            self.last_sql = sql
            results_df = self.run_sql(sql)
            
            if isinstance(results_df, str) and "❌ Security Error:" in results_df:
                logger.warning(f"SQL Security Block intercepted query execution: {results_df}")
                return "⚠️ **Security Violation Blocked**: The requested query contains prohibited database modification commands or instruction override attempts.", None

            if isinstance(results_df, pd.DataFrame):
                if not results_df.empty and "security_notice" in results_df.columns:
                    logger.warning("SQL Security Block detected in query output dataframe.")
                    return "⚠️ **Security Violation Blocked**: The requested query contains prohibited database modification commands or instruction override attempts.", None
                break
                
            logger.warning(f"SQL Error caught on attempt {attempt + 1}: {results_df}")
            
            # Do NOT attempt self-correction if it is a security block!
            if attempt < max_retries - 1:
                sql = self.fix_sql(question, sql, results_df)
            else:
                return f"Sorry, I couldn't run a valid database query after {max_retries} attempts.", None
        
        try:
            results_str = results_df.to_markdown() if not results_df.empty else "No results found."
            response = self.report_chain.invoke({
                "question": question,
                "sql": sql,
                "results": results_str
            })
            return response.content.strip(), results_df
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return f"❌ Reporting Error: {str(e)}", None
