#!/usr/bin/python
# -*- coding: UTF-8 -*-

from __future__ import division
import os
import sys
import time
from collections import Counter
from util.calculation import WriteReadCluster, one_kv, k_calculation
from util.intervaltree import Interval, IntervalTree
from functools import reduce

global forward_zones, backward_zones, singles, cluster_dict

if __name__ == '__main__':
    # st = time.time()
    outer_path = os.getcwd()
    directory_name = sys.argv[1]
    os.chdir(outer_path + "/" + directory_name)
    sub_files = filter(lambda x: os.path.isdir(x) and x != 'pic', os.listdir(os.getcwd()))
    # print (sub_files)

    # The following objects record the statistics for all traces.
    forward_zone_count = 0
    backward_zone_count = 0
    single_zone_count = 0

    read_nums = []  # read_nums := list( readnum for each trace)
    write_nums = []  # write_nums := list( writenum for each trace)

    zone_pair_violation_nums = []
    zone_pair_violation_rate = []
    k_readnum_list = []  # k_readnum_list := list( list(readnum for k = 1,2,3...) for each trace)
    k_readnum_rate_list = []  # k_readnum_list := list( list( tuple(readnum, rate) for k = 1,2,3...) for each trace)

    write_latency_sum = 0
    read_latency_sum = 0

    k_trace_num = {1: 0}  # Record the num of k-atomicity traces.

    print ("write_round read_round" +
           " replica_factor write_consistency_level read_consistency_level" +
           " dcchance chance lb snitch read_process dcdelay" +
           " insert_count operation_count client_count ops duration read_proportion client_delay" +
           " repeat" +
           " real ops" +
           " writenum readnum" +
           " zone_count(forward/backward/single)" +
           " violation(F-F/F-B/F-S)" +
           " total zone_pair_violation_rate" +
           " latency(W & R)" +
           " k_max" +
           " Count-P")

    for sub_file in sub_files:

        write_round, read_round, \
        replica_factor, write_ConsistencyLevel, read_ConsistencyLevel, \
        dcchance, chance, lb, snitch, read_process, dcdelay, \
        insert_count, operation_count, client_count, ops, duration, read_proportion, client_delay, repeat \
            = map(lambda x: x.split('=')[1] if '=' in x else x, sub_file.strip().split("@"))

        if write_round == '1' or read_ConsistencyLevel == 'LOCAL_QUORUM':
            continue

        os.chdir(outer_path + '/' + directory_name + '/' + sub_file)
        file_list = os.listdir(os.getcwd())

        # Pre-process 1:
        # Get operations:

        read_lines = []
        write_lines = []
        for filename in file_list:
            with open(filename, 'r') as ftrace:
                # Distinguish write operations from read operations
                lines = ftrace.readlines()
                for line in lines:
                    if 'W' in line:
                        write_lines.append(line)
                    else:
                        # Omit reads that return initial value.
                        if 'DEFAULT' in line:
                            continue
                        read_lines.append(line)

            # Another way to iterate: for write & read seperated clients:
        # if filename[21]=='0':
        #	##print ftrace.name
        #	write_lines.extend(ftrace.readlines())
        # else:
        #	read_lines.extend(ftrace.readlines())

        trace_write_num = len(write_lines)
        trace_read_num = len(read_lines)

        write_nums.append(trace_write_num)
        read_nums.append(trace_read_num)

        # Pre-process 2:
        # Get zones:
        write_start = []
        write_finish = []
        write_latency = []

        read_start = []
        read_finish = []
        read_latency = []

        trace_zone_violation_num = 0

        cluster_dict = {}  # cluster_dict := { (ver,pid) : WriteReadCluster }

        # 2.1 Use writes to form clusters.
        for index, op in enumerate(write_lines):
            new_op = op.strip().split("|||")  # Op := [key, val, str(WRITE/READ), long(start_time), long(finish_time), int(latency), tuple(version) ]

            write_start.append(long(new_op[3]))
            write_finish.append(long(new_op[4]))
            write_latency.append(int(new_op[5]))

            version = new_op[6]  # Construct the final version in the form of (ver,pid)
            cluster_dict[version] = WriteReadCluster.WriteReadCluster(version, new_op[3], new_op[4],
                                                                      index)  # Join the dictating write to the cluster.

        # 2.2 Join reads to corresponding clusters.
        for index, op in enumerate(read_lines):
            new_op = op.strip().split("|||")  # Op := [key, val, long(start_time), long(finish_time), int(latency), int(ver), int(pid) ]
            read_start.append(long(new_op[3]))
            read_finish.append(long(new_op[4]))
            read_latency.append(int(new_op[5]))

            version = new_op[6]  # Construct the final version in the form of (ver,pid)
            cluster_dict[version].append(new_op[3], new_op[4], index)  # join reads to corresponding clusters.

        # 2.3 Distinguish different types of zones.
        forward_zones = []
        backward_zones = []
        singles = []
        for ver in cluster_dict:
            if cluster_dict[ver].zone_type == "F":
                forward_zones.append(ver)
            elif cluster_dict[ver].zone_type == "B":
                backward_zones.append(ver)
            else:
                singles.append(ver)

        forward_zone_count += len(forward_zones)
        backward_zone_count += len(backward_zones)
        single_zone_count += len(singles)

        backward_zones.extend(singles)

        # Process 3:
        # Verify k-atomicity, k=1,2,3...

        # 3.1 k=1:
        is_one_atomicity, ff_violations, fb_violations, fs_violations = one_kv.one_kv(cluster_dict, forward_zones,
                                                                                      backward_zones, singles)


        trace_zone_violation_num = ff_violations + fb_violations + fs_violations
        zone_pair_violation_rate.append(trace_zone_violation_num * 2 / (trace_write_num * (trace_write_num - 1)))

        trace_write_latency_sum = sum(write_latency)
        write_latency_sum += trace_write_latency_sum
        trace_read_latency_sum = sum(read_latency)
        read_latency_sum += trace_read_latency_sum
        zone_pair_violation_nums.append(trace_zone_violation_num)

        if is_one_atomicity:
            print ('{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}'
                   '#{:.2f}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{:.2f}#{:.2f}#{:.4f}#{}#[({}, {})]'
                   .format(write_round, read_round,
                           replica_factor, write_ConsistencyLevel, read_ConsistencyLevel,
                           dcchance, chance, lb, snitch, read_process, dcdelay,
                           insert_count, operation_count, client_count, ops, duration, read_proportion, client_delay,
                           repeat,
                           round((len(write_lines) + len(read_lines)) / int(duration), 2),
                           len(write_lines), len(read_lines),
                           len(forward_zones), len(backward_zones), len(singles),
                           ff_violations, fb_violations, fs_violations,
                           trace_zone_violation_num, zone_pair_violation_rate[-1],
                           trace_write_latency_sum / len(write_latency), trace_read_latency_sum / len(read_latency),
                           1,
                           trace_read_num, 1.00
                           )
                   )

            k_trace_num[1] += 1
            k_readnum_list.append([trace_read_num, 0])
            k_readnum_rate_list.append([(trace_read_num, 1), (0, 0)])
            continue

        # 3.2 k>1:

        # 3.2.1 using interval tree and get trunks:

        # Step 1: Construct an interval tree consisting of only forward zones
        zone_tree = IntervalTree(
            Interval(cluster_dict[ver].min_finish, cluster_dict[ver].max_start, ver) for ver in forward_zones)
        sorted(zone_tree)
        # print zone_tree
        # print "forward zone num:"+str(len(zone_tree))

        # Merge forward zones with overlapping ranges and merge them into a single interval.
        # Using a dict to store chunk info.
        chunk_dict = {}  # chunk_dict := {first_beginning_zone_ver in the chunk : list(vers of clusters in the chunk)}


        # def version_reducer(current_data, new_data):
        # 	global chunk_dict
        # 	try:
        # 		current_data(new_data)
        # 	except:
        # 		chunk_dict[current_data].append(new_data)
        # 		return current_data
        # 	return new_data
        #
        # def version_initializer(newdata):
        # 	global chunk_dict
        # 	chunk_dict[newdata]=[newdata]
        # 	return

        def version_reducer(current_data, new_data):
            global chunk_dict
            if hasattr(current_data, '__call__'):
                # if callable(current_data) :
                current_data()
                chunk_dict[new_data] = [new_data]
                return new_data
            else:
                chunk_dict[current_data].append(new_data)
                return current_data


        def version_initializer():
            return


        zone_tree.merge_overlaps(version_reducer, version_initializer)

        max_chunk_size = 1  # Record the max number of clusters in a chunk.
        # print "forward-zone chunks with more than one forward zones:"
        for ver, chunk in chunk_dict.items():
            if len(chunk) > 1:
                max_chunk_size = max(max_chunk_size, len(chunk))

        # print chunk
        # cluster_dict[ver].display()
        # write_index = cluster_dict[ver].write
        # print 'WRITE : time interval:{0}~{1},latency:{2}'.format(write_start[write_index], write_finish[write_index], write_latency[write_index])
        # for index in cluster_dict[ver].reads:
        #	print 'READ : time interval:{0}~{1},latency:{2}'.format(read_start[index],read_finish[index],read_latency[index])

        # print "forward-zone chunks:{}".format(chunk_dict)

        sorted(zone_tree)
        # print zone_tree
        # print "forward-zone chunk num:"+str(len(zone_tree))
        # print "range:"+str(zone_tree.range())

        # Step 2: Add backward zones to the forward-zone chunks(when enveloped by some forward zones) & join in the chunk_dict.

        for ver in backward_zones:
            start_interval = zone_tree[cluster_dict[ver].max_start]
            end_interval = zone_tree[cluster_dict[ver].min_finish]

            if (len(start_interval) == 1) and (start_interval == end_interval):
                # print "backward zone:"+ ver

                fz_chunk = start_interval.pop()  # fz_chunk : the earliest-beginning forward-zone in the chunk
                fz_ver = fz_chunk.data

                chunk_dict[fz_ver].append(ver)
                # print chunk_dict[fz_ver]
                max_chunk_size = max(max_chunk_size, len(chunk_dict[fz_ver]))

            # for ver in chunk_dict[fz_ver]:
            #	cluster_dict[ver].display()
            #	write_index = cluster_dict[ver].write
            #	print 'WRITE : time interval:{0}~{1},latency:{2}'.format(write_start[write_index], write_finish[write_index], write_latency[write_index])
            #	for index in cluster_dict[ver].reads:
            #		print 'READ : time interval:{0}~{1},latency:{2}'.format(read_start[index],read_finish[index],read_latency[index])
            else:
                chunk_dict[ver] = [ver]

        chunk_size_list = map(lambda x: len(x), chunk_dict.values())
        sorted_chunk_size_dict = dict(Counter(chunk_size_list))
        # print 'chunk size:num:{}'.format(sorted_chunk_size_dict)
        # print 'max chunk size:{}'.format(max_chunk_size)
        # 3.2.2
        # TODO: Approach 1:  GPO Algorithm for each chunk:
        # Attention: GPO Algorithm is only applied for the trace consisting of only forward zones without backward zones.

        # Approach 2: CGS Algorithm for each chunk:
        # for key,vers in chunk_dict.items():
        #	if len(vers) == 1
        #		read_k[0] += cluster_dict[vers[0]].readcount
        #		continue
        #	else:
        #		m = len(vals)
        #		k = 1
        #		while True:
        #			if m < k:
        #				read_k[k-1] += cluster_dict[val].readcount for val in vals
        #				break

        chunk_k, trace_k_readnum_count = k_calculation.k_calculation(chunk_dict, cluster_dict, max_chunk_size,
                                                                     write_start, write_finish, read_start, read_finish)
        # print 'chunk_k:{}'.format(chunk_k)
        # print 'read num count :{}'.format(trace_k_readnum_count)
        k, max_k_chunk = max(chunk_k)
        # print 'k = {}'.format(k)
        if k in k_trace_num:
            k_trace_num[k] += 1
        else:
            k_trace_num[k] = 1

        k_readnum_list.append(trace_k_readnum_count)
        k_readnum_rate_list.append(
            zip(trace_k_readnum_count, list(round(count / trace_read_num, 4) for count in trace_k_readnum_count)))

        print ('{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{}'
               '#{:.2f}#{}#{}#{}#{}#{}#{}#{}#{}#{}#{:.2f}#{:.2f}#{:.4f}#{}#{}'
               .format(write_round, read_round,
                       replica_factor, write_ConsistencyLevel, read_ConsistencyLevel,
                       dcchance, chance, lb, snitch, read_process, dcdelay,
                       insert_count, operation_count, client_count, ops, duration, read_proportion, client_delay,
                       repeat,
                       round((len(write_lines) + len(read_lines)) / int(duration), 2),
                       len(write_lines), len(read_lines),
                       len(forward_zones), len(backward_zones), len(singles),
                       ff_violations, fb_violations, fs_violations,
                       trace_zone_violation_num, zone_pair_violation_rate[-1],
                       trace_write_latency_sum / len(write_latency), trace_read_latency_sum / len(read_latency),
                       k,
                       k_readnum_rate_list[-1][:10]
                       )
               )

    # total_trace_num = sum(k_trace_num.values())
    # print "Number of traces : {}".format(total_trace_num)
    # print "Number of traces in the format of (k_max : num of traces):{}".format(k_trace_num)
    #
    # print "Forward Zone num:{}".format(forward_zone_count)
    # print "Backward Zone num:{}".format(backward_zone_count)
    # print "Single Zone num:{}".format(single_zone_count)
    # write_num_sum = sum(write_nums)
    # read_num_sum = sum(read_nums)
    # duration = 60
    # print "Write num in total:{}".format(write_num_sum)
    # print "Read num in total:{}".format(read_num_sum)
    # print "Average write num:{}".format(write_num_sum / total_trace_num)
    # print "Average read num:{}".format(read_num_sum / total_trace_num)
    # print "Average workload:{}".format((write_num_sum + read_num_sum) / total_trace_num)
    # print ("ops:{}".format((write_num_sum + read_num_sum) / (total_trace_num * duration)))
    # print "Average write latency in total/ms:{:3f}".format(write_latency_sum / write_num_sum)
    # print "Average read latency in total/ms:{:3f}".format(read_latency_sum / read_num_sum)
    # print "Zone pair violation num in total:{}".format(sum(zone_pair_violation_nums))
    # print "Zone_pair_violation_rate:{:9f}".format(sum(zone_pair_violation_rate) / total_trace_num)
    # # read_stale_num_sum = sum(map(sum, zip(*k_readnum_list))[1:])
    # read_fresh_num_sum = sum(
    #     zip(*k_readnum_list)[0])  # k=1: may be lower than the real num considering we omit the large-size chunks.
    # read_stale_num_sum = sum(map(sum, zip(*k_readnum_list))[
    #                          1:])  # k>1: may be lower than the real num considering we omit the large-size chunks.
    # # read_stale_num_sum = read_num_sum - read_fresh_num_sum
    # read_stale_num_rate = read_stale_num_sum / (read_fresh_num_sum + read_stale_num_sum)
    # print 'Fresh/Stale read num:{},{}'.format(read_fresh_num_sum, read_stale_num_sum)
    # print 'Fresh/Stale read num rate:{:4%},{:4%}'.format(1 - read_stale_num_rate, read_stale_num_rate)
    #
    # en = time.time()
    #
    # print 'Used time for processing results:{}s'.format(en - st)
