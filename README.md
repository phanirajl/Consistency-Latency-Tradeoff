# Consistency-Latency-Tradeoff
Experiment of the Consistency-Latency Tradeoff Algorithm.

实验进度：

| 阶段                         | 目前进展                           |
| ---------------------------- | ---------------------------------- |
| Cassandra 配置               | 完成本地集群配置                   |
| YCSB 配置                    | 实现读写通信轮数可调配的Quorum算法 |
| k-atomicity 验证             | 待实现:GPO算法                     |
| Consistency-Latency Tradeoff | 待测                               |



## Cassandra 配置


## YCSB 配置

### Workload层

新建一个CLTradeoffWorkload继承CoreWorkload,改写其中的doInsert, doRead, doWrite方法。

### DB层

为了简化，在实验中将表格中的数据结构按照以下方式设置：

> 使用 (y_id text primary key , field0 text) 数据结构。即表中键y_id只有单个名为field0的column。
>
> 仅仅插入单个键值对
>
> 将算法中用到的版本号嵌入timestamp中：timestamp := < 32-bit ver, 32-bit pid > .
>
> 版本号在插入数据时初始化为<0, 0>

1. 创建CLTradeoffParam类：保存通信过程中所需要用到的参数，包括：返回值，版本号，读写通信轮数，ack中是否携带版本号等。

2. 更改DB类：新增三个抽象函数实现实验中所要求的数据结构。在参数中携带

3. 更改DBWrapper：继承DB类，新增针对实验所要求的数据类型参数的insert,read,update方法。

4. 实现读写算法：实现基于Quorum的1/2轮通信的读写算法，即：重写 READ/UPDATE(for existed key)/INSERT(for new key)方法。

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

5. 存在问题：

   * 未实现一轮写算法中在ack中携带版本号；
   * 采用NetworkTopology拓扑策略，即Cassandra内部识别不同数据中心的节点。这种策略下的实现改动较少，只需要将读写一致性设置为Quorum，即可以通过Cassandra内部的转发机制实现算法。存在风险：每个数据中心内有一个协调者负责向副本节点转发用户请求并收集结果返回给用户。与算法中所要求的“副本节点之间不通信”条件有些出入。（不过，如果可以保证协调者非副本节点即可？）


# k-atomicity 验证

k-atomicity验证算法

1. 获取trace.
2. 将trace中的operation根据读写的value区分成一个个cluster，对每个cluster区分forward/backward zone.
3. 处理chunk, 采用FZF(Forward Zone First)算法[1][1]。高效实现需要用到interval tree结构（正在实现这步）
4. 对每个chunk使用GPO算法[2][2]。



[1]: Golab W, Hurwitz J, Li X. On the k-atomicity-verification problem[C]//Distributed Computing Systems (ICDCS), 2013 IEEE 33rd International Conference on. IEEE, 2013: 591-600.

[2]: Golab W, Li X S, López-Ortiz A, et al. Computing weak consistency in polynomial time[C]//Proceedings of the 2015 ACM Symposium on Principles of Distributed Computing. ACM, 2015: 395-404.

