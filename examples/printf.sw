/*===============================*/
/* Sweet prinf from C            */
/*===============================*/
extern printf 2
"Hello, %s!\n" "World" printf

// Check if printf returned 14, as it should since we printed 14 chars
14 ? if
    "printf test OK\n"print
else
    "printf test FAIL\n"print
end