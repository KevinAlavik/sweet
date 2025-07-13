#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

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
    char data[ARENA_BLOCK_SIZE - sizeof(struct ArenaBlock *) - sizeof(size_t)];
} ArenaBlock;

static ArenaBlock *arena_head = NULL;

void arena_alloc_init(void)
{
    arena_head = malloc(sizeof(ArenaBlock));
    if (!arena_head)
    {
        fprintf(stderr, "libsw: arena_alloc_init failed\n");
        exit(1);
    }
    arena_head->next = NULL;
    arena_head->used = 0;
    DEBUG_LOG("arena: initialized with %d bytes", ARENA_BLOCK_SIZE);
}

void *arena_alloc_new(uintptr_t size)
{
    if (!arena_head)
        arena_alloc_init();

    size = (size + 7) & ~((uintptr_t)7);

    ArenaBlock *block = arena_head;
    while (1)
    {
        size_t remaining = sizeof(block->data) - block->used;
        if (size <= remaining)
        {
            void *ptr = block->data + block->used;
            block->used += size;
            DEBUG_LOG("arena: allocated %lu bytes at %p", (unsigned long)size, ptr);
            return ptr;
        }
        if (!block->next)
        {
            block->next = malloc(sizeof(ArenaBlock));
            if (!block->next)
            {
                fprintf(stderr, "libsw: arena_alloc_new failed\n");
                exit(1);
            }
            block->next->next = NULL;
            block->next->used = 0;
            DEBUG_LOG("arena: added new block");
        }
        block = block->next;
    }
}

void arena_alloc_cleanup(void)
{
    ArenaBlock *block = arena_head;
    int count = 0;
    while (block)
    {
        ArenaBlock *next = block->next;
        free(block);
        block = next;
        count++;
    }
    arena_head = NULL;
    DEBUG_LOG("arena: cleaned up %d blocks", count);
}

// RUNTIME API
extern void sweet_main(void);

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
    size_t len1 = strlen(str1);
    size_t len2 = strlen(str2);

    if (len1 != len2)
    {
        DEBUG_LOG("string@compare(%s, %s): false (length mismatch)", str1, str2);
        return 0;
    }

    int result = strncmp(str1, str2, len1) == 0;
    DEBUG_LOG("string@compare(%s, %s): %s", str1, str2, result ? "true" : "false");
    return result;
}

char *stdin_getline(void)
{
    size_t capacity = 64;
    size_t length = 0;

    char *buffer = arena_alloc_new(capacity);
    if (!buffer)
    {
        DEBUG_LOG("stdin_getline: arena allocation failed");
        return NULL;
    }

    int ch;
    while ((ch = fgetc(stdin)) != EOF && ch != '\n')
    {
        if (length + 1 >= capacity)
        {
            size_t new_capacity = capacity * 2;
            char *new_buffer = arena_alloc_new(new_capacity);
            if (!new_buffer)
            {
                DEBUG_LOG("stdin_getline: arena reallocation failed");
                return NULL;
            }

            memcpy(new_buffer, buffer, length);
            buffer = new_buffer;
            capacity = new_capacity;
        }

        buffer[length++] = (char)ch;
    }

    buffer[length] = '\0';
    DEBUG_LOG("stdin_getline: read \"%s\"", buffer);
    return buffer;
}

void *new(uintptr_t size)
{
    return arena_alloc_new(size);
}

int main(void)
{
    DEBUG_LOG("libsw runtime v1.0");
    arena_alloc_init();
    sweet_main();
    arena_alloc_cleanup();
    return 0;
}
