#!/usr/bin/python
# -*- coding: UTF-8 -*-

from cassandra.cluster import Cluster
import subprocess
import random
import time
import os, sys

f = open("../workloads/cassProperties")
iplist = f.readline().split("=")[1].split(",")
f.close()
# iplist = ['127.0.0.61', '127.0.0.62', '127.0.0.63', '127.0.0.64', '127.0.0.65', '127.0.0.66', '127.0.0.67', '127.0.0.68', '127.0.0.69']

#replicaParam = ["'replication_factor' : 3", "'replication_factor' : 5", "'replication_factor' : 9"]
#replicaParam = ["'replication_factor' : 9"]
#topology = "'SimpleStrategy'"

topology = "'NetworkTopologyStrategy'"
#replicaParam = ["'dc1' : 1, 'dc2' : 1, 'dc3' : 1", "'dc1' : 3, 'dc2' : 3, 'dc3' : 3", "'dc1' : 3, 'dc2' : 1, 'dc3' : 1"]
replicaParam = ["'dc1' : 1, 'dc2' : 1, 'dc3' : 1"]

proportion = [ 'readproportion=0.80 -p updateproportion=0.20','readproportion=0.50 -p updateproportion=0.50', 'readproportion=0.95 -p updateproportion=0.05',  'readproportion=0.20 -p updateproportion=0.80']
#proportion = ['readproportion=0.80 -p updateproportion=0.20']

#waittime = [' -p waitBase=10 -p waitRandom=1', ' -p waitBase=20 -p waitRandom=1', ' -p waitBase=40 -p waitRandom=1']
#waittime = [' -p waitBase=20 -p waitRandom=1']

insertcount = ['1']
#insertcount = ['1', '10', '100']

operationcount = ["10000","100000"]
exectime = ['60']
qpss = ["1000", "300"]

#clientcount = [3, 5]
clientcount = [(100, 0),(100,0)]

#readConsistencyLevel = ["LOCAL_QUORUM", "ONE", "QUORUM", "ALL", "TWO"]
#writeConsistencyLevel = ["LOCAL_QUORUM", "ONE", "QUORUM", "ALL", "TWO"]
consistencyLevel = ["QUORUM", "LOCAL_QUORUM","EACH_QUORUM"]

chances = [(0.0, 0.0), (0.2, 0.1), (0.3, 0.2),(0.4, 0.3)]

lbs = ["rr", "globalaware", "localaware"]
#clientdelays = ['0','5','10','15','20','25','30']
clientdelays = ['0','5','20']
lbdict = {0: " -db CLTradeoffCassandraDB", 1: " -db CLTradeoffCassandraDB", 2: " -db CLTradeoffCassandraDB"}

#readConsistencyLevel = ["ONE"]
#writeConsistencyLevel = ["ONE"]

readRound = ['1','2']
writeRound = ['2','1']

repeat = 30
#repeat = 1

cluster = Cluster(iplist)
session = cluster.connect()
currenttime = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(time.time())) + "_" + sys.argv[1]

#paramMap = {0: replicaParam, 1: proportion, 2: insertcount, 3: qpss, 4: readConsistencyLevel, 5: writeConsistencyLevel, 6: chances, 7: lbs, 8: clientdelays}
#nameMap = dict(zip([0, 1, 2, 3, 4, 5, 6, 7, 8], ["replicaP", "prop", "inscount", "qps", "readCons", "writeCons", "chance", "lb", 'clientdelay']))

#paramMap = {0: replicaParam, 1: proportion, 2: qpss, 3: clientcount, 4: clientdelays, 5: consistencyLevel}
#nameMap = dict(zip([0, 1, 2, 3, 4, 5], ["replicaP", "prop", "qps", "cnts",  "clientdelay", "consistency"]))

#paramMap = {0: replicaParam, 1: proportion, 2: writeRound, 3: readRound}
#nameMap = dict(zip([0, 1, 2, 3], ["replicaP", "prop", "wRound", "rRound"]))

paramMap = {0: proportion}
nameMap = dict(zip([0], ["prop"]))

changingParamMap = {}



