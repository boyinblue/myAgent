#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ast
import math
import operator
import sys


_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_ALLOWED_FUNCS = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
}

_ALLOWED_CONSTS = {
    "pi": math.pi,
    "e": math.e,
}


def _eval_node(node: ast.AST):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("숫자 상수만 허용됩니다.")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise ValueError("지원하지 않는 연산자입니다.")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _BIN_OPS[op_type](left, right)

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise ValueError("지원하지 않는 단항 연산자입니다.")
        operand = _eval_node(node.operand)
        return _UNARY_OPS[op_type](operand)

    if isinstance(node, ast.Name):
        if node.id in _ALLOWED_CONSTS:
            return _ALLOWED_CONSTS[node.id]
        raise ValueError(f"허용되지 않은 이름입니다: {node.id}")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise ValueError("허용되지 않은 함수 호출 형식입니다.")
        func_name = node.func.id
        func = _ALLOWED_FUNCS.get(func_name)
        if func is None:
            raise ValueError(f"지원하지 않는 함수입니다: {func_name}")
        args = [_eval_node(arg) for arg in node.args]
        return func(*args)

    raise ValueError("지원하지 않는 수식 형식입니다.")


def safe_calc(expression: str):
    expression = (expression or "").strip()
    if not expression:
        raise ValueError("계산식을 입력해주세요. 예: 2*(3+4)")

    tree = ast.parse(expression, mode="eval")
    return _eval_node(tree)


def main() -> int:
    expr = " ".join(sys.argv[1:]).strip()
    if not expr:
        print("❌ 사용법: python tools/calc.py <수식>")
        print("예: python tools/calc.py \"2*(3+4)\"")
        return 1

    try:
        result = safe_calc(expr)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        print(f"🧮 {expr} = {result}")
        return 0
    except ZeroDivisionError:
        print("❌ 0으로 나눌 수 없습니다.")
        return 1
    except Exception as exc:
        print(f"❌ 계산 실패: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
