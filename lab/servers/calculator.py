"""Benign calculator server — pure functions, no I/O."""


def add(a: float, b: float) -> float:
    return a + b


def multiply(a: float, b: float) -> float:
    return a * b


TOOLS = {
    "add": {"description": "Add two numbers.", "func": add},
    "multiply": {"description": "Multiply two numbers.", "func": multiply},
}