for run in range(repeat):
        for idx in paramMap.keys():
                replicaP = replicaParam[0]
                prop = proportion[0]
                
		inscount = insertcount[0]
                opcount = operationcount[0]
                cnts = clientcount[0]
	
		chance = chances[0]
		lb = lbs[0]
		qps = qpss[0]
		clientdelay = clientdelays[0]

                #readCons = readConsistencyLevel[2]
                #writeCons = writeConsistencyLevel[2]
		readCons = consistencyLevel[1]
		writeCons = consistencyLevel[1]
		rRound = readRound[0]
		wRound = writeRound[0]

                param = paramMap[idx]
                if idx != list(sorted(paramMap))[0]:
                        param = param[1:]
			if len(param) == 0:
				continue
                for paramValue in param:

                        changingIdxList = list(sorted(changingParamMap.keys()))
                        level = -1
                        positions = [0] * len(changingIdxList)
                        if len(positions) != 0:
                            positions[0] = -1
                        while level != len(changingIdxList):
                                if len(positions) == 0:
                                    level = len(changingIdxList)
                                else:
                                    level = 0
                                    positions[level] = positions[level] + 1
                                    if positions[level] != len(changingParamMap[changingIdxList[level]]):
                                            locals()[nameMap[changingIdxList[level]]] = changingParamMap[changingIdxList[level]][positions[level]]

                                    while level < len(changingIdxList) and positions[level] == len(changingParamMap[changingIdxList[level]]):
                                            positions[level] = 0
                                            locals()[nameMap[changingIdxList[level]]] = changingParamMap[changingIdxList[level]][positions[level]]
                                            level = level + 1
                                            if level == len(changingIdxList):
                                                    break
                                            positions[level] = positions[level] + 1
                                            if positions[level] != len(changingParamMap[changingIdxList[level]]):
                                                    locals()[nameMap[changingIdxList[level]]] = changingParamMap[changingIdxList[level]][positions[level]]
                                    if level == len(changingIdxList):
                                            break

				

				



				print idx
				print nameMap[idx]
				print paramValue
                                locals()[nameMap[idx]] = paramValue
                                replicaId = []
                                for part in replicaP.split(','):
                                        replicaId.append(part.split(':')[1].strip())
                                #print (replicaP + " " + prop + " " + inscount + " " + opcount + " " + qps + " " + str(cnts) + " " + readCons + " " + writeCons + " " + str(chance) + " " + lb + " " + str(idx) + " " + clientdelay)
				print (replicaP + " " + prop + " " + inscount + " " + opcount + " " + qps + " " + str(cnts) + " " + readCons + " " + writeCons + " " + str(chance) + " " + lb + " " + str(idx) + " " + clientdelay + " writeRound:" + wRound + " readRound:" +rRound )
                                replicaStr = "_".join(replicaId)
                                # print replicaStr
                                clicnt = cnts[0]
                                readclicnt = cnts[1]
                                #waitTmp = wait.strip().split()
                                #waitBase = waitTmp[1]
                                #waitRandom = waitTmp[3]
                                #print waitTmp
                                if replicaStr == "1" and (readCons != "ALL" or writeCons != "ALL"):
                                        break
                                while True:
                                        try:
                                                session.execute('drop keyspace if exists ycsb;', None)
                                                time.sleep(10)
                                                session.execute("create keyspace ycsb with replication = {'class' : " + topology + ", " + replicaP + "};", None)
                                                time.sleep(5)
                                                session.execute("use ycsb;", None)
                                                session.execute('create table usertable ( y_id varchar primary key, field0 varchar) WITH dclocal_read_repair_chance = ' + str(chance[0]) + " AND read_repair_chance = " + str(chance[1]) + ' AND caching = {\'keys\': \'NONE\',\'rows_per_partition\': \'NONE\'} ' + ' AND speculative_retry = \'NONE\';', None)
                                                print "successfully create table!"
                                                break
                                        except:
                                                print time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(time.time())) + " cannot connect to server"
                                                time.sleep(10)



                                time.sleep(5)
				if lb == 'rr':
					db = " -db CLTradeoffCassandraDB"
				elif lb == 'localaware':
					db = ""
				else:
					db = "tbd"
                                load = subprocess.Popen(args=" ./ycsb load cassandra-cql -P ../workloads/workloada -P ../workloads/cassProperties -p workload=CLTradeoffWorkload" + " -p processId=0" + " -p " + prop + " -p insertcount=" + inscount + " -p operationcount=" + opcount + " -p cassandra.readconsistencylevel=ALL" + " -p cassandra.writeconsistencylevel=ALL" + " -p clientcount=" + str(clicnt + readclicnt) + db, shell=True, cwd=".")
                                load.wait()
                                time.sleep(5)
                                uniqueNumber = random.sample(range(1000, 10000), clicnt + readclicnt)
                                # dir = "replica_factor" + replicaP[-1:] + "@" + prop[:14] + prop[16:19] + "@insertcount" + inscount + "@operationcount" + opcount + "@clientcount" + str(clicnt) + "@" + readCons + "@" + writeCons + "@" + time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
                                result = []
                                #os.makedirs("./" + currenttime + "/" + replicaStr + "@" + prop[0:19] + "@inscount=" + inscount +"@qps=" + qps + "@readConsLevel=" + readCons + "@writeConsLevel=" + writeCons + "@clientcount=" + str(clicnt + readclicnt) + "@dcchance=" + str(chance[0]) + "@chance=" + str(chance[1]) + "@lb=" + lb + "@clientdelay=" + clientdelay + "@repeat=" + str(run))
                                os.makedirs("./" + currenttime + "/" + replicaStr + "@" + prop[0:19] + "@inscount=" + inscount +"@qps=" + qps + "@readround=" + rRound + "@writeround=" + wRound + "@readConsLevel=" + readCons + "@writeConsLevel=" + writeCons + "@clientcount=" + str(clicnt + readclicnt) + "@dcchance=" + str(chance[0]) + "@chance=" + str(chance[1]) + "@lb=" + lb + "@clientdelay=" + clientdelay + "@repeat=" + str(run))                                
				for idxx, uninum in enumerate(uniqueNumber[0:clicnt]):
					rlb = db
					if db == 'tbd':
						rlb = lbdict[idxx % 3] 
					arg = " ./ycsb run cassandra-cql -P ../workloads/workloada -P ../workloads/cassProperties -p workload=CLTradeoffWorkload" + " -p readround=" + rRound + " -p writeround=" + wRound + " -p processId=" + str(uninum) + " -p " + prop + " -p insertcount=" + inscount + " -p operationcount=" + opcount + " -p recording=true" + " -p replica_factor=" + replicaStr + " -p cassandra.readconsistencylevel=" + readCons + " -p cassandra.writeconsistencylevel=" + writeCons + " -p clientcount=" + str(clicnt + readclicnt) + " -p time=" + currenttime + " -p qps=" + qps + " -p dcchance=" + str(chance[0]) + " -p chance=" + str(chance[1]) + " -p lb=" + lb + " -p clientdelay=" + clientdelay + " -p repeat=" + str(run) + " -p maxexecutiontime=" + exectime[0] + " -p threadcount=1 " + rlb;
					print arg
                                        result.append(subprocess.Popen(args=arg, shell=True, cwd="."))
                                        time.sleep(0.2)
                                for idxx, uninum in enumerate(uniqueNumber[clicnt:]):
					rlb = db
					if db == "tbd":
						rlb = lbdict[idxx % 3]
                                        result.append(subprocess.Popen(args=" ./ycsb run cassandra-cql -P ../workloads/workloada -P ../workloads/cassProperties -p readround=" + rRound + " -p writeround=" + wRound + " -p workload=CLTradeoffWorkload" + " -p processId=" + str(uninum) + " -p readproportion=1.00 -p updateproportion=0.00" + " -p lookproportion=" + prop[15:19] + " -p insertcount=" + inscount + " -p operationcount=" + opcount + " -p recording=true" + " -p replica_factor=" + replicaStr + " -p cassandra.readconsistencylevel=" + readCons + " -p cassandra.writeconsistencylevel=" + writeCons + " -p clientcount=" + str(clicnt + readclicnt) + " -p time=" + currenttime + " -p qps=" + qps + " -p dcchance=" + str(chance[0]) + " -p chance=" + str(chance[1]) + " -p lb=" + lb + " -p clientdelay=" + clientdelay + " -p repeat=" + str(run) + " -p maxexecutiontime=" + exectime[0] + " -p threadcount=1 " +rlb, shell=True, cwd="."))
                                        time.sleep(0.2)

                                while (len(result) > 0):
                                        i = 0
                                        while (i < len(result)):
                                                res = result[i]
                                                res.poll()
                                                if res.returncode != None:
                                                        del result[i]
                                                        continue
                                                i += 1
                                        time.sleep(0.5)
                                time.sleep(5)
                
                
