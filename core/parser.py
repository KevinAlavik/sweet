from core.lexer import TokenType, LexerError
from abc import ABC, abstractmethod
from enum import Enum, auto

class ParserError(Exception):
    def __init__(self, message, line, column):
        super().__init__(f"Parser Error: Line {line}:{column}: {message}")

class BuiltinTypes(Enum):
    UInt = 0
    Char = 1
    InlineString = 2

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
        ctx.stack_types.append(BuiltinTypes.UInt)
        return [f"    push {self.value}"]

    def __str__(self):
        return f"Number({self.value})"

class String(ASTNode):
    def __init__(self, value):
        self.value = value

    def compile(self, ctx):
        label = ctx.add_string(self.value)
        ctx.stack_depth += 1
        ctx.stack_types.append(BuiltinTypes.InlineString)
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
        right_type = BuiltinTypes(ctx.stack_types.pop())
        left_type = BuiltinTypes(ctx.stack_types.pop())

        if right_type != BuiltinTypes.UInt or left_type != BuiltinTypes.UInt:
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

        ctx.stack_types.append(BuiltinTypes.UInt)
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
        typ = BuiltinTypes(ctx.stack_types[-1])
        code = []
        if typ in (BuiltinTypes.InlineString, BuiltinTypes.Char):
            ctx.stack_types.pop()
            ctx.stack_depth -= 1
            code += [
                "    pop rdi",
                "    push rbp",
                "    call print_str",
                "    pop rbp"
            ]
        else:
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
        ctx.stack_types.append(BuiltinTypes.String)
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
        rt = BuiltinTypes(ctx.stack_types.pop())
        lt = BuiltinTypes(ctx.stack_types.pop())

        if lt in (BuiltinTypes.InlineString, BuiltinTypes.Char) and rt in (BuiltinTypes.InlineString, BuiltinTypes.Char):
            ctx.stack_depth -= 2
            code += [
                "    pop rsi",
                "    pop rdi",
                "    push rbp",
                "    call compare_str",
                "    pop rbp",
                "    push rax"
            ]
            ctx.stack_types.append(BuiltinTypes.UInt)
            ctx.stack_depth += 1
        elif lt == BuiltinTypes.UInt and rt == BuiltinTypes.UInt:
            ctx.stack_depth -= 2
            code += [
                "    pop rsi",
                "    pop rdi",
                "    push rbp",
                "    call compare_int",
                "    pop rbp",
                "    push rax"
            ]
            ctx.stack_types.append(BuiltinTypes.UInt)
            ctx.stack_depth += 1
        else:
            raise Exception(f"Can't compare {lt} with {rt}")

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

        ctx.stack_types.append(BuiltinTypes.UInt)
        ctx.stack_depth += 1
        code.append("    push rax")

        return code

    def __str__(self):
        return f"Call({self.func}, {self.arg_count})"

class VarDef(ASTNode):
    def __init__(self, name, size, t):
        self.name = name
        self.size = size
        self.type = t

    def compile(self, ctx):
        label = f"{ctx.new_label()}"
        if not hasattr(ctx, "vars"):
            ctx.vars = {}

        ctx.vars[self.name] = [label, self.size, self.type]

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
    

class ArrayDef(ASTNode):
    def __init__(self, name, count, unit_size, base_type):
        self.name      = name
        self.count     = count
        self.unit_size = unit_size
        self.base_type = base_type
        self.size      = count * unit_size

    def compile(self, ctx):
        label = ctx.new_label()
        if not hasattr(ctx, "vars"):
            ctx.vars = {}
        ctx.vars[self.name] = [label, self.size, self.base_type, self.count]
        code = [
            f"    mov rdi, {self.size}",
            "    push rbp",
            "    call new",
            "    pop rbp",
            f"    mov [{label}], rax"
        ]
        return code

    def __str__(self):
        return f"ArrayDef({self.name}[{self.count}], base={self.base_type})"


class LoadVar(ASTNode):
    def __init__(self, name):
        self.name = name

    def compile(self, ctx):
        if not hasattr(ctx, "vars") or self.name not in ctx.vars:
            raise Exception(f"Var '{self.name}' not defined")
        lbl, size, t, *rest = ctx.vars[self.name]
        ctx.stack_depth  += 1
        ctx.stack_types.append(t)
        return [f"    mov rax, [{lbl}]", "    push rax"]

    def __str__(self):
        return f"LoadVar({self.name})"

class LoadVarIdx(ASTNode):
    def __init__(self, name, idx):
        self.name = name
        self.idx = idx

    def compile(self, ctx):
        if not hasattr(ctx, "vars") or self.name not in ctx.vars:
            raise Exception(f"Var '{self.name}' not defined")

        label, size_bits, var_type, *rest = ctx.vars[self.name]

        code = [
            "    xor rax, rax",
            f"    mov al, [{label} + {self.idx}]",
            "    push rax"
        ]

        ctx.stack_depth += 1
        ctx.stack_types.append(var_type)
        print("indexed variable with type "+ str(var_type))
        return code

    def __str__(self):
        return f"LoadVarIdx({self.name}, {self.idx})"

    
