#!/usr/bin/env bash
LOGFILE=$1
MATCH=$2
CMD="signaldctl key trust-all"
echo "Watching logfile $LOGFILE for match $MATCH and running $CMD"
tail -fn0 $LOGFILE | \
while read line ; do
        echo "$line" | grep -q "$MATCH"
        if [ $? = 0 ]
        then
             $CMD
        fi
done
