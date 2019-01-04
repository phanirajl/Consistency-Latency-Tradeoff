#!/usr/bin/python
# -*- coding: UTF-8 -*-

# conf.py sets all properties/parameters for the experiments.

# The parameters consist of server(Cassandra) parameters, client(YCSB) parameters and algorithm parameters.
# Attention!!!
# Each parameter list better has its values in a partial order
# So that the experimental results can be plotted in a reasonable way.

# Set Cassandra/server ip list:
ip_list = ['127.0.0.61', '127.0.0.62', '127.0.0.61',
           '127.0.0.64', '127.0.0.65', '127.0.0.66',
           '127.0.0.67', '127.0.0.68', '127.0.0.69']

# --> Set server parameters:
# Attention:
# These parameters are only suitable for Cassandra.
# Among these, snitch_strategy_list, read_process_list, server_delay_in_ms_list are only applied for hacked Cassandra.

topology = "'NetworkTopologyStrategy'"
# replica_factor_list = ["'dc1' : 3, 'dc2' : 1, 'dc3' : 1",
#                        "'dc1' : 1, 'dc2' : 1, 'dc3' : 1",
#                        "'dc1' : 3, 'dc2' : 3, 'dc3' : 3"]
replica_factor_list = ['1_1_1', '3_1_1', '3_3_3']
default_replica_factor = '3_1_1'

write_consistency_level_list = ['QUORUM']
default_write_consistency_level = 'QUORUM'

read_consistency_level_list = ['QUORUM', 'EACH_QUORUM']
default_read_consistency_level = 'QUORUM'

# read_repair_chance_list = [(0.0, 0.0), (0.2, 0.1), (0.3, 0.2), (0.4, 0.3)]
dc_local_read_repair_chance_list = ['0.0', '0.2', '0.3', '0.4']
default_dc_local_read_repair_chance = '0.0'

read_repair_chance_list = ['0.0', '0.1', '0.2', '0.3']
default_read_repair_chance = '0.0'

load_balancing_strategy_list = ['rr', 'globalaware', 'localaware']
default_load_balancing_strategy = 'rr'

lb_dict = {0: " -db CLTradeoffCassandraDB", 1: " -db CLTradeoffCassandraDB", 2: " -db CLTradeoffCassandraDB"}

snitch_strategy_list = ['None']
default_snitch_strategy = 'None'

read_process_list = ['simple', 'digest']
default_read_process = 'simple'

server_delay_in_ms_list = ['0', '30', '50']
default_server_delay_in_ms = '30'


# --> Set client parameters:

# Set the number of insert operation in the YCSB load phase.
# Used to set YCSB's property: recordcount
insert_count_list = ['1', '10', '100']
default_insert_count = '1'

# Set operation numbers for each client in the YCSB run phase.
# Won't be achieved if the actual speed is limited by the ops and the execution time.
operation_count_list = ['3000000']
default_operation_count = '3000000'

# The number of write/read clients.
client_count_list = ['10', '30', '50']
default_client_count = '30'

# Set ops : all clients' total operation numbers per second.
# ops_list = ['60', '120', '180', '240', '300']
ops_list = ['300']
default_ops = '300'

execution_second_list = ['10', '60', '300']
default_execution_second = '60'

# wait_time = [' -p waitBase=10 -p waitRandom=1', ' -p waitBase=20 -p waitRandom=1', ' -p waitBase=40 -p waitRandom=1']
# default_wait_time = ' -p waitBase=10 -p waitRandom=1'

# Set the proportion of read/update operations in the YCSB run phase.
read_proportion_list = ['0.50', '0.80', '0.95']
default_read_proportion = '0.80'

# Set the average delay between clients and servers when clients send requests.
client_delay_in_ms_list = ['0', '5', '20']
default_client_delay_in_ms = '5'

# --> Set algorithm parameters.
read_round_list = ['2', '1']
write_round_list = ['2']

# --> Set experimental repeat times.
repeat = 1

# Record all parameters in a given order.
# Result process will use the following two lists.
# Also, trace file is named in the form of the following property orders.
algorithm_name_list = ['write_round', 'read_round']

property_name_list = ['replica_factor', 'write_consistency_level', 'read_consistency_level',
                      'dc_read_repair_chance', 'local_read_repair_chance',
                      'load_balancing_strategy', 'snitch_strategy', 'read_process', 'server_delay_in_ms',
                      'insert_count', 'operation_count', 'client_count', 'ops',
                      'execution_second', 'read_proportion', 'client_delay_in_ms',
                      ]
property_values_list = [replica_factor_list, read_consistency_level_list, read_consistency_level_list,
                        dc_local_read_repair_chance_list, read_repair_chance_list,
                        load_balancing_strategy_list,
                        snitch_strategy_list, read_process_list, server_delay_in_ms_list,
                        insert_count_list, operation_count_list, client_count_list,
                        ops_list, execution_second_list, read_proportion_list, client_delay_in_ms_list,
                        ]
property_map = dict(zip(property_name_list, property_values_list))

# Set default parameter values.
default_value_list = [default_replica_factor, default_write_consistency_level, default_read_consistency_level,
                      default_dc_local_read_repair_chance, default_read_repair_chance,
                      default_load_balancing_strategy,
                      default_snitch_strategy, default_read_process, default_server_delay_in_ms,
                      default_insert_count, default_operation_count, default_client_count,
                      default_ops, default_execution_second, default_read_proportion, default_client_delay_in_ms
                      ]
default_property_value_map = dict(zip(property_name_list, default_value_list))


# You can set tunable parameters here.
parameter_name_list = ["client_count", "ops", "read_proportion", "replica_factor", "read_consistency_level"]
parameter_values_map = dict((name, property_map[name]) for name in parameter_name_list)


if __name__ == '__main__':
    print ('Default parameter-values:{}'.format(default_property_value_map))
    print ("All tunable parameters:{}".format(parameter_values_map))