from enum import Enum, auto

class TokenType(Enum):
    NUMBER = auto()
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    COMPARE = auto()
    STRING = auto()
    KEYWORD = auto()
    IDENTIFIER = auto()
    EOF = auto()

token_map = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.MULTIPLY,
    "/": TokenType.DIVIDE,
    "?": TokenType.COMPARE,
}

keywords = {"if", "else", "end", "dup", "print", "input", "extern"}

class Token:
    def __init__(self, type_, value, line, column):
        self.type = type_
        self.value = value
        self.line = line
        self.column = column

    def __str__(self):
        return f"Token({self.type}, {self.value}, line={self.line}, col={self.column})"

    def __repr__(self):
        return self.__str__()

class LexerError(Exception):
    def __init__(self, message, line, column):
        super().__init__(f"Lexer Error: Line {line}:{column}: {message}")

class Lexer:
    def __init__(self, src):
        self.src = src
        self.pos = 0
        self.line = 1
        self.column = 1
        self.current_char = self.src[self.pos] if self.src else None

    def advance(self):
        if self.current_char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.pos += 1
        self.current_char = self.src[self.pos] if self.pos < len(self.src) else None

    def skip_whitespace(self):
        while self.current_char is not None and self.current_char.isspace():
            self.advance()

    def number(self):
        result = ""
        start_line, start_column = self.line, self.column
        while self.current_char is not None and self.current_char.isdigit():
            result += self.current_char
            self.advance()
        return Token(TokenType.NUMBER, int(result), start_line, start_column)

    def get_next_token(self):
        while self.current_char is not None:
            if self.current_char.isspace():
                self.skip_whitespace()
                continue

            start_line, start_column = self.line, self.column

            # Handle single-line comments
            if self.current_char == "/" and self.pos + 1 < len(self.src) and self.src[self.pos + 1] == "/":
                self.advance()  # consume first /
                self.advance()  # consume second /
                while self.current_char is not None and self.current_char != "\n":
                    self.advance()
                continue

            # Handle multi-line comments
            if self.current_char == "/" and self.pos + 1 < len(self.src) and self.src[self.pos + 1] == "*":
                self.advance()  # consume first /
                self.advance()  # consume *
                while self.current_char is not None:
                    if self.current_char == "*" and self.pos + 1 < len(self.src) and self.src[self.pos + 1] == "/":
                        self.advance()  # consume *
                        self.advance()  # consume /
                        break
                    self.advance()
                continue

            if self.current_char.isdigit():
                return self.number()

            if self.current_char in token_map:
                tok_type = token_map[self.current_char]
                char = self.current_char
                self.advance()
                return Token(tok_type, char, start_line, start_column)

            if self.current_char == "\"":
                self.advance()
                start_pos = self.pos
                while self.current_char is not None and self.current_char != "\"":
                    self.advance()
                if self.current_char == "\"":
                    self.advance()
                    return Token(TokenType.STRING, self.src[start_pos:self.pos-1], start_line, start_column)
                else:
                    raise LexerError("Unterminated string literal", start_line, start_column)

            if self.current_char.isalpha():
                start_pos = self.pos
                while (
                    self.current_char is not None and
                    (self.current_char.isalnum() or self.current_char in "_-")
                ):
                    self.advance()
                word = self.src[start_pos:self.pos]
                if word in keywords:
                    return Token(TokenType.KEYWORD, word, start_line, start_column)
                else:
                    return Token(TokenType.IDENTIFIER, word, start_line, start_column)  
            raise LexerError(f"Unknown character: {self.current_char}", start_line, start_column)
        return Token(TokenType.EOF, None, self.line, self.column)

    def lex(self):
        tokens = []
        try:
            while True:
                token = self.get_next_token()
                tokens.append(token)
                if token.type == TokenType.EOF:
                    break
            return tokens
        except LexerError as e:
            print(e)