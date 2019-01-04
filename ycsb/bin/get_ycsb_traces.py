#!/usr/bin/python
# -*- coding: UTF-8 -*-

from cassandra.cluster import Cluster
from itertools import product
from conf import *
import time
import os
import sys
import subprocess

# All properties/parameters have been given in the file "conf.py"
# Including ip list, Cassandra/server parameters and YCSB/client parameters.

if __name__ == '__main__':
    # Get connected to the Cassandra clusters.
    cluster = Cluster(ip_list)
    session = cluster.connect()
    session.default_timeout = 50

    # Set output directory name and filename.
    # dir_name = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(time.time())) + "_" + sys.argv[1]
    dir_name = sys.argv[1]

    changing_parameter_map = {}
    count = 0
    for run in range(repeat):
        default_setting_done = False
        for param_name, param_values in parameter_values_map.items():
            # Set basic values for all parameters.
            replica_factor = default_replica_factor
            read_consistency_level = default_read_consistency_level
            write_consistency_level = default_write_consistency_level
            dc_local_read_repair_chance = default_dc_local_read_repair_chance
            read_repair_chance = default_read_repair_chance
            load_balancing_strategy = default_load_balancing_strategy
            snitch_strategy = default_snitch_strategy
            read_process = default_read_process
            server_delay_in_ms = default_server_delay_in_ms

            insert_count = default_insert_count
            operation_count = default_operation_count
            client_count = default_client_count
            ops = default_ops
            execution_second = default_execution_second
            read_proportion = default_read_proportion
            client_delay_in_ms = default_client_delay_in_ms

            # if default_setting_done is False:
            #     param_values = param_values[1:]
            # else:
            #     default_setting_done = False
            #
            # if len(param_values) == 0:
            #     continue

            for param_value in param_values:
                if default_property_value_map[param_name] == param_value:
                    if default_setting_done is True:
                        continue
                    else:
                        default_setting_done = True

                for write_round, read_round in product(write_round_list, read_round_list):
                    globals()[param_name] = param_value
                    # Set some further info.
                    part1, part2, part3 = replica_factor.split('_')
                    replica_str = " 'dc1' : " + part1 + ", 'dc2' : " + part2 + ", 'dc3' : " + part3

                    update_proportion = str(1 - float(read_proportion))

                    print ('---> Now tuning parameter < {} : {} > to the value < {} >'.format(param_name,
                                                                                              parameter_values_map[
                                                                                                  param_name],
                                                                                              locals()[param_name]))
                    print ('------------Cassandra parameters------------')
                    print ("Replica factor: " + replica_str)
                    print ("Write/Read Consistency Level: " + write_consistency_level + "/" + read_consistency_level)
                    print ("Background DC-Local Read-Repair Chance: " + str(dc_local_read_repair_chance))
                    print ("Background Read-Repair Chance: " + str(read_repair_chance))
                    print ("Load Balance Strategy: " + load_balancing_strategy)
                    print ("Snitch Strategy: " + snitch_strategy)
                    print ("Read Process: " + read_process)
                    print ("Server Delay across DCs: " + server_delay_in_ms)
                    print ('------------Client parameters---------------')
                    print ("Insert Count: " + insert_count)
                    print ("Operation Count: " + operation_count)
                    print ("Client Count: " + str(client_count))
                    print ("ops: " + str(ops))
                    print ("Duration: " + execution_second)
                    print ("Client Delay: " + client_delay_in_ms)
                    print ("Read/Update Proportion: " + str(read_proportion) + "/" + str(update_proportion))
                    print ('------------Algorithm parameters------------')
                    print ("Write/Read Round: " + write_round + "/" + read_round)
                    count += 1
                    print ('This is Trace : {}'.format(count))
                    print ('')
                    # continue

                    # waitTmp = wait.strip().split()
                    # waitBase = waitTmp[1]
                    # waitRandom = waitTmp[3]
                    # print waitTmp
                    if replica_str == "1" and (read_consistency_level != "ALL" or write_consistency_level != "ALL"):
                        break
                    st = time.time()
                    while True:
                        try:
                            session.execute('drop keyspace if exists ycsb;', None)
                            # time.sleep(10)
                            session.execute(
                                "create keyspace ycsb with replication = {'class' : " + topology + ", " + replica_str + "};",
                                None)
                            # time.sleep(5)
                            session.execute("use ycsb;", None)
                            session.execute(
                                'create table usertable ( y_id varchar primary key, field0 varchar)' +
                                ' WITH dclocal_read_repair_chance = ' + str(dc_local_read_repair_chance) +
                                ' AND read_repair_chance = ' + str(read_repair_chance) +
                                ' AND caching = {\'keys\': \'NONE\',\'rows_per_partition\': \'NONE\'}' +
                                ' AND speculative_retry = \'NONE\';', None)
                            print ("Successfully create table!")
                            break
                        except RuntimeError:
                            print (time.strftime("%Y-%m-%d-%H-%M-%S",
                                                 time.localtime(time.time())) + " Cannot connect to server")
                    end = time.time()
                    print ('Connection used time: {}'.format(end-st))

                    time.sleep(10)
                    if load_balancing_strategy == 'rr':
                        db = " -db CLTradeoffCassandraDB"
                    elif load_balancing_strategy == 'localaware':
                        db = ""
                    else:
                        db = "tbd"

                    # YCSB load phase:
                    # Insert test data into the table.
                    load = subprocess.Popen(
                        args=" ./ycsb load cassandra-cql" +
                             " -P ../workloads/workloada" +
                             " -P ../workloads/cassProperties" +
                             " -p workload=CLTradeoffWorkload" +
                             " -p clientID=0" +
                             " -p readproportion=" + str(read_proportion) +
                             " -p updateproportion=" + str(update_proportion) +
                             " -p insertcount=" + insert_count +
                             " -p operationcount=" + operation_count +
                             " -p cassandra.readconsistencylevel=ALL" +
                             " -p cassandra.writeconsistencylevel=ALL" +
                             " -p clientcount=" + str(client_count) + db,
                        shell=True,
                        cwd=".")
                    load.wait()
                    time.sleep(5)

                    # YCSB run phase:
                    # Filename records the following info:
                    # Algorithm parameters: write round, read round
                    # YCSB/client workload parameters:
                    # insert count, client count, ops, max execution time, client delay, repeat id...
                    # Cassandra/server parameters:
                    # replica factor, write consistency level, read consistency level,
                    # read repair chance, load balance strategy...
                    os.makedirs("./" + dir_name + "/" + "wRound=" + write_round + "@rRound=" + read_round +
                                "@replica=" + replica_factor +
                                "@writeCL=" + write_consistency_level + "@readCL=" + read_consistency_level +
                                "@dcchance=" + str(dc_local_read_repair_chance) +
                                "@chance=" + str(read_repair_chance) + "@lb=" + load_balancing_strategy +
                                "@snitch=" + snitch_strategy + "@readprocess=" + read_process +
                                "@dcdelay=" + server_delay_in_ms +
                                "@inscount=" + insert_count +
                                "@opcount=" + operation_count + "@clientcount=" + str(client_count) +
                                "@ops=" + ops + "@time=" + execution_second +
                                "@readproportion=" + read_proportion +
                                "@clientdelay=" + client_delay_in_ms +
                                "@repeat=" + str(run))

                    result = []
                    # Mix write & read process:
                    for client_id in range(0, int(client_count)):
                        rlb = db
                        if db == 'tbd':
                            rlb = lb_dict[client_id % 3]
                        result.append(subprocess.Popen(
                            args=" ./ycsb run cassandra-cql" +
                                 " -P ../workloads/workloada" +
                                 " -P ../workloads/cassProperties" +
                                 " -p workload=CLTradeoffWorkload" +
                                 " -p writeround=" + write_round + " -p readround=" + read_round +
                                 " -p replica=" + replica_factor +
                                 " -p cassandra.readconsistencylevel=" + read_consistency_level +
                                 " -p cassandra.writeconsistencylevel=" + write_consistency_level +
                                 " -p dcchance=" + str(dc_local_read_repair_chance) +
                                 " -p chance=" + str(read_repair_chance) +
                                 " -p lb=" + load_balancing_strategy +
                                 " -p snitch=" + snitch_strategy +
                                 " -p readprocess=" + read_process +
                                 " -p dcdelay=" + server_delay_in_ms +
                                 " -p insertcount=" + insert_count +
                                 " -p operationcount=" + operation_count +
                                 " -p clientcount=" + str(client_count) +
                                 " -p ops=" + ops + " -p maxexecutiontime=" + execution_second +
                                 " -p readproportion=" + str(read_proportion) +
                                 " -p updateproportion=" + str(update_proportion) +
                                 " -p clientdelay=" + client_delay_in_ms +
                                 " -p repeat=" + str(run) +
                                 " -p clientID=" + str(client_id) +
                                 " -p dir_name=" + dir_name +
                                 " -p threadcount=1 " +
                                 " -p recording=true" + rlb,
                            shell=True,
                            cwd="."))

                    while len(result) > 0:
                        i = 0
                        while i < len(result):
                            res = result[i]
                            res.poll()
                            if res.returncode is not None:
                                del result[i]
                                continue
                            i += 1
                        time.sleep(0.5)
                    time.sleep(1)
