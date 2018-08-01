
import os
from util import Op
from util import linkedList
from util import one_kv_rules

path=os.getcwd()
print path
#os.chdir(path)
cwd_files = os.listdir(os.getcwd())
print cwd_files


for trace_file in cwd_files:

	if trace_file[:16]!= "2018-07-31-23-51" or os.path.dirname(trace_file) == False:
		continue

	os.chdir(path+"/"+trace_file)
	print os.getcwd()
	sub_files = os.listdir(os.getcwd())
	print sub_files

	three_3_3=0
	three_1_1=0
	one_1_1=0
	fz=0
	bz=0
	sz=0
	for sub_file in sub_files:

		if sub_file[1]!= "_" or os.path.dirname(sub_file) == False:
			continue
		#print sub_file
		
		os.chdir(path+'/'+trace_file+'/'+sub_file)
		filelist = os.listdir(os.getcwd())

		ops=[]
		ops_props=[]

		
		#process 1:
		#get operations:		
		for filename in filelist:
			#if filename[0]!='t':
			#	continue
			ftrace = open(filename, "r")
			#print ftrace.name
			ops.extend(ftrace.readlines())

			ftrace.close()

		print len(ops)
		for operation in ops:
			ops_props.append(operation.strip().split("|||"))
			#print ops_props
		
		print len(ops_props)
		#process 2:
		#get zones:
		cluster_list={}
	
		for index,op in enumerate(ops_props):
			#print index
			#print op
			val = op[1]
			if cluster_list.has_key(val):
				cluster_list[val].min_finish = min(cluster_list[val].min_finish, op[4])
				cluster_list[val].max_start = max(cluster_list[val].max_start, op[3])
				if cluster_list[val].min_finish < cluster_list[val].max_start:
					cluster_list[val].zone_type = "forward"
				else:
					cluster_list[val].zone_type = "backward"	
				# if read ends before the dictated write:
				#
				#
				#	
			else:
				cluster_list[val] = linkedList.SingleLinkedList(val,op[4],op[3])
	
			newItem = Op.Op(index,op[2],op[3],op[4])			
			cluster_list[val].append(newItem)
		'''
		for k,v in cluster_list.items():
			print k
			print cluster_list[k].size()
			print cluster_list[k].travel()
		'''
		forward_zones=[]
		backward_zones=[]
		singles=[]
		for k,v in cluster_list.items():
			if cluster_list[k].zone_type=="forward":
				forward_zones.append(k)
			elif cluster_list[k].zone_type=="backward":
				backward_zones.append(k)
			else:
				singles.append(k)

		fz+=len(forward_zones)
		bz+=len(backward_zones)
		sz+=len(singles)
		print "forward zone :"+str(len(forward_zones))
		print "backward zone :"+str(len(backward_zones))
		print "single :"+str(len(singles))
		
		backward_zones.extend(singles)

	
		#process 3:
		#test k-atomicity, k=1,2,3...
	
		#3.1 brute force:
		#3.1.1 k=1:
	
		#comparing 2 forward zones:
		is_one_atomicity = True
		for i in range(len(forward_zones)-1):
			for j in range(i+1, len(forward_zones)):
				if one_kv_rules.one_kv_violation_fz(cluster_list[forward_zones[i]],cluster_list[forward_zones[j]]):
					is_one_atomicity = False
					break
		#comparing a forward zone and a backward zone:
		if is_one_atomicity == True:
			for i in forward_zones:
				for j in backward_zones:
					if one_kv_rules.one_kv_violation_fz_bz(cluster_list[i],cluster_list[j]):
						is_one_atomicity = False
						break

		if is_one_atomicity == True:
			print sub_file+" is atomic!"
		else:
			print sub_file+" is not atomic!" 
			if sub_file[:5]=="3_3_3":
				three_3_3+=1
			elif sub_file[:5]=="3_1_1":
				three_1_1+=1
			else:
				one_1_1+=1
		#3.1.2 k>1:
	
	
		#3.2 using interval tree and get trunks:
		#3.2.1 k=1:
	
		#3.2.2 k>1:
		#gpo for each chunk:
		'''
		T=set()
		U=set()
		k=2
		while true:
			B=[]
			for i in range(k):
				B.append(set())
			while size(U) > 0:
				for i in range(1,k):
					if(size(B[i])==i):
						l = i
						v = lambda x
	
	
		#CGS for each chunk:
	'''	
	print "3_3_3 not atomic num:"+str(three_3_3)
	print "3_1_1 not atomic num:"+str(three_1_1)
	print "1_1_1 not atomic num:"+str(one_1_1)
	print "fz num:"+str(fz)
	print "bz num:"+str(bz)
	print "sz num:"+str(sz)


		


			

	






	
