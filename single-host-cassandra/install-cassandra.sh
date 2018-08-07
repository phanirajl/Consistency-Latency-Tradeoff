#!/bin/bash

# $1 indicates cluster name, $2 is username, $3 stores node number (optional, default is 3)


CLUSTER_NAME=$1
MAXCAP=10
# even only there is one datacenter this can be also 3 or 5 to set more seeds
datacenter=3

if [[ $# -ge 3 && $3 -gt $MAXCAP ]]; then
    echo "total number of node ecceeds $MAXCAP, abort."
    exit 2
fi


# $2 passes in username like 'whf', $1 indicates the start number of the username
create_dirs()
{
	node=$1
	mkdir -p $2/node$node/data/{data,commitlog,saved_caches}
        mkdir -p $2/node$node/hints
	mkdir -p $2/node$node/logs
}

copy_config()
{
	node=$1
	src="/etc/cassandra"
	dst="$2/node$node/conf"
	mkdir -p $dst
	cp -r "$src"/* $dst
}

setup_resources()
{
    printf "    - Copying configs\n"
    copy_config $1 $2
}

setup_node()
{
    printf "    + setting up node %d...\n" $1
    create_dirs $1 $2
    setup_resources $1 $2
    tweak_cassandra_config $*
}

tweak_cassandra_config()
{
    env="$2/node$1/conf/cassandra-env.sh"
    conf="$2/node$1/conf/cassandra.yaml"
    logs="$2/node$1/conf/logback.xml"
    jvm="$2/node$1/conf/jvm.options"
    rackdc="$2/node$1/conf/cassandra-rackdc.properties"

    base_data_dir="$2/node$1/data"

    # set Xms and Xmx
    printf "    -Setting heap properties\n"
    regexp="s/#\-Xms4G/-Xms2G/g"
    sed -i -- "$regexp" $jvm
    regexp="s/#-Xmx4G/-Xmx2G/g"
    sed -i -- "$regexp" $jvm
    echo -e "\n-XX:MaxDirectMemorySize=1024M\n-XX:NativeMemoryTracking=summary" >> $jvm
	#echo -e "\ncassandra.logdir: ""/$2/node$1/logs" >> $conf
	#echo -e "\ncassandra.staragedir: ""/$2/node$1/data" >> $conf
	#echo -e "\ncassandra.configurationFile: ""2/node$1/conf/logback.xml" >> $conf
	
    # Set the cluster name
    printf "    - Setting up the cluster name\n"
    regexp="s/Test Cluster/$CLUSTER_NAME/g"
    sed -i -- "$regexp" $conf

    # Set the JMX port
    printf "	-Setting up JMX port\n"
    let port=7199+$1
	echo "port $port"
    regexp="s/JMX_PORT=\"7199\"/JMX_PORT=\"$port\"/g"
    sed -i -- $regexp $env

    # Set the commitlog directory, and various other directories
    printf "	- Setting up directories\n"
    regexp="s|/var/lib/cassandra/commitlog|$base_data_dir/commitlog|g"
    sed -i -- "$regexp" $conf

    # data_file_directories
    regexp="s|/var/lib/cassandra/data|$base_data_dir/data|g"
    sed -i -- "$regexp" $conf

    # saved_caches_directory
    regexp="s|/var/lib/cassandra/saved_caches|$base_data_dir/saved_caches|g"
    sed -i -- "$regexp" $conf

    # C* logs
    regexp="s|<jmxConfigurator />|<jmxConfigurator /> <property name=\"cassandra.logdir\" value=\"$2/node$1/logs/\" />|g"
    sed -i -- "$regexp" $logs

    # Set the gc log location
    printf "    - Setting up the GC log location\n"
    regexp="s|#-Xloggc:/var/log/cassandra/gc.log|-Xloggc:$2/node$1/logs/gc.log|g"
    sed -i -- "$regexp" $jvm
    if [[ ! -e $2/node$1/logs/gc.log ]]; then
        touch "$2/node$1/logs/gc.log"
    fi

    # Disable hinted handoff
    #printf "    - Disable hinted handoff\n"
    #regexp="s|^hinted_handoff_enabled:.*|hinted_handoff_enabled: false|g"
    #sed -i -- "$regexp" $conf

    # Set the hints location
    printf "    - Setting up the hints location\n"
    regexp="s|^# hints_directory.*|hints_directory: $2/node$1/hints|g"
    sed -i -- "$regexp" $conf

    if [[ $4 == "networktopology" ]]; then
        # Override datacenter information
        printf "    - Override datacenter information\n"
        let dc=($1-$start_seq)/$dcmachine+1
        regexp="s|^dc=dc1|dc=dc$dc|g"
        sed -i -- "$regexp" $rackdc

        # Set snitch
        printf "    Set snitch property\n"
        regexp="s|^endpoint_snitch.*|endpoint_snitch: GossipingPropertyFileSnitch|g"
        sed -i -- "$regexp" $conf
    fi

    # Set up the network interface
    printf "    - Setting up network interface\n"
    sudo ifconfig "lo:$1" "127.0.0.$1"

    # Bind the various services to their local IP address
    # listen_address
    printf "      - Binding services\n"
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


start_seq=`bash userno.sh $2 $MAXCAP`

[ $start_seq = "illegal" ] && exit 1


if [[ $# -lt 3 ]]; then
    C_NODES=3
else
    C_NODES=$3
fi
printf "~= cluster: %s, %d nodes =~\n" "$CLUSTER_NAME" "$C_NODES"

let dcmachine=$C_NODES/$datacenter

let end_seq=$start_seq+$C_NODES-1
echo "end_seq $end_seq" 

# seeds
seeds=''
for ((idc=1;idc<=$datacenter;idc++)); do 
	let seedno=$start_seq+$idc*$dcmachine-$dcmachine; echo $seedno;
	if [[ $seedno > $end_seq ]]; then
		break
	fi
	if [[ -z $seeds ]]; then
		seeds="127.0.0.$seedno"
	else
		seeds=$seeds",127.0.0.$seedno"
	fi
	
done
echo $seeds
	

topo="simpletopology"
if [[ $# -gt 3 && $4 == "networktopology" ]]; then
    topo="networktopology"
fi

for i in $(seq $start_seq $end_seq); do
    setup_node $i $2 $start_seq $topo
done

printf "Done.\n"
