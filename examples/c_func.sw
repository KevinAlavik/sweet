/*===============================*/
/* Sweet hello world from C      */
/*===============================*/

// man write 2
extern write 3 // write takes 3 args, and the sweet compiler is so stupid we have to provide the count
1 "Hello, World!\n" 13 write

// Ensure newline
"\n"print

// Check if it returned 13 (to check if it was successful)
13 ? if
    "Successfully called write() from sweet\n"print
else
    "Failed to call write() from sweet\n"print
end