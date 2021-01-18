# test-assignment
Script for parsing emails. By default finds all ips (v4 and v6) and domains in letter,
writes it into db and prints it in console. Can also search headers by pattern or substring
(start script with parameters -hs --header-string to search by string, and -hp --header-pattern
to use regex pattern).
Writes logs into main.log. It's possible to change level of logging (by adding -cl
--change-level argument).
