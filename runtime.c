#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stddef.h>
#include <stdalign.h>

#ifdef LIBSW_DEBUG
#define DEBUG_LOG(fmt, ...) \
    fprintf(stderr, "libsw: " fmt "\n", ##__VA_ARGS__)
#else
#define DEBUG_LOG(...) (void)0
#endif

#define ARENA_BLOCK_SIZE 4096

typedef struct ArenaBlock
{
    struct ArenaBlock *next;
    size_t used;
    size_t capacity;
    alignas(max_align_t) unsigned char data[];
} ArenaBlock;

typedef struct
{
    ArenaBlock *head;
} Arena;

static Arena global_arena = {NULL};

static ArenaBlock *arena_block_new(size_t min_capacity)
{
    size_t block_size = ARENA_BLOCK_SIZE;
    if (min_capacity + sizeof(ArenaBlock) > block_size)
    {
        block_size = min_capacity + sizeof(ArenaBlock);
    }
    ArenaBlock *block = malloc(block_size);
    if (!block)
    {
        fprintf(stderr, "libsw: arena block allocation failed\n");
        exit(EXIT_FAILURE);
    }
    block->next = NULL;
    block->used = 0;
    block->capacity = block_size - sizeof(ArenaBlock);
    DEBUG_LOG("arena: new block %p with %zu bytes", (void *)block, block->capacity);
    return block;
}

void arena_init(Arena *arena)
{
    if (arena->head)
        return;
    arena->head = arena_block_new(ARENA_BLOCK_SIZE - sizeof(ArenaBlock));
    DEBUG_LOG("arena: initialized");
}

void *arena_alloc(Arena *arena, size_t size)
{
    size_t align = alignof(max_align_t);
    size = (size + (align - 1)) & ~(align - 1);

    if (!arena->head)
    {
        arena_init(arena);
    }

    ArenaBlock *block = arena->head;

    while (block)
    {
        size_t remaining = block->capacity - block->used;
        if (size <= remaining)
        {
            void *ptr = block->data + block->used;
            block->used += size;
            DEBUG_LOG("arena: allocated %zu bytes at %p", size, ptr);
            return ptr;
        }
        if (!block->next)
        {
            block->next = arena_block_new(size > ARENA_BLOCK_SIZE ? size : ARENA_BLOCK_SIZE);
        }
        block = block->next;
    }

    fprintf(stderr, "libsw: arena allocation failed for size %zu\n", size);
    exit(EXIT_FAILURE);
}

void arena_cleanup(Arena *arena)
{
    ArenaBlock *block = arena->head;
    int count = 0;
    while (block)
    {
        ArenaBlock *next = block->next;
        free(block);
        block = next;
        count++;
    }
    arena->head = NULL;
    DEBUG_LOG("arena: cleaned up %d blocks", count);
}

char *stdin_getline(void)
{
    size_t capacity = 64;
    size_t length = 0;
    char *buffer = arena_alloc(&global_arena, capacity);
    if (!buffer)
        return NULL;

    int ch;
    while ((ch = fgetc(stdin)) != EOF && ch != '\n')
    {
        if (length + 1 >= capacity)
        {
            size_t new_capacity = capacity * 2;
            char *new_buffer = arena_alloc(&global_arena, new_capacity);
            memcpy(new_buffer, buffer, length);
            buffer = new_buffer;
            capacity = new_capacity;
        }
        buffer[length++] = (char)ch;
    }
    if (length == 0 && ch == EOF)
    {
        return NULL;
    }
    buffer[length] = '\0';
    DEBUG_LOG("stdin_getline: read \"%s\"", buffer);
    return buffer;
}

void print_int(long val)
{
    printf("%ld", val);
}

void print_str(const char *str)
{
    printf("%s", str);
}

uintptr_t compare_int(uintptr_t a, uintptr_t b)
{
    uintptr_t result = (a == b);
    DEBUG_LOG("int@compare(%lu, %lu): %s", (unsigned long)a, (unsigned long)b, result ? "true" : "false");
    return result;
}

uintptr_t compare_str(const char *str1, const char *str2)
{
    if (!str1 || !str2)
        return 0;
    if (strlen(str1) != strlen(str2))
        return 0;
    int result = strncmp(str1, str2, strlen(str1)) == 0;
    DEBUG_LOG("string@compare(%s, %s): %s", str1, str2, result ? "true" : "false");
    return result;
}

void *new(size_t size)
{
    return arena_alloc(&global_arena, size);
}

extern void sweet_main(void);

int main(void)
{
    DEBUG_LOG("libsw runtime v2.0");
    arena_init(&global_arena);
    sweet_main();
    arena_cleanup(&global_arena);
    return 0;
}
