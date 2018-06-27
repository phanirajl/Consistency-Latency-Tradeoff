# Consistency-Latency-Tradeoff
Experiment of the Consistency-Latency Tradeoff Algorithm.

#YCSB

Implement 2-round Quorum-based Algorithm.
Specifically, modify READ/UPDATE(for existed key)/INSERT(for new key) method.

###Attention:

> Use (key text, value text) structure.
>
> Use Timestamp as "version" described in the algorithm.

###Read algorithm:

> When reading data in the first round , read the responding timestamp at the same time. 
>
> Write back the value with the timestamp to a quorum of replicas.

###Write algorithm:

> Ask for a quorum of timestamp in the first round. 
>
> Then,timestamp++.
>
> Update value with the new timestamp to a quorum of replicas.



