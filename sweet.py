#!/bin/env python3
from enum import Enum, auto
import sys


class TokenType(Enum):
    NUMBER = auto()
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    KEYWORD = auto()
    EOF = auto()
    COMPARE = auto()

    def __str__(self):
        return self.name

token_map = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.MULTIPLY,
    "/": TokenType.DIVIDE,
    "?": TokenType.COMPARE,
}

keywords = {"if", "else", "end", "dup"}

class Token:
    def __init__(self, type_, value):
        self.type = type_
        self.value = value
    
    def __str__(self):
        return f'Token({self.type}, {self.value})'
    
    def __repr__(self):
        return self.__str__()

class Lexer:
    def __init__(self, src):
        self.src = src
        self.pos = 0
        self.current_char = self.src[self.pos] if self.src else None
    
    def advance(self):
        self.pos += 1
        if self.pos < len(self.src):
            self.current_char = self.src[self.pos]
        else:
            self.current_char = None
    
    def skip_whitespace(self):
        while self.current_char is not None and self.current_char.isspace():
            self.advance()
    
    def number(self):
        result = ''
        while self.current_char is not None and self.current_char.isdigit():
            result += self.current_char
            self.advance()
        return Token(TokenType.NUMBER, int(result))

    def get_next_token(self):
        while self.current_char is not None:
            if self.current_char.isspace():
                self.skip_whitespace()
                continue
            
            if self.current_char.isdigit():
                return self.number()
            
            if self.current_char in token_map:
                token_type = token_map[self.current_char]
                self.advance()
                return Token(token_type, self.current_char)
            
            if self.current_char.isalpha():
                start_pos = self.pos
                while self.current_char is not None and self.current_char.isalnum():
                    self.advance()
                word = self.src[start_pos:self.pos]
                if word in keywords:
                    return Token(TokenType.KEYWORD, word)
                else:
                    raise Exception(f'Unknown keyword: {word}')
                
            raise Exception(f'Unknown character: {self.current_char}')
        return Token(TokenType.EOF, None)

class Interpreter:
    def __init__(self, lexer):
        self.lexer = lexer
        self.stack = []
        self.current_token = self.lexer.get_next_token()

    def error(self, msg='Syntax error'):
        raise Exception(msg)

    def eat(self, expected_type):
        if self.current_token.type == expected_type:
            self.current_token = self.lexer.get_next_token()
        else:
            self.error(f"Expected {expected_type}, got {self.current_token.type}")

    def apply_operator(self, op_func, symbol):
        if len(self.stack) < 2:
            self.error(f"Not enough values on stack for '{symbol}'")
        
        b = self.stack.pop()
        a = self.stack.pop()
        result = op_func(a, b)
        self.stack.append(result)

    def skip_to_else_or_end(self):
        depth = 1
        while depth > 0:
            token = self.lexer.get_next_token()
            if token.type == TokenType.KEYWORD:
                if token.value == "if":
                    depth += 1
                elif token.value == "end":
                    depth -= 1
                elif token.value == "else" and depth == 1:
                    # Found matching else at same nesting level
                    break
            elif token.type == TokenType.EOF:
                self.error("Unmatched 'if'")
        self.current_token = self.lexer.get_next_token()

    def skip_to_end(self):
        depth = 1
        while depth > 0:
            token = self.lexer.get_next_token()
            if token.type == TokenType.KEYWORD:
                if token.value == "if":
                    depth += 1
                elif token.value == "end":
                    depth -= 1
            elif token.type == TokenType.EOF:
                self.error("Unmatched 'else'")
        self.current_token = self.lexer.get_next_token()

    def process_token(self, token):
        if token.type == TokenType.NUMBER:
            self.stack.append(token.value)
            self.eat(TokenType.NUMBER)

        elif token.type == TokenType.PLUS:
            self.eat(TokenType.PLUS)
            self.apply_operator(lambda a, b: a + b, '+')
        elif token.type == TokenType.MINUS:
            self.eat(TokenType.MINUS)
            self.apply_operator(lambda a, b: a - b, '-')
        elif token.type == TokenType.MULTIPLY:
            self.eat(TokenType.MULTIPLY)
            self.apply_operator(lambda a, b: a * b, '*')
        elif token.type == TokenType.DIVIDE:
            self.eat(TokenType.DIVIDE)
            self.apply_operator(lambda a, b: a / b, '/')
        elif token.type == TokenType.COMPARE:
            self.eat(TokenType.COMPARE)
            if len(self.stack) < 2:
                self.error("Not enough values on stack for '?'")
            b = self.stack.pop()
            a = self.stack.pop()
            result = 1 if a == b else 0
            self.stack.append(result)

        elif token.type == TokenType.KEYWORD:
            if token.value == "if":
                self.eat(TokenType.KEYWORD)
                condition = self.stack.pop() if self.stack else 0
                if not condition:
                    self.skip_to_else_or_end()
            elif token.value == "else":
                self.eat(TokenType.KEYWORD)
                self.skip_to_end()
            elif token.value == "end":
                self.eat(TokenType.KEYWORD)
            elif token.value == "dup":
                self.eat(TokenType.KEYWORD)
                if not self.stack:
                    self.error("Stack is empty for 'dup'")
                self.stack.append(self.stack[-1])
            else:
                self.error(f"Unknown keyword: {token.value}")
        else:
            self.error(f"Unexpected token: {token}")

    def interpret(self):
        while self.current_token.type != TokenType.EOF:
            self.process_token(self.current_token)
        return self.stack

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input file>")
        sys.exit(1)

    with open(sys.argv[1], 'r') as f:
        src = f.read()

    lexer = Lexer(src)
    interpreter = Interpreter(lexer)
    print(interpreter.interpret())
    
if __name__ == "__main__":
    main()