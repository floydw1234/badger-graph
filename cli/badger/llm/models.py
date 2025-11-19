"""Model-specific LLM client wrappers."""

from typing import Dict, Any, Optional
from badger.config import BadgerConfig
from badger.llm.client import LLMClient
from badger.llm.config import (
    get_qwen_endpoint,
    get_gpt_oss_endpoint,
    get_qwen_model,
    get_gpt_oss_model,
)


class QwenClient(LLMClient):
    """Client wrapper for qwen-3-coder-30b model."""
    
    def __init__(self, config: BadgerConfig):
        """Initialize Qwen client from config.
        
        Args:
            config: BadgerConfig instance
        """
        endpoint = get_qwen_endpoint(config)
        model = get_qwen_model(config)
        
        super().__init__(
            endpoint=endpoint,
            model=model,
            api_key=config.api_key,
            max_retries=config.max_retries,
            timeout=config.timeout,
            requests_per_minute=60  # Reasonable default for query generation
        )
    
    def parse_query(
        self,
        user_query: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = 1000
    ) -> Dict[str, Any]:
        """Parse user query to extract code elements for graph query.
        
        Args:
            user_query: Natural language query from user
            temperature: Sampling temperature (lower for more deterministic)
            max_tokens: Maximum tokens to generate
        
        Returns:
            Response dict with parsed query elements
        """
        system_prompt = """You are a code analysis assistant. Your task is to parse user queries about codebases and extract relevant code elements.

Extract the following from the user's query:
- Function names mentioned
- Class names mentioned
- Variable names mentioned (if relevant)
- File paths mentioned

Respond with a structured analysis that can be used to construct a graph query."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        return self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def construct_graphql_query(
        self,
        matched_elements: Dict[str, list[Dict[str, Any]]],
        user_query: str,
        temperature: float = 0.3,
        max_tokens: Optional[int] = 2000
    ) -> str:
        """Construct GraphQL query from vector search results using qwen-3-coder-30b.
        
        Args:
            matched_elements: Dictionary with 'functions' and/or 'classes' lists from vector search.
                            Each item has: name, file, signature/methods, vector_distance
            user_query: Original user query for context
            temperature: Sampling temperature (lower for more deterministic)
            max_tokens: Maximum tokens to generate
        
        Returns:
            GraphQL query string that retrieves full context (callers, callees, relationships)
        """
        # Format matched elements for the prompt
        matched_text = []
        
        if matched_elements.get("functions"):
            matched_text.append("Matched Functions:")
            for func in matched_elements["functions"][:10]:  # Limit to top 10
                name = func.get("name", "")
                file = func.get("file", "")
                signature = func.get("signature", "")
                matched_text.append(f"  - {name} in {file}")
                if signature:
                    matched_text.append(f"    Signature: {signature}")
        
        if matched_elements.get("classes"):
            matched_text.append("\nMatched Classes:")
            for cls in matched_elements["classes"][:10]:  # Limit to top 10
                name = cls.get("name", "")
                file = cls.get("file", "")
                methods = cls.get("methods", [])
                matched_text.append(f"  - {name} in {file}")
                if methods:
                    matched_text.append(f"    Methods: {', '.join(methods[:5])}")
        
        matched_elements_str = "\n".join(matched_text) if matched_text else "No matches found."
        
        # Example GraphQL query structure
        example_query = """
Example GraphQL query structure:
```
query($funcName0: String!, $funcName1: String!) {
    func_0: queryFunction(filter: {name: {eq: $funcName0}}) {
        id
        name
        file
        line
        column
        signature
        parameters
        returnType
        docstring
        containedInFile {
            path
        }
        callsFunction {
            name
            file
            line
        }
        calledByFunction {
            name
            file
            line
        }
    }
    func_1: queryFunction(filter: {name: {eq: $funcName1}}) {
        id
        name
        file
        line
        signature
        callsFunction {
            name
            file
        }
    }
    cls_0: queryClass(filter: {name: {eq: $className0}}) {
        id
        name
        file
        line
        methods
        baseClasses
        containedInFile {
            path
        }
        inheritsClass {
            name
            file
        }
        containsMethod {
            name
            file
        }
    }
}
```
"""
        
        system_prompt = """You are a GraphQL query generator for a code graph database. Your task is to generate a valid GraphQL query that retrieves comprehensive context about code elements.

