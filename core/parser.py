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
        return f"BinaryOp({self.op}, {self.left}, {self.right})"

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
                    "    push rbp",
                    "    call print_str",
                    "    pop rbp"
                ]
                return code

        ctx.stack_types.pop()
        ctx.stack_depth -= 1
        code += [
            "    pop rdi",
            "    push rbp",
            "    call print_int",
            "    pop rbp"
        ]
        return code

    def __str__(self):
        return "Print()"

class Input(ASTNode):
    def compile(self, ctx):
        code = []
        code += [
            "    push rbp",
            "    call stdin_getline",
            "    pop rbp",
            "    push rax"
        ]
        ctx.stack_types.append(StackType.STRING)
        ctx.stack_depth += 1
        return code
    
    def __str__(self):
        return "Input()"


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
        return f"Compare({self.left}, {self.right})"

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
        return f"IfElse({self.condition}, {self.if_body}{else_str})"

class Extern(ASTNode):
    def __init__(self, ext):
        self.ext = ext
    
    def compile(self, ctx):
        code = [
            f"extern {self.ext}"
        ]
        return code;    
    
    def __str__(self):
        return f"Extern({self.ext})"

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
        return f"Call({self.func}, {self.arg_count})"

class VarDef(ASTNode):
    def __init__(self, name, size):
        self.name = name
        self.size = size

    def compile(self, ctx):
        label = f"{ctx.new_label()}"
        if not hasattr(ctx, "vars"):
            ctx.vars = {}
        if not hasattr(ctx, "var_sizes"):
            ctx.var_sizes = {}

        ctx.vars[self.name] = label
        ctx.var_sizes[self.name] = self.size

        code = [
            f"    mov rdi, {self.size}",
            f"    push rbp",
            f"    call new",
            f"    pop rbp",
            f"    mov [{label}], rax"
        ]
        return code

    def __str__(self):
        return f"VarDef({self.name}, {self.size})"

class LoadVar(ASTNode):
    def __init__(self, name):
        self.name = name

    def compile(self, ctx):
        if not hasattr(ctx, "vars") or self.name not in ctx.vars:
            raise Exception(f"Variable '{self.name}' not defined")
        label = ctx.vars[self.name]
        ctx.stack_depth += 1
        ctx.stack_types.append(StackType.NUMBER)
        return [
            f"    mov rax, [{label}]",
            f"    push rax"
        ]

    def __str__(self):
        return f"LoadVar({self.name})"
    
class StoreVar(ASTNode):
    def __init__(self, name):
        self.name = name

    def compile(self, ctx):
        if ctx.stack_depth < 1:
            raise Exception("Stack underflow in StoreVar")
        if not hasattr(ctx, "vars") or self.name not in ctx.vars:
            raise Exception(f"Variable '{self.name}' not defined")
        label = ctx.vars[self.name]
        ctx.stack_depth -= 1
        ctx.stack_types.pop()
        return [
            "    pop rax",
            f"    mov [{label}], rax"
        ]

    def __str__(self):
        return f"StoreVar({self.name})"

class Bang(ASTNode):
    def compile(self, ctx):
        if ctx.stack_depth == 0 or not ctx.stack_types:
            raise Exception("Stack underflow in Bang")
        top_type = ctx.stack_types.pop()
        ctx.stack_depth -= 1
        if top_type == StackType.NUMBER:
            code = []
            code += ["    pop rax", "    test rax, rax", "    sete al", "    movzx rax, al", "    push rax"]
            ctx.stack_types.append(StackType.NUMBER)
            ctx.stack_depth += 1
            return code
        raise Exception("Bang operator only supported for numbers")
    def __str__(self):
        return "Bang()"

class BangWrapper(ASTNode):
    def __init__(self, node):
        self.node = node
    def compile(self, ctx):
        code = []
        code += self.node.compile(ctx)
        code += Bang().compile(ctx)
        return code
    def __str__(self):
        return f"BangWrapper({self.node})"

