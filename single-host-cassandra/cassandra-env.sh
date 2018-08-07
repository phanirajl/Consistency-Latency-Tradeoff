#!/bin/bash

# expect one parameter i.e. the username

lsdir=`ls $1`
dirarr=($lsdir)
matcharr=()

echo "${dirarr[@]}"

for subdir in ${dirarr[@]}; do
    match=`echo "$subdir" | egrep "node(25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[1-9])"`
    if [[ $match = "$subdir" ]]; then
        export CASSANDRA_CONF="$1/$subdir/conf"
        #CLASSPATH=$CASSANDRA_CONF
        #for jar in cassandra/lib/*.jar; do
         #   CLASSPATH=$CLASSPATH:$jar
        #done

        #for jar in /cassandra/build/lib/jars/*.jar; do
         #   CLASSPATH=$CLASSPATH:$jar
        #done
        #CLASSPATH=$CLASSPATH:"cassandra/build/apache-cassandra-3.7-SNAPSHOT.jar"

        #export CLASSPATH
        CASSANDRA_HOME=./cassandra
        # set JVM javaagent opts to avoid warnings/errors
        if [ "$JVM_VENDOR" != "OpenJDK" -o "$JVM_VERSION" \> "1.6.0" ] \
              || [ "$JVM_VERSION" = "1.6.0" -a "$JVM_PATCH_VERSION" -ge 23 ]
        then
            JAVA_AGENT="$JAVA_AGENT -javaagent:$CASSANDRA_HOME/lib/jamm-0.3.0.jar"
        fi
        export CASSANDRA_HOME
        export JAVA_AGENT
        export CASSANDRA_INCLUDE=`pwd`"/cassandra/bin/cassandra.in.sh"

        short=""
        long=""
        if [[ $# -gt 1 ]]; then
            short="-DshortDelay=$2"
            long="-DlongDelay=$3"
        fi
        ./cassandra/bin/cassandra -p "$1/$subdir/pid" -Dcassandra.logdir="$1/$subdir/logs" -Dcassandra.storagedir="$1/$subdir/data" -Dlogback.configurationFile="$1/$subdir/conf/logback.xml" $short $long
        sleep 60
    fi
done

