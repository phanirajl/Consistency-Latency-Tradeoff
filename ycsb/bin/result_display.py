#!/usr/bin/python
# -*- coding: UTF-8 -*-

import os
import sys
from itertools import product
from conf import *
from copy import deepcopy
from util.display import plot


write_round_list = []
read_round_list = []
property_list = []
write_latency_list = []
read_latency_list = []
k_max_list = []
probability_list = []

with open(os.getcwd() + '/' + sys.argv[1] + '/' + sys.argv[1] + '.txt', 'r') as f:
    lines = f.readlines()[1:]
    for line in lines:
        raw_values = line.split('#')

        write_round_list.append(raw_values[0])
        read_round_list.append(raw_values[1])
        property_list.append(dict(zip(property_name_list, raw_values[2:18])))
        write_latency_list.append(eval(raw_values[-4]))
        read_latency_list.append(eval(raw_values[-3]))
        k_max_list.append(eval(raw_values[-2]))
        probability_list.append(eval(raw_values[-1]))

property_result_list = zip(write_round_list, read_round_list, property_list, write_latency_list, read_latency_list,
                           k_max_list, probability_list)

# print ('default trace num :')
# print (len(filter(lambda xxx: cmp(xxx[2], default_property_value_map) == 0, property_result_list)))


# Metrics:
algorithm_conf = (('2', '2'), ('2', '1'))

snitch_values = ('None')
read_process_values = ('simple')
cassandra_conf = product(snitch_values, read_process_values)

algorithm_cassandra_conf = product(cassandra_conf, algorithm_conf)


# The method filters results for a given parameter as the independent variable.
# -name: the parameter name
# -values: all possible values of the parameters, set in "conf.py"
def get_param_results(name, values):
    param_traces = []
    # Add basic-parameter traces.
    param_property_value_map = deepcopy(default_property_value_map)
    # Add other traces:
    for value in values:
        param_property_value_map[name] = value
        param_traces.extend(filter(lambda x: cmp(x[2], param_property_value_map) == 0, property_result_list))
    return param_traces


if __name__ == '__main__':
    for param_name, param_values in parameter_values_map.items():
        param_results = get_param_results(param_name, param_values)
        print (param_name)
        print (param_values)
        print (len(param_results))
        try:
            os.makedirs(os.getcwd() + '/' + sys.argv[1] + '/pic')
        except OSError:
            pass
        plot.make_plot(param_results, param_name, param_values)
