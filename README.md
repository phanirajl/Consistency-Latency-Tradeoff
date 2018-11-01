# Consistency-Latency-Tradeoff
本实验在本地沙盒和阿里云两套集群环境中分别进行，通过一系列基于Quorum复制机制的读写算法，采用YCSB数据库测试工具，生成不同参数下的目标trace，并对这些trace进行一致性测定和延迟统计，从而发现一致性和访问延迟之间的权衡关系，并对理论模型进行模拟和验证。

实验主要包括以下内容：

1. Cassandra源码改动
2. Cassandra配置
3. YCSB配置
4. *k*-atomicity验证
5. 一致性-延迟权衡

目前实验进度：

| 阶段                         | 目前进展                              |
| ---------------------------- | ------------------------------------- |
| Cassandra源码修改            | 完成相关优化措施的禁用                |
| Cassandra 配置               | 完成本地集群配置                      |
| YCSB 配置                    | 实现读写通信轮数可调配的Quorum算法    |
| *k*-atomicity 验证           | 已实现验证atomicity算法，待实现：k-av |
| Consistency-Latency Tradeoff | 测出初步结果                          |

当前计划：

* 实现*k*-av验证算法。
* 确定最终实验计划。



## Cassandra源码改动

Cassandra内部存在非常多针对系统性能的优化措施，比如：

> 为了减少读操作的延迟，当读请求的一致性级别CL>ONE时，采用了摘要读过程（digest read），即只读一个最近副本的原始数据，剩下副本读取摘要数据，以减小数据传输量，加快读取速度；
>
> 为了保证满足一致性等级，当发现读到的多个副本数据中存在不一致时，会强制将所有副本修复到一致性的最高强度（Consistency level=ALL），然后再读取其中一个副本数据。

事实上，上述两个读过程优化设计的例子其实就隐含着微妙的一致性和访问延迟之间的权衡问题。比如，摘要读可以保证大部分情况下的低延迟返回，但是一旦出现了不一致的情况，系统这时就无法从摘要读中确定哪个副本是最新值了，此时不得不再次进行通信。这额外的通信已经导致低延迟无法保持了，不如干脆做个强制的读修复以保证更高的一致性，而这又可以提高之后读请求中的摘要读成功概率。

开发者必然是做了充分多的测试来验证这样的优化措施在真实的生产环境中足以提高整个系统的性能。不过，在我们的实验中，为了更加理想地接近我们的理论模型，充分反映我们建模的合理性和准确性，我们需要将一些优化措施禁止掉。同时，为了更加准确地反应Cassandra的真实性能，我们将会额外进行真实性能测试，并进行一系列的对比。因此，实验计划分为两部分：

> 1. 禁用Cassandra内部相关优化措施进行测试以模拟理论模型
> 2. 直接使用Casandra进行测试以反映真实性能

实验过程中，主要针对W2R1算法，发现出现较少non-atomic结果的情况（与理论结果些许不符）。

考虑以下原因：

- 参考已有初步实验结论：服务器之间延迟越大，不一致性出现的情况越多。计划增加Cassandra中服务器之间的延迟进行试验；

