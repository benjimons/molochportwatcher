# molochportwatcher
Find ports that may be newely exposed to the internet using Moloch session data.

This is tested with Moloch 1.7.0 only.

# Pseudocode Logic
1. Index all successful TCP handshakes seen inbound towards us (by using MAC address as a filter to find only Inbound connections)
2. Look at Yesterdays successful TCP handshakes, determine if we saw these handshakes yesterday too, create a list of ones we didnt see yesterday.
3. Using the new list of ones we never saw, check again the day before to see if we saw a handshake then, create a list of ones we didnt see the day before
4. ..... continue going back until the list gets smaller
5. If you get back 30 days and you have IP:Port pairs that you never saw before, raise an alert.