class StoreVar(ASTNode):
    def __init__(self, name):
        self.name = name

    def compile(self, ctx):
        if ctx.stack_depth < 1:
            raise Exception("StoreVar underflow")
        if not hasattr(ctx, "vars") or self.name not in ctx.vars:
            raise Exception(f"Var '{self.name}' not defined")
        lbl, size, t, count = ctx.vars[self.name]
        ctx.stack_depth -= 1
        val_type = ctx.stack_types.pop()
        code = ["    pop rax"]
        if val_type == BuiltinTypes.InlineString and t == BuiltinTypes.Char:
            print("memcpy")
            code += [f"    mov rsi, rax",     # src
                     f"    mov rdi, [{lbl}]", # dst
                     f"    mov rdx, {count}",
                     f"    call memcpy" ]
        else:
            code += [f"    mov [{lbl}], rax"]
        return code

    def __str__(self):
        return f"StoreVar({self.name})"

class Bang(ASTNode):
    def compile(self, ctx):
        if ctx.stack_depth == 0 or not ctx.stack_types:
            raise Exception("Stack underflow in Bang")
        top_type = ctx.stack_types.pop()
        ctx.stack_depth -= 1
        if top_type == BuiltinTypes.UInt:
            code = []
            code += ["    pop rax", "    test rax, rax", "    sete al", "    movzx rax, al", "    push rax"]
            ctx.stack_types.append(BuiltinTypes.UInt)
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
    
class BlockExpr(ASTNode):
    def __init__(self, expressions):
        self.expressions = expressions

    def compile(self, ctx):
        code = []
        for expr in self.expressions:
            code += expr.compile(ctx)
        return code

    def __str__(self):
        return f"BlockExpr({self.expressions})"

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

            if tok.type == TokenType.INTLIT:
                self.eat(TokenType.INTLIT)
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

                    condition_expr = self.parse_block(until_keywords={"do"})
                    if not condition_expr:
                        raise ParserError("No condition provided for loop", tok.line, tok.column)

                    self.eat(TokenType.KEYWORD)

                    loop_body = self.parse_block(until_keywords={"end"})
                    if self.current_token.type == TokenType.KEYWORD and self.current_token.value == "end":
                        self.eat(TokenType.KEYWORD)
                    else:
                        raise ParserError('Expected "end" after loop block', tok.line, tok.column)

                    block_stack.append(Loop(BlockExpr(condition_expr), loop_body))

                elif tok.value == "extern":
                    self.eat(TokenType.KEYWORD)
                    if self.current_token.type != TokenType.IDENTIFIER:
                        raise ParserError("Expected identifier after extern", tok.line, tok.column)
                    name = self.current_token.value
                    self.eat(TokenType.IDENTIFIER)
                    if self.current_token.type != TokenType.INTLIT:
                        raise ParserError("Expected argument count after extern name", tok.line, tok.column)
                    args = int(self.current_token.value)
                    self.eat(TokenType.INTLIT)
                    block_stack.append(Extern(name))
                    self.ctx.known_externs[name] = args

                elif tok.value == "var":
                    self.eat(TokenType.KEYWORD)
                    name = self.current_token.value; self.eat(TokenType.IDENTIFIER)
                    self.eat(TokenType.KEYWORD)
                    base = self.current_token.value
                    unit_size = self.ctx.type_sizes[self.ctx.type_map[base]]
                    base_type = self.ctx.type_map[base]
                    self.eat(TokenType.IDENTIFIER)

                    # array?
                    if self.current_token.type == TokenType.LBRACK:
                        self.eat(TokenType.LBRACK)
                        cnt = int(self.current_token.value); self.eat(TokenType.INTLIT)
                        self.eat(TokenType.RBRACK)
                        node = ArrayDef(name, cnt, unit_size, base_type)
                    else:
                        # scalar fallback
                        node = ArrayDef(name, 1, unit_size, base_type)

                    self.ctx.known_vars.append(name)
                    block_stack.append(node)

                    # inline init for arrays only
                    if isinstance(node, ArrayDef) and self.current_token.type == TokenType.STRING:
                        lit = self.current_token.value
                        if len(lit) > node.count:
                            raise ParserError(f"Literal too long for {name}[{node.count}]", tok.line, tok.column)
                        block_stack.append(String(lit))
                        self.eat(TokenType.STRING)

                elif tok.value == "set":
                    self.eat(TokenType.KEYWORD)
                    if self.current_token.type != TokenType.IDENTIFIER:
                        raise ParserError("Expected variable name after 'set'", tok.line, tok.column)
                    name = self.current_token.value
                    self.eat(TokenType.IDENTIFIER)
                    block_stack.append(StoreVar(name))
                else:
                    raise ParserError(f"Unexpected keyword: {tok.value}", tok.line, tok.column)

            elif tok.type == TokenType.IDENTIFIER:
                name = tok.value
                if name in self.ctx.known_externs:
                    self.eat(TokenType.IDENTIFIER)
                    arg_count = self.ctx.known_externs[name]
                    block_stack.append(Call(name, arg_count))
                elif name in self.ctx.known_vars:
                    self.eat(TokenType.IDENTIFIER)
                    if self.current_token.type == TokenType.LBRACK:
                        self.eat(TokenType.LBRACK)
                        idx = self.current_token.value
                        self.eat(TokenType.INTLIT)
                        print(f"Accessing variable {name} at idx {idx}")
                        self.eat(TokenType.RBRACK)
                        block_stack.append(LoadVarIdx(name, idx))
                    else:
                        block_stack.append(LoadVar(name))
                else:
                    raise ParserError(f"Unknown identifier: {name}. All known externs: {list(self.ctx.known_externs.keys())}", tok.line, tok.column)

            else:
                raise ParserError(f"Unexpected token {tok}", tok.line, tok.column)

        return block_stack

    def parse(self):
        return self.parse_block(until_keywords=set())