#    for replicaP in replicaParam:
#        replicaId = []
#        for part in replicaP.split(','):
#            replicaId.append(part.split(':')[1].strip())
#        replicaStr = "_".join(replicaId)
#        print replicaStr
#
#
#
#        for prop in proportion:
#            for inscount in insertcount:
#                for opcount in operationcount: 
#                    for wait in waittime:
#                        for cnts in clientcount:
#                            clicnt = cnts[0]
#                            readclicnt = cnts[1]
#                            for readCons in readConsistencyLevel:
#                                for writeCons in writeConsistencyLevel:
#                                    waitTmp = wait.strip().split()
#                                    waitBase = waitTmp[1]
#                                    waitRandom = waitTmp[3]
#                                    print waitTmp
#
#                                    if replicaStr == "1" and (readCons != "ALL" or writeCons != "ALL"):
#                                        break
#                                    while True:
#                                            try:
#                                                    session.execute('drop keyspace if exists ycsb;', None)
#                                                    time.sleep(10)
#                                                    session.execute("create keyspace ycsb with replication = {'class' : " + topology + ", " + replicaP + "};", None)
#                                                    time.sleep(5)
#                                                    session.execute("use ycsb;", None)
#                                                    session.execute('create table usertable ( y_id varchar primary key, value varchar) WITH dclocal_read_repair_chance = 0.0 AND read_repair_chance = 0.0  AND speculative_retry = \'NONE\';', None)
#                                                    break
#                                            except:
#                                                    print time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime(time.time())) + "cannot connect to server"
#                                                    time.sleep(10)
#    
#                                                    
#                                                    
#                                    time.sleep(5)
#                                    load = subprocess.Popen(args=" ./ycsb load cassandra-cql -P ../workloads/workloada -P ../workloads/cassProperties -p workload=LoggingWorkload" + " -p " + prop + " -p insertcount=" + inscount + " -p operationcount=" + opcount + " -p cassandra.readconsistencylevel=" + readCons + " -p cassandra.writeconsistencylevel=" + writeCons + " -p clientcount=" + str(clicnt + readclicnt) + " -db MyCassandraDB", shell=True, cwd=".")
#                                    load.wait()
#                                    time.sleep(5)
#                                    uniqueNumber = random.sample(range(1000, 10000), clicnt + readclicnt)
#                                    # dir = "replica_factor" + replicaP[-1:] + "@" + prop[:14] + prop[16:19] + "@insertcount" + inscount + "@operationcount" + opcount + "@clientcount" + str(clicnt) + "@" + readCons + "@" + writeCons + "@" + time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime()) 
#                                    result = []
#
#                                    os.makedirs("./" + currenttime + "/" + replicaStr + "@" + prop[0:19] + "@inscount=" + inscount +"@opcount=" + opcount + "@readConsLevel=" + readCons + "@writeConsLevel=" + writeCons + "@clientcount=" + str(clicnt + readclicnt) + "@" + waitBase + "@" + waitRandom + "@repeat=" + str(run))
#
#                                    for uninum in uniqueNumber[0:clicnt]:
#                                        result.append(subprocess.Popen(args=" ./ycsb run cassandra-cql -P ../workloads/workloada -P ../workloads/cassProperties -p workload=LoggingWorkload" + " -p processId=" + str(uninum) + " -p " + prop + " -p insertcount=" + inscount + " -p operationcount=" + opcount + " -p recording=true" + " -p replica_factor=" + replicaStr + " -p cassandra.readconsistencylevel=" + readCons + " -p cassandra.writeconsistencylevel=" + writeCons + " -p clientcount=" + str(clicnt + readclicnt) + " -p time=" + currenttime + wait + " -p repeat=" + str(run) + " -db MyCassandraDB", shell=True, cwd="."))
#                                        time.sleep(0.2)
#                                    for uninum in uniqueNumber[clicnt:]:
#                                        result.append(subprocess.Popen(args=" ./ycsb run cassandra-cql -P ../workloads/workloada -P ../workloads/cassProperties -p workload=LoggingWorkload" + " -p processId=" + str(uninum) + " -p readproportion=1.00 -p updateproportion=0.00" + " -p lookproportion=" + prop[15:19] + " -p insertcount=" + inscount + " -p operationcount=" + opcount + " -p recording=true" + " -p replica_factor=" + replicaStr + " -p cassandra.readconsistencylevel=" + readCons + " -p cassandra.writeconsistencylevel=" + writeCons + " -p clientcount=" + str(clicnt + readclicnt) + " -p time=" + currenttime + wait + " -p repeat=" + str(run) + " -db MyCassandraDB", shell=True, cwd="."))
#                                        time.sleep(0.2)
#
#                                    while (len(result) > 0):
#                                        i = 0
#                                        while (i < len(result)):
#                                            res = result[i]
#                                            res.poll()
#                                            if res.returncode != None:
#                                                del result[i]
#                                                continue
#                                            i += 1
#                                        time.sleep(0.5)                                                                
#                                    time.sleep(10)

