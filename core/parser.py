from core.lexer import TokenType, LexerError
from abc import ABC, abstractmethod
from enum import Enum, auto

class ParserError(Exception):
    def __init__(self, message, line, column):
        super().__init__(f"Parser Error: Line {line}:{column}: {message}")

class StackType(Enum):
    NUMBER = auto()
    STRING = auto()

class ASTNode(ABC):
    @abstractmethod
    def compile(self, ctx):
        pass

    def __repr__(self):
        return str(self)

class Number(ASTNode):
    def __init__(self, value):
        self.value = value

    def compile(self, ctx):
        ctx.stack_depth += 1
        ctx.stack_types.append(StackType.NUMBER)
        return [f"    push {self.value}"]

    def __str__(self):
        return f"Number({self.value})"

class String(ASTNode):
    def __init__(self, value):
        self.value = value

    def compile(self, ctx):
        label = ctx.add_string(self.value)
        ctx.stack_depth += 1
        ctx.stack_types.append(StackType.STRING)
        return [
            f"    lea rax, [{label}]",
            "    push rax"
        ]

    def __str__(self):
        return f'String("{self.value}")'

class BinaryOp(ASTNode):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

    def compile(self, ctx):
        code = []
        code += self.left.compile(ctx)
        code += self.right.compile(ctx)

        if len(ctx.stack_types) < 2:
            raise Exception("Stack underflow in BinaryOp")
        right_type = ctx.stack_types.pop()
        left_type = ctx.stack_types.pop()

        if right_type != StackType.NUMBER or left_type != StackType.NUMBER:
            raise Exception("Binary operations only supported on numbers")

        code += ["    pop rbx", "    pop rax"]
        if self.op == "+":
            code.append("    add rax, rbx")
        elif self.op == "-":
            code.append("    sub rax, rbx")
        elif self.op == "*":
            code.append("    imul rax, rbx")
        elif self.op == "/":
            code += ["    cqo", "    idiv rbx"]
        else:
            raise Exception(f"Unknown binary operator {self.op}")
        code += ["    push rax"]

        ctx.stack_types.append(StackType.NUMBER)
        ctx.stack_depth -= 1
        return code

    def __str__(self):
        return f"BinaryOp(op='{self.op}', left={self.left}, right={self.right})"

class Dup(ASTNode):
    def compile(self, ctx):
        if len(ctx.stack_types) < 1:
            raise Exception("Stack underflow in Dup")
        top_type = ctx.stack_types[-1]
        ctx.stack_depth += 1
        ctx.stack_types.append(top_type)
        return ["    pop rax", "    push rax", "    push rax"]

    def __str__(self):
        return "Dup()"

# Special builtin
class Print(ASTNode):
    def compile(self, ctx):
        if ctx.stack_depth == 0:
            raise Exception("Stack underflow in Print")

        code = []
        if ctx.stack_depth >= 1 and len(ctx.stack_types) >= 1:
            _type = ctx.stack_types[-1]
            if _type == StackType.STRING:
                ctx.stack_types.pop()
                ctx.stack_depth -= 1
                code += [
                    "    pop rdi",
                    "    call print_str"
                ]
                return code

        ctx.stack_types.pop()
        ctx.stack_depth -= 1
        code += [
            "    pop rdi",
            "    call print_int"
        ]
        return code

    def __str__(self):
        return "Print()"

class Input(ASTNode):
    def __str__(self):
        return "Input()"
    
    def compile(self, ctx):
        code = []
        code += [
            "    call stdin_getline",
            "    push rax"
        ]
        ctx.stack_types.append(StackType.STRING)
        ctx.stack_depth += 1
        return code

class Compare(ASTNode):
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def compile(self, ctx):
        code = []
        code += self.left.compile(ctx)
        code += self.right.compile(ctx)

        if len(ctx.stack_types) < 2:
            raise Exception("Stack underflow in Compare")
        right_type = ctx.stack_types.pop()
        left_type = ctx.stack_types.pop()

        if left_type == StackType.STRING and right_type == StackType.STRING:
            ctx.stack_depth -= 2
            code += [
                "    pop rsi",
                "    pop rdi",
                "    push rbp",
                "    call compare_str"
            ]
            code += ["    push rax"]
            ctx.stack_types.append(StackType.NUMBER)
            ctx.stack_depth += 1
        elif left_type == StackType.NUMBER and right_type == StackType.NUMBER:
            ctx.stack_depth -= 2
            code += [
                "    pop rsi",
                "    pop rdi",
                "    push rbp",
                "    call compare_int"
            ]
            code += [
                "    pop rbp",
                "    push rax"
            ]
            ctx.stack_types.append(StackType.NUMBER)
            ctx.stack_depth += 1
        else:
            raise Exception(f"Cant compare a {left_type} and a {right_type}")
        return code

    def __str__(self):
        return f"Compare(left={self.left}, right={self.right})"

class IfElse(ASTNode):
    def __init__(self, condition, if_body, else_body=None):
        self.condition = condition
        self.if_body = if_body
        self.else_body = else_body

    def compile(self, ctx):
        code = []
        code += self.condition.compile(ctx)
        if ctx.stack_depth == 0:
            raise Exception("Stack underflow in If condition")
        code += ["    pop rax"]
        ctx.stack_depth -= 1
        else_label = ctx.new_label()
        end_label = ctx.new_label()

        code += [
            "    cmp rax, 0",
            f"    je {else_label}"
        ]
        for node in self.if_body:
            code += node.compile(ctx)
        code += [f"    jmp {end_label}"]
        code += [f"{else_label}:"]
        if self.else_body:
            for node in self.else_body:
                code += node.compile(ctx)
        code += [f"{end_label}:"]
        return code

    def __str__(self):
        else_str = f", else_body={self.else_body}" if self.else_body else ""
        return f"IfElse(condition={self.condition}, if_body={self.if_body}{else_str})"

