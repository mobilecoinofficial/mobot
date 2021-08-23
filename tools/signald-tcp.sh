# Copyright (c) 2021 MobileCoin. All rights reserved.

socat -d TCP4-LISTEN:15432,fork UNIX-CONNECT:/usr/local/signald.sock &

JAVA_OPTS="-Xms256m -Xmx1024m"  /usr/local/bin/signald -d /signald -s /usr/local/signald.sock -v
