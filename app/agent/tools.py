import ast
import hashlib
import math
import operator
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AgentTools:
    """Collection of deterministic tools for agent use.

    All tools are deterministic: same input always produces the same output,
    enabling safe caching of results.
    """

    DEFAULT_DOCS: Dict[str, str] = {
        "python": "Python is a high-level programming language known for readability and versatility.",
        "cache": "Caching stores frequently accessed data to reduce latency and computation.",
        "llm": "Large Language Models (LLMs) are AI systems trained on vast text corpora.",
        "api": "An API (Application Programming Interface) allows software components to communicate.",
        "redis": "Redis is an in-memory data structure store used as database, cache, and message broker.",
        "pgvector": "pgvector is a PostgreSQL extension for vector similarity search.",
        "fastapi": "FastAPI is a modern, fast web framework for building APIs with Python.",
    }

    def calculator(self, expression: str) -> str:
        """Safely evaluate a mathematical expression.

        Supports +, -, *, /, **, sqrt, pow, abs, and numeric literals.
        Uses AST-based restricted evaluation to prevent code injection.

        Args:
            expression: Mathematical expression string.

        Returns:
            Result string in the format 'Result: <value>' or error message.
        """
        allowed_names = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
            "sqrt": math.sqrt,
            "pi": math.pi,
            "e": math.e,
        }
        allowed_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }

        if not expression or not expression.strip():
            return "Error: empty expression"

        try:
            tree = ast.parse(expression.strip(), mode="eval")
        except SyntaxError as exc:
            logger.error("Invalid calculator expression: %s", expression)
            return f"Error: invalid syntax - {exc}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Expression):
                continue
            elif isinstance(node, ast.Constant):
                if not isinstance(node.value, (int, float)):
                    raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")
            elif isinstance(node, ast.Num):  # pragma: no cover - Python 3.7 compat
                if not isinstance(node.n, (int, float)):
                    raise ValueError("Unsupported number type")
            elif isinstance(node, ast.BinOp):
                if type(node.op) not in allowed_operators:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            elif isinstance(node, ast.UnaryOp):
                if type(node.op) not in allowed_operators:
                    raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            elif isinstance(node, ast.Call):
                if not (isinstance(node.func, ast.Name) and node.func.id in allowed_names):
                    raise ValueError("Unsupported function call")
            elif isinstance(node, ast.Name):
                if node.id not in allowed_names:
                    raise ValueError(f"Unsupported name: {node.id}")
            elif isinstance(node, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Load, ast.Store)):
                continue
            else:
                raise ValueError(f"Unsupported expression element: {type(node).__name__}")

        def _eval(node):
            if isinstance(node, ast.Expression):
                return _eval(node.body)
            elif isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.BinOp):
                left = _eval(node.left)
                right = _eval(node.right)
                return allowed_operators[type(node.op)](left, right)
            elif isinstance(node, ast.UnaryOp):
                operand = _eval(node.operand)
                return allowed_operators[type(node.op)](operand)
            elif isinstance(node, ast.Call):
                func = allowed_names[node.func.id]
                args = [_eval(arg) for arg in node.args]
                kwargs = {kw.arg: _eval(kw.value) for kw in node.keywords}
                return func(*args, **kwargs)
            elif isinstance(node, ast.Name):
                return allowed_names[node.id]
            else:
                raise ValueError(f"Cannot evaluate {type(node).__name__}")

        result = _eval(tree)
        return f"Result: {result}"

    def document_lookup(self, query: str, documents: Optional[Dict[str, str]] = None) -> str:
        """Look up a document by keyword.

        Args:
            query: Search query string.
            documents: Optional dictionary mapping keywords to document snippets.
                Uses DEFAULT_DOCS if None.

        Returns:
            Matching document snippet, or 'not found' if no match.
        """
        docs = documents if documents is not None else self.DEFAULT_DOCS
        q = query.lower().strip()
        if not q:
            return "Error: empty query"
        for key, value in docs.items():
            if key in q:
                return value
        return "not found"

    def mock_weather(self, city: str) -> str:
        """Return deterministic mock weather for a city.

        Args:
            city: City name string.

        Returns:
            Mock weather report string.
        """
        city_hash = int(hashlib.sha256(city.lower().strip().encode()).hexdigest(), 16)
        conditions = ["sunny", "cloudy", "rainy", "partly cloudy", "windy"]
        temps = range(15, 35)
        condition = conditions[city_hash % len(conditions)]
        temp = temps[city_hash % len(temps)]
        return f"Weather in {city}: {condition}, {temp}°C"