The GraphQL schema includes:
- Function type: id, name, file, line, column, signature, parameters, returnType, docstring, containedInFile, callsFunction, calledByFunction
- Class type: id, name, file, line, column, methods, baseClasses, containedInFile, inheritsClass, containsMethod
- File type: path

IMPORTANT:
1. Generate ONLY the GraphQL query string, no explanations or markdown code blocks
2. Use variables for function/class names (e.g., $funcName0: String!)
3. Include relationships: callsFunction, calledByFunction, inheritsClass, containsMethod, containedInFile
4. Query all matched functions and classes
5. Return the query as a single string that can be executed directly"""
        
        user_prompt = f"""User Query: {user_query}

{matched_elements_str}

{example_query}

Generate a GraphQL query that retrieves full context for the matched elements, including their relationships (callers, callees, inheritance, file containment). Use variables for all function and class names. Return ONLY the query string, no markdown or explanations."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Extract query from response (may be wrapped in markdown code blocks)
        query = response.get("content", "").strip()
        
        # Remove markdown code blocks if present
        if query.startswith("```"):
            # Remove opening and closing code blocks
            lines = query.split("\n")
            # Remove first line (```graphql or ```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last line if it's just ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            query = "\n".join(lines)
        
        return query.strip()


class GPTOSSClient(LLMClient):
    """Client wrapper for gpt-oss-120b model."""
    
    def __init__(self, config: BadgerConfig):
        """Initialize GPT-OSS client from config.
        
        Args:
            config: BadgerConfig instance
        """
        endpoint = get_gpt_oss_endpoint(config)
        model = get_gpt_oss_model(config)
        
        super().__init__(
            endpoint=endpoint,
            model=model,
            api_key=config.api_key,
            max_retries=config.max_retries,
            timeout=config.timeout,
            requests_per_minute=30  # Lower rate for larger model
        )
    
    def process_with_context(
        self,
        user_query: str,
        context: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4000
    ) -> Dict[str, Any]:
        """Process user query with code graph context.
        
        Args:
            user_query: User's natural language request
            context: Context from graph query (functions, classes, relationships)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        
        Returns:
            Response dict with model output
        """
        system_prompt = """You are an expert coding assistant with access to a codebase graph. You can understand code relationships and make intelligent edits.

You have access to tools:
- read_file: Read source files
- edit_file: Modify files with preview
- query_graph: Query the code graph for more context

Use the provided context to understand the codebase structure, then help the user with their request."""
        
        # Format context for the prompt
        context_text = self._format_context(context)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context from code graph:\n{context_text}\n\nUser request: {user_query}"}
        ]
        
        return self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format graph context for LLM consumption.
        
        Args:
            context: Context dict with functions, classes, etc.
        
        Returns:
            Formatted context string
        """
        lines = []
        
        if context.get("functions"):
            lines.append("Functions:")
            for func in context["functions"][:20]:  # Limit to top 20
                name = func.get("name", "unknown")
                file = func.get("file", "unknown")
                line = func.get("line", "?")
                signature = func.get("signature", "")
                lines.append(f"  - {name} in {file}:{line} {signature}")
        
        if context.get("classes"):
            lines.append("\nClasses:")
            for cls in context["classes"][:20]:  # Limit to top 20
                name = cls.get("name", "unknown")
                file = cls.get("file", "unknown")
                line = cls.get("line", "?")
                lines.append(f"  - {name} in {file}:{line}")
        
        if context.get("relationships"):
            lines.append("\nRelationships:")
            for rel in context["relationships"][:20]:  # Limit to top 20
                lines.append(f"  - {rel}")
        
        return "\n".join(lines) if lines else "No context found."