class Loop(ASTNode):
    def __init__(self, condition, body):
        self.condition = condition
        self.body = body

    def compile(self, ctx):
        code = []
        loop_label = ctx.new_label()
        end_label = ctx.new_label()

        code += [f"{loop_label}:"]        
        code += self.condition.compile(ctx)
        if ctx.stack_depth == 0:
            raise Exception("Stack underflow in Loop condition")
        code += ["    pop rax"]
        ctx.stack_depth -= 1
        ctx.stack_types.pop()

        code += [
            "    cmp rax, 0",
            f"    je {end_label}"
        ]

        for node in self.body:
            code += node.compile(ctx)
        code += [f"    jmp {loop_label}"]
        code += [f"{end_label}:"]
        return code

    def __str__(self):
        return f"Loop({self.condition}, {self.body})"

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
                node = Number(tok.value)
                if self.current_token.type == TokenType.BANG:
                    self.eat(TokenType.BANG)
                    node = BangWrapper(node)
                block_stack.append(node)

            elif tok.type in (TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH):
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

            elif tok.type == TokenType.BANG:
                self.eat(TokenType.BANG)
                block_stack.append(Bang())

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

                elif tok.value == "loop":
                    self.eat(TokenType.KEYWORD)
                    condition = []
                    while not (self.current_token.type == TokenType.KEYWORD and self.current_token.value == "do"):
                        if self.current_token.type == TokenType.IDENTIFIER:
                            if self.current_token.value in self.ctx.known_vars:
                                condition.append(LoadVar(self.current_token.value))
                                self.eat(TokenType.IDENTIFIER)
                            else:
                                raise ParserError(f"Unknown variable: {self.current_token.value}", tok.line, tok.column)
                        elif self.current_token.type == TokenType.NUMBER:
                            condition.append(Number(self.current_token.value))
                            self.eat(TokenType.NUMBER)
                        elif self.current_token.type == TokenType.COMPARE:
                            self.eat(TokenType.COMPARE)
                            if len(condition) < 2:
                                raise ParserError("Not enough operands for compare in loop condition", tok.line, tok.column)
                            right = condition.pop()
                            left = condition.pop()
                            condition.append(Compare(left, right))
                        elif self.current_token.type == TokenType.BANG:
                            self.eat(TokenType.BANG)
                            if not condition:
                                raise ParserError("No operand for bang in loop condition", tok.line, tok.column)
                            node = condition.pop()
                            condition.append(BangWrapper(node))
                        else:
                            raise ParserError(f"Unexpected token in loop condition: {self.current_token}", tok.line, tok.column)
                    if not condition:
                        raise ParserError("No condition provided for loop", tok.line, tok.column)
                    if len(condition) > 1:
                        raise ParserError("Multiple conditions in loop", tok.line, tok.column)
                    condition = condition[0]
                    self.eat(TokenType.KEYWORD)
                    loop_body = self.parse_block(until_keywords={"end"})
                    if self.current_token.type == TokenType.KEYWORD and self.current_token.value == "end":
                        self.eat(TokenType.KEYWORD)
                    else:
                        raise ParserError("Expected \"end\" after loop block", tok.line, tok.column)
                    block_stack.append(Loop(condition, loop_body))

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

                elif tok.value == "var":
                    self.eat(TokenType.KEYWORD)
                    if self.current_token.type != TokenType.IDENTIFIER:
                        raise ParserError("Expected identifier after var", tok.line, tok.column)
                    name = self.current_token.value
                    self.eat(TokenType.IDENTIFIER)
                    if self.current_token.type != TokenType.NUMBER:
                        raise ParserError("Expected variable size after variable name", tok.line, tok.column)
                    size = int(self.current_token.value)
                    self.eat(TokenType.NUMBER)
                    block_stack.append(VarDef(name, size))
                    self.ctx.known_vars.append(name)

                elif tok.value == "set":
                    self.eat(TokenType.KEYWORD)
                    if self.current_token.type != TokenType.IDENTIFIER:
                        raise ParserError("Expected variable name after 'set'", tok.line, tok.column)
                    name = self.current_token.value
                    self.eat(TokenType.IDENTIFIER)
                    block_stack.append(StoreVar(name))

                elif tok.value == "do" or tok.value == "end":
                    raise ParserError(f"Unexpected keyword: {tok.value}", tok.line, tok.column)

                else:
                    raise ParserError(f"Unsupported keyword: {tok.value}", tok.line, tok.column)

            elif tok.type == TokenType.IDENTIFIER:
                name = tok.value
                if name in self.ctx.known_externs:
                    self.eat(TokenType.IDENTIFIER)
                    arg_count = self.ctx.known_externs[name]
                    block_stack.append(Call(name, arg_count))
                elif name in self.ctx.known_vars:
                    self.eat(TokenType.IDENTIFIER)
                    block_stack.append(LoadVar(name))
                else:
                    raise ParserError(f"Unknown identifier: {name}. All known externs: {list(self.ctx.known_externs.keys())}", tok.line, tok.column)

            else:
                raise ParserError(f"Unexpected token {tok}", tok.line, tok.column)

        return block_stack

    def parse(self):
        return self.parse_block(until_keywords=set())