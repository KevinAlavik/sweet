#include <stdio.h>

extern void sweet_main(void);

void print_int(long val) { printf("%d", val); }
void print_str(const char *str, long len) { printf("%.*s", len, str); }

int main() {
  sweet_main();
  return 0;
}