- Cassandra内部优化措施如读修复未完全关闭（当一致性级别CL=QUORUM时，系统的读修复是在读请求的过程中自动触发的。参考[set read repair chance to 0 but find read repair process in trace](https://issues.apache.org/jira/browse/CASSANDRA-11409)）。简单而言，Cassandra的读修复是读操作发生时的副本同步技术，分为**前台读修复**和**后台读修复**。

  > **前台读修复**：
  >
  > 当一致性级别CL>ONE时， Cassandra的读请求过程中会访问多个副本数据，若出现数据不一致（ digest mismatch）的情况，会自动引发前台读修复，此时*所有*（存疑）具有该数据的副本节点都会被访问到并且进行数据修复，待修复完成后才会返回数据给客户端。
  >
  > **后台读修复**：
  >
  > 当一致性级别CL=ONE时，先返回数据给客户端，再进行读修复。整个修复流程发生在后台，不会阻塞响应返回。后台读修复会修复所有副本。
  >
  > **注**：
  >
  > *dclocal_read_repair_chance*和*read_repair_chance*是设置**后台读修复**的机率参数，即使设置`dclocal_read_repair_chance=0 `和`  read_repair_chance=0`，前台读修复也会在一致性级别CL>ONE时且出现数据不一致（ digest mismatch）的情况下引发，要禁用此功能需要修改源码。

  潜在解决方案：

  - 放弃Cassandra自带的QUORUM读写机制，重写客户端，Consistency Level设置为ONE（此时只返回一个副本节点，不会触发读修复）。自定义实现QUORUM通信和副本比较机制。
  - （推荐）修改源码。需要将所有触发读修复的机制全取消。具体实现见[Cassandra 数据读取过程解析](https://github.com/Lingzhi-Ouyang/Consistency-Latency-Tradeoff/blob/master/Cassandra%20数据读取过程解析.md)一文需要注意以下事项：
    - 由于Cassandra在CL=QUORUM的读过程中只读取个别副本的完整数据（speculative_retry = NONE时），剩下副本读取digest进行比较是否一致（发生不一致时再进行一次对所有副本的完整数据读取兼修复，即前台读修复原理），因此，实验中需要将读过程变成不进行读修复的一轮通信过程，即向所有的副本发送完整读请求（makeDataRequests）而非摘要请求（makeDigestRequests）,通过比较版本号直接返回最新版本的数据而不触发读修复。





## Cassandra 配置

### 本地沙盒

见single-host-cassandra目录，主要包括：

- *install-cassandra.sh*: 生成指定用户的资源。

  `./install-cassandra.sh {cname} {uname} {num} [networktopology] `

  其中 多数据中心默认3中心。

- *cassandra-env.sh*: 启动cassandra，并设置相关环境变量。

  `./cassandra-env.sh {uname} [random params]`

- *stop.sh* & *stop-and-delete.sh*: 停止Cassandra进程（并删除所有内容）

  `./stop-delete.sh {uname} `

- cassandra: 包含Cassandra源码和相关启动脚本，本实验中对*read repair*相关功能做了修改（禁止在Consistency level = Quorum的一致性条件发现DigestMismatch时启动修复功能）修改源码后，使用ant对cassandra进行编译，结果主要体现在*build/apache-cassandra-3.x-[xxx].jar, build/apache-cassandra-thrift-3.x-[xxx].jar*中。



### 阿里云





## YCSB 配置

见ycsb-0.12.0目录。主要包括运行ycsb测试框架的脚本文件，DB层和负载层配置等。

* *bin/BatchExec.py*: 启动YCSB，配置相关负载参数。
* *lib*: 类文件。主要改写的代码包括workload层和DB层。
* *workload*: 基本负载参数可在此目录下文件中设定，在脚本文件中调用。

### Workload层

Workload层实现定制化的负载生成服务。负载参数如读写比例，频率等都在本层进行设定。

新建一个CLTradeoffWorkload继承CoreWorkload, 改写其中的doInsert, doRead, doWrite方法。

### DB层

DB层负责调用数据库的客户端借口进行实际数据库操作。本实验中多轮通信的子过程都在DB层实现。

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
   * 采用NetworkTopology拓扑策略，即Cassandra内部识别不同数据中心的节点。这种策略下的实现改动较少，只需要将读写一致性设置为Quorum，即可以通过Cassandra内部的转发机制实现算法。存在风险：每个数据中心内有一个协调者负责向副本节点转发用户请求并收集结果返回给用户，即副本节点之间存在角色分工。与算法中所要求的“副本节点之间不通信”条件有些出入。（不过，如果保证协调者只负责数据的转发和收集，对算法影响较小。）



## 实验参数

### Cassandra 影响参数

* 服务器之间的延迟：

* 网络拓扑(replication strategy) & 副本数量(replica factor)：设定为3_3_3, 3_1_1, 1_1_1 三组。

* 跨数据中心服务器的网络延迟：

* 读写一致性程度：QUORUM

* 读修复：禁止，即设置：

  `dclocal_read_repair_chance=0 `

  `  read_repair_chance=0`

* caching: 禁止，即在创建keyspace时设置：

  `... WITH caching = { 'keys' : 'NONE', 'rows_per_partition' : 'NONE' };`


### YCSB影响参数

* 读写用户数：
* 读写吞吐率：
* 客户端和服务器的网络延迟：
* 通信轮数：read round/ write round = 1 or 2

### 参数默认值设置

|                                  | Write  | Read   |
| -------------------------------- | ------ | ------ |
| Consistency level                | QUORUM | QUORUM |
| Quorum-based communication round | 1/2    | 1/2    |
| qps                              | 50     | 1000   |
| Client num                       | 10     | 10     |

|                                     | Default    |
| ----------------------------------- | ---------- |
| Replication Strategy                | 1_1_1      |
| Delay between servers & clients/ms  | 0          |
| Delay between servers across DCs/ms | 30         |
| Read repair chance(local/DC)        | 0          |
| Load Balance Strategy               | RoundRobin |



## k-atomicity 验证

### 预处理

1. 获取trace.
2. 将trace中的operation根据读写的value区分成一个个cluster，对每个cluster区分forward/backward zone.

### Atomicity 验证算法

采用算法[1][1],  一个trace非atomic 等价于 存在下列两种情况之一：

1. 存在两个forward zone 相交
2. 存在一个forward zone 包含某个backward zone.

### k-atomicity验证算法

1. 处理chunk, 采用FZF(Forward Zone First)算法[2][2]。高效实现需要用到interval tree结构（正在实现这步）
2. 对每个chunk使用GPO算法[3][3]。

[1]: Phillip B. Gibbons and Ephraim Korach. 1997. Testing Shared Memories. Society for Industrial and Applied Mathematics, pp 1208-1244, 1997.

[2]: Golab W, Hurwitz J, Li X. On the k-atomicity-verification problem[C]//Distributed Computing Systems (ICDCS), 2013 IEEE 33rd International Conference on. IEEE, 2013: 591-600.

[3]: Golab W, Li X S, López-Ortiz A, et al. Computing weak consistency in polynomial time[C]//Proceedings of the 2015 ACM Symposium on Principles of Distributed Computing. ACM, 2015: 395-404.



## 一致性-延迟之间的权衡

### 实验一  理论模型验证

采用参数默认值配置，得到的实验结果如下（2018.10.31）：

| Algorithm | Write Latency/ms | Read Latency/ms | Atomicity violation Probability |
| --------- | ---------------- | --------------- | ------------------------------- |
| W2R2      | 215              | 211             | 0/265554=0                      |
| W2R1      | 218              | 104             | 6/2174423≈0.0000028=2.8e-6      |
| W1R2      | 112              | 211             | 13850/265506≈0.052              |

注：

1. 一致性违反概率暂时采用出现一致性违反的读写对数量占总的读数量而定，而不是*k*-ato规则（算法暂时未实现）。
2. W1R2算法虽然出现读到陈旧值的概率不高，但是会出现大部分写操作无法成功写入值的情况，因此实用性不高（需要另外选取衡量写入成功概率的指标）。

### 实验二  Cassandra真实性能验证



