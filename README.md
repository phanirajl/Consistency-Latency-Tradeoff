# Consistency-Latency-Tradeoff
Experiment of the Consistency-Latency Tradeoff Algorithm.

## Cassandra 配置


## YCSB 配置

### Workload层

...

### DB层

1. 更改DB类：

2. 实现读写算法：实现基于Quorum的1/2轮通信的读写算法，即：重写 READ/UPDATE(for existed key)/INSERT(for new key)方法。

   #### 2-round Read algorithm:

   > When reading data in the first round , read the responding timestamp at the same time. 
   >
   > Write back the value with the timestamp to a quorum of replicas.

   #### 1-round Read algorithm:

   > Reading data from a quorum of replicas.

   #### 2-round Write algorithm:

   > Ask for a quorum of timestamp in the first round. 
   >
   > Then,ver++.
   >
   > Update value with the new timestamp to a quorum of replicas.

   #### 1-round Write algorithm:

   > local ver++.
   >
   > Update value with the new local timestamp to a quorum of replicas.

3. 为了简化，在实验中将表格中的数据结构按照以下方式设置：

> 使用 (y_id text primary key , field0 text) 数据结构。即表中键y_id只有单个名为field0的column。
>
> 仅仅插入单个键值对
>
> 将算法中用到的版本号嵌入timestamp中：timestamp := < 32-bit ver, 32-bit pid > .
>
> 版本号在插入数据时初始化为<0, 0>

4. 存在问题：

>  未实现一轮写算法中在ack中携带版本号；

>  采用NetworkTopology拓扑策略，即Cassandra内部识别不同数据中心的节点。这种策略下的实现改动较少，只需要将读写一致性设置为Quorum，即可以通过Cassandra内部的转发机制实现算法。
>
> 存在风险：每个数据中心内有一个协调者负责向副本节点转发用户请求并收集结果返回给用户。与算法中所要求的“副本节点之间不通信”条件有些出入。不过。只要保证协调者非副本节点即可。

