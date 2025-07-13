#include <stdio.h>
#include <string.h>
#include <stdint.h>

extern void sweet_main(void);

void print_int(long val) { printf("%d", val); }
void print_str(const char *str) { printf("%s", str); }

uintptr_t compare_int(uintptr_t a, uintptr_t b)
{
    return a == b;
}

uintptr_t compare_str(const char *str1, const char *str2)
{
    if (strlen(str1) != strlen(str2))
        return 0;
    return strncmp(str1, str2, strlen(str1)) == 0;
}

int main()
{
    sweet_main();
    return 0;
}
