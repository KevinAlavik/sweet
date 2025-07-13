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
    char *buffer = malloc(capacity);

    if (!buffer)
    {
        DEBUG_LOG("stdin_getline: allocation failed");
        return NULL;
    }

    int ch;
    while ((ch = fgetc(stdin)) != EOF && ch != '\n')
    {
        if (length + 1 >= capacity)
        {
            capacity *= 2;
            char *new_buffer = realloc(buffer, capacity);
            if (!new_buffer)
            {
                free(buffer);
                DEBUG_LOG("stdin_getline: reallocation failed");
                return NULL;
            }
            buffer = new_buffer;
        }
        buffer[length++] = (char)ch;
    }

    buffer[length] = '\0';
    DEBUG_LOG("stdin_getline: read \"%s\"", buffer);
    return buffer;
}

void c_func(const char *msg)
{
    printf("%s", msg);
}

int main(void)
{
    DEBUG_LOG("libsw runtime v1.0");
    sweet_main();
    return 0;
}