class Extern(ASTNode):
    def __init__(self, ext):
        self.ext = ext
    
    def compile(self, ctx):
        code = [
            f"extern {self.ext}"
        ]
        return code;    
    
    def __str__(self):
        return f"Extern(ext={self.ext})"

class Call(ASTNode):
    def __init__(self, func, arg_count):
        self.func = func
        self.arg_count = arg_count
    
    def compile(self, ctx):
        code = []
        arg_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]

        if ctx.stack_depth < self.arg_count:
            raise Exception(f"Stack underflow in Call to {self.func}")

        for i in reversed(range(self.arg_count)):
            code.append(f"    pop {arg_regs[i]}")
            ctx.stack_types.pop()
            ctx.stack_depth -= 1

        code.append(f"    push rbp")
        code.append(f"    call {self.func}")
        code.append(f"    pop rbp")

        ctx.stack_types.append(StackType.NUMBER)
        ctx.stack_depth += 1
        code.append("    push rax")

        return code

    def __str__(self):
        return f"Call(func={self.func}, arg_count={self.arg_count})"


class Parser:
    def __init__(self, lexer, ctx):
        self.lexer = lexer
        self.current_token = self.lexer.get_next_token()
        self.ctx = ctx

    def eat(self, type_):
        if self.current_token.type == type_:
            self.current_token = self.lexer.get_next_token()
        else:
            raise ParserError(f"Expected {type_}, got {self.current_token.type}",
                              self.current_token.line, self.current_token.column)

    def parse_block(self, until_keywords):
        block_stack = []
        while self.current_token.type != TokenType.EOF:
            tok = self.current_token
            if tok.type == TokenType.KEYWORD and tok.value in until_keywords:
                break

            if tok.type == TokenType.NUMBER:
                self.eat(TokenType.NUMBER)
                block_stack.append(Number(tok.value))

            elif tok.type in (TokenType.PLUS, TokenType.MINUS, TokenType.MULTIPLY, TokenType.DIVIDE):
                self.eat(tok.type)
                if len(block_stack) < 2:
                    raise ParserError("Not enough operands for binary operator", tok.line, tok.column)
                right = block_stack.pop()
                left = block_stack.pop()
                block_stack.append(BinaryOp(tok.value, left, right))

            elif tok.type == TokenType.STRING:
                self.eat(TokenType.STRING)
                block_stack.append(String(tok.value))

            elif tok.type == TokenType.COMPARE:
                self.eat(TokenType.COMPARE)
                if len(block_stack) < 2:
                    raise ParserError("Not enough operands for compare operator", tok.line, tok.column)
                right = block_stack.pop()
                left = block_stack.pop()
                block_stack.append(Compare(left, right))

            elif tok.type == TokenType.KEYWORD:
                if tok.value == "dup":
                    self.eat(TokenType.KEYWORD)
                    block_stack.append(Dup())

                elif tok.value == "print":
                    self.eat(TokenType.KEYWORD)
                    block_stack.append(Print())

                elif tok.value == "input":
                    self.eat(TokenType.KEYWORD)
                    block_stack.append(Input())

                elif tok.value == "if":
                    self.eat(TokenType.KEYWORD)
                    if len(block_stack) < 1:
                        raise ParserError("Not enough operands for if condition", tok.line, tok.column)
                    condition = block_stack.pop()
                    if_body = self.parse_block(until_keywords={"else", "end"})
                    else_body = None
                    if self.current_token.type == TokenType.KEYWORD and self.current_token.value == "else":
                        self.eat(TokenType.KEYWORD)
                        else_body = self.parse_block(until_keywords={"end"})
                    if self.current_token.type == TokenType.KEYWORD and self.current_token.value == "end":
                        self.eat(TokenType.KEYWORD)
                    else:
                        raise ParserError("Expected \"end\" after if block", tok.line, tok.column)
                    block_stack.append(IfElse(condition, if_body, else_body))
                elif tok.value == "extern":
                    self.eat(TokenType.KEYWORD)
                    if self.current_token.type != TokenType.IDENTIFIER:
                        raise ParserError("Expected identifier after extern", tok.line, tok.column)
                    name = self.current_token.value
                    self.eat(TokenType.IDENTIFIER)
                    if self.current_token.type != TokenType.NUMBER:
                        raise ParserError("Expected argument count after extern name", tok.line, tok.column)
                    args = int(self.current_token.value)
                    self.eat(TokenType.NUMBER)
                    block_stack.append(Extern(name))
                    self.ctx.known_externs[name] = args
                else:
                    raise ParserError(f"Unsupported keyword: {tok.value}", tok.line, tok.column)
            elif tok.type == TokenType.IDENTIFIER:
                name = tok.value
                if name in self.ctx.known_externs:
                    self.eat(TokenType.IDENTIFIER)
                    arg_count = self.ctx.known_externs[name]
                    block_stack.append(Call(name, arg_count))
                else:
                    raise ParserError(f"Unknown identifier: {name}. All known externs: {list(self.ctx.known_externs.keys())}", tok.line, tok.column)
            else:
                raise ParserError(f"Unexpected token {tok}", tok.line, tok.column)

        return block_stack

    def parse(self):
        return self.parse_block(until_keywords=set())
