#!/bin/bash

# $1 : user name
# $2 : topology
# $3 : start_ip (optional, default : 127.0.0.1)

CLUSTER_NAME=$1"_cluster"
DC_MACHINE_NUM=(${2//_/ })
DC_NUM=${#DC_MACHINE_NUM[@]}

if [[ $# -lt 3 ]]; then
    start_seq=71
else
    start_seq=$3
fi

# seeds
seeds="127.0.0.$start_seq"
seedno=${start_seq}
NODE_IN_DC=()
for ((i=0;i<$DC_NUM;i++)); do
    for id in `seq $((seedno-$start_seq)) $((seedno+${DC_MACHINE_NUM[i]}-1-$start_seq))` ; do
        NODE_IN_DC[$id]=$(($i+1))
#        echo ${NODE_IN_DC[$id]}
    done
    if [[ $i -lt ${DC_NUM}-1  ]]; then
        seedno=$((seedno+${DC_MACHINE_NUM[i]}))
        seeds=$seeds",127.0.0.$seedno"
    fi
done
echo "seeds:"$seeds
end_seq=$((seedno+${DC_MACHINE_NUM[$DC_NUM-1]}-1))
#echo $end_seq

# topology
if [[ ${DC_NUM} -gt 1 ]]; then
    TOPOLOGY="networktopology"
else
    TOPOLOGY="simpletopology"
fi


# $1 : node id
setup_node()
{
    printf " \n+ Setting up node%d...\n" $1
    create_dirs $1
    setup_resources $1
    tweak_cassandra_config $1
}


create_dirs()
{
	node=$1
	mkdir -p $CLUSTER_NAME/node$node/data/{data,commitlog,saved_caches}
    mkdir -p $CLUSTER_NAME/node$node/hints
	mkdir -p $CLUSTER_NAME/node$node/logs
}


copy_config()
{
	node=$1
	src="cassandra/conf"
	dst="$CLUSTER_NAME/node$node/conf"
	mkdir -p $dst
	cp -r "$src"/* $dst
}


setup_resources()
{
    echo "  -Copying configurations"
    copy_config $1
}



tweak_cassandra_config()
{
    env="$CLUSTER_NAME/node$1/conf/cassandra-env.sh"
    conf="$CLUSTER_NAME/node$1/conf/cassandra.yaml"
    logs="$CLUSTER_NAME/node$1/conf/logback.xml"
    jvm="$CLUSTER_NAME/node$1/conf/jvm.options"
    rackdc="$CLUSTER_NAME/node$1/conf/cassandra-rackdc.properties"

    base_data_dir="$CLUSTER_NAME/node$1/data"

    # Set the JMX port
    let port=7200+$1
	echo "  -Setting up JMX port :$port"
    regexp="s/JMX_PORT=\"7199\"/JMX_PORT=\"$port\"/g"
    sed -i -- $regexp $env

    # set Xms and Xmx
    regexp="s/#\-Xms4G/-Xms2G/g"
    sed -i -- "$regexp" $jvm
    regexp="s/#-Xmx4G/-Xmx2G/g"
    sed -i -- "$regexp" $jvm
    echo -e "\n-XX:MaxDirectMemorySize=1024M\n-XX:NativeMemoryTracking=summary" >> $jvm
    echo "  -Setting heap properties:-Xms2G -Xmx2G -XX:NativeMemoryTracking=summary"
	#echo -e "\ncassandra.logdir: ""/$CLUSTER_NAME/node$1/logs" >> $conf
	#echo -e "\ncassandra.staragedir: ""/$CLUSTER_NAME/node$1/data" >> $conf
	#echo -e "\ncassandra.configurationFile: ""2/node$1/conf/logback.xml" >> $conf

    # Set the gc log location
    regexp="s|#-Xloggc:/var/log/cassandra/gc.log|-Xloggc:$CLUSTER_NAME/node$1/logs/gc.log|g"
    sed -i -- "$regexp" $jvm
    if [[ ! -e $CLUSTER_NAME/node$1/logs/gc.log ]]; then
        touch "$CLUSTER_NAME/node$1/logs/gc.log"
    fi
    echo "  -Setting up the GC log location:$CLUSTER_NAME/node$1/logs/gc.log"

    # C* logs
    regexp="s|<jmxConfigurator />|<jmxConfigurator /> <property name=\"cassandra.logdir\" value=\"$CLUSTER_NAME/node$1/logs/\" />|g"
    sed -i -- "$regexp" $logs

    # Set the cluster name
    regexp="s/Test Cluster/$CLUSTER_NAME/g"
    sed -i -- "$regexp" $conf
    echo "  -Setting up the cluster name:"$CLUSTER_NAME

    # Set the commitlog directory, and various other directories
    echo "  -Setting up directories"
    regexp="s|/var/lib/cassandra/commitlog|$base_data_dir/commitlog|g"
    sed -i -- "$regexp" $conf

    # data_file_directories
    regexp="s|/var/lib/cassandra/data|$base_data_dir/data|g"
    sed -i -- "$regexp" $conf

    # saved_caches_directory
    regexp="s|/var/lib/cassandra/saved_caches|$base_data_dir/saved_caches|g"
    sed -i -- "$regexp" $conf

    # Disable hinted handoff
    echo "  -Disable hinted handoff"
    regexp="s|^hinted_handoff_enabled:.*|hinted_handoff_enabled: false|g"
    sed -i -- "$regexp" $conf

    # Set the hints location
    echo "  -Setting up the hints location"
    regexp="s|^# hints_directory.*|hints_directory: $CLUSTER_NAME/node$1/hints|g"
    sed -i -- "$regexp" $conf

    if [[ $TOPOLOGY == "networktopology" ]]; then
        # Override datacenter information

        id=$(($1-$start_seq))
        let dc=${NODE_IN_DC[$id]}
        regexp="s|^dc=dc1|dc=dc$dc|g"
        sed -i -- "$regexp" $rackdc
        echo "  -Override DC information:dc=dc"$dc

        # Set snitch
        echo "  -Set snitch property"
        regexp="s|^endpoint_snitch.*|endpoint_snitch: GossipingPropertyFileSnitch|g"
	    #regexp="s|^endpoint_snitch.*|endpoint_snitch: DynamicEndpointSnitch|g"
        sed -i -- "$regexp" $conf
    fi

    # Set up the network interface
    echo "  -Setting up network interface"
    sudo ifconfig "lo:$1" "127.0.0.$1"

    # Bind the various services to their local IP address
    # listen_address
    echo "  -Binding services:listen_address: 127.0.0.$1 rpc_address: 127.0.0.$1"
    regexp="s/listen_address: localhost/listen_address: 127.0.0.$1/g"
    sed -i -- "$regexp" $conf

    # rpc_address
    regexp="s/rpc_address: localhost/rpc_address: 127.0.0.$1/g"
    sed -i -- "$regexp" $conf


    # seeds="127.0.0.$3"

    # seeds=`echo $raw_seeds | sed -e s/,$//`
    regexp="s/seeds: \"127.0.0.1\"/seeds: \"$seeds\"/g"
    sed -i -- "$regexp" $conf
}


# nodes setup
for i in $(seq $start_seq $end_seq); do
    setup_node $i
    if test -z $iplist; then
        iplist="127.0.0.$i"
    else
        iplist=$iplist",127.0.0.$i"
    fi
done
#echo $iplist

# record ip list
file="../ycsb/workloads/cassProperties"
sed -i -e "s|^hosts=.*|hosts=$iplist|g" -e "s/[,]*$//g" $file

echo "Done."







#[ $start_seq = "illegal" ] && exit 1


#if [[ $# -lt 3 ]]; then
#    C_NODES=3
#else
#    C_NODES=$3
#fi
#echo "~= cluster: %s, %d nodes =~\n" "$CLUSTER_NAME" "$C_NODES"

#let dcmachine=$C_NODES/$DC_NUM
#
#let end_seq=$start_seq+$C_NODES-1
#echo "end_seq $end_seq"




#
#for ((idc=1;idc<=$DC_NUM;idc++)); do
#	let seedno=$start_seq+$idc*$dcmachine-$dcmachine; echo $seedno;
#	if [[ $seedno > $end_seq ]]; then
#		break
#	fi
#	if [[ -z $seeds ]]; then
#		seeds="127.0.0.$seedno"
#	else
#		seeds=$seeds",127.0.0.$seedno"
#	fi
#
#done
#echo $seeds
#
#



