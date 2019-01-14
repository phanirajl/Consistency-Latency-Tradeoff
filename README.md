# Consistency-Latency-Tradeoff实验配置
本实验主要包括两部分：

1. 实验环境搭建：在单机上搭建Cassandra集群以模拟一个多数据中心的分布式存储环境

2. 􏳦􏲒 实验运行：通过脚本文件运行多个YCSB实例，生成不同负载条件下的trace运行记录，对运行记录进行数据处理与分析，得到最终可视化结果。


## 实验环境：Cassandra集群搭建

位于single-host-cassandra目录，包含：

- *install-cassandra.sh* : Cassandra集群拓扑配置脚本；
- *cassandra.sh* : Cassandra集群启动脚本；
- *stop.sh* : 中止Cassandra进程；
- *stop-and-delete.sh* : 中止Cassandra进程并删除所有节点数据；
- *cassandra*文件夹 :  包含Cassandra源码和相关启动脚本，本实验采用了基于apache-cassadnra-3.7扩展之后的Cassandra系统，部分功能存在修改和扩充，详情见文档《Cassandra扩展》。



### 部署与启动

#### Step 1

设置Cassandra集群拓扑结构，用户名，并对各节点进行资源分配与隔离。

`./install-cassandra.sh {username} {topo} [start_seq]`

* *username* : 用户名，用来标示并隔离不同用户的资源。 指定username之后，会在当前目录下创建一个名为*username_cluster*的文件夹，里面为各个节点分别生成一个数据文件夹；
* *topo* : 拓扑结构，用来分配集群中机器在各个数据中心中的数量。topo指定为以下数量的含义如下：
  * 3 : 创建一个单数据中心（默认为dc1）的集群，该dc中有3台虚拟的机器；配合Cassandra中的SimpleStrategy复制策略使用；
  * 3_3_3 :  创建一个3数据中心（默认为dc1, dc2, dc3）的集群，每个dc中各有3台虚拟的机器；通常配合Cassandra中的NetworkTopologyStrategy复制策略使用。注：不同DC间的机器数量用"_"分隔；
* *start_seq* : 我们采用本地回环地址为每台机器分配ip。若指定*start_seq*，则从地址127.0.0.*start_seq*开始为每台机器分配一个ip。若不指定，默认从127.0.0.71开始分配。

此外，每台机器的端口号默认从7201开始分配。



例如：创建一个user为oy，拓扑结构为3个DC，每个DC各有3个节点的集群，可以采用以下方式：

`./install-cassandra.sh oy 3_3_3 11` 

此时，即在当前目录下创建了一个名为*oy_cluster*的文件夹，里面包含了9个子文件夹，每个子文件夹对应一台Cassandra服务器。9台服务器中，dc1, dc2, dc3分别有3台机器，ip地址为：127.0.0.11～127.0.0.19，对应端口号为7201～7209。

此时，每个服务器的子文件夹包含:

* conf 文件夹: 内含服务器的配置文件，用于启动；
* data文件夹 : 存放数据库数据；
* hints文件夹 ： 存放数据库运行蝈车过程中产生的hinted-handoff数据；
* logs文件夹 : 存放运行时日志。



#### Step 2

启动Cassandra集群

`./cassandra.sh {username}`

* *username* : 用户名，用来选择**Step 1**中对应用户配置好的集群。



启动后，每个服务器文件夹会生成一个pid文件记录当前服务器进程号，在中断服务时使用。



### 中止服务

如果仅仅是中断所有服务器进程（日后仍可重启），可采用以下命令：

`./stop.sh {username}`

如果中断所有服务器进程并删除所有数据，命令如下：

`./stop-and-delete.sh {username}`

如果想要中止个别服务器进程，一种方法是直接查看某台机器对应pid并采用kill指令删除：

`sudo kill -9 {pid}`

还可以通过端口号查询对应进程pid并删除：

` lsof  -i:{port}`

或 

`netstat -nap | grep {port}`



## 实验运行

位于ycsb目录，主要包含：

- *bin* : 存放实验启动脚本，数据处理脚本，相关实验数据和实验结果
- *lib* : 实验中使用到的类文件
- *workload* :  负载文件，可通过脚本制定。
- *LICENSE.txt* : ycsb认证文件

#### Step 0 : 负载配置

*bin/conf.py* 脚本可供用户自定义实验参数和负载，详情见文档《ycsb负载设置》。注意，*bin/conf.py* 脚本内容直接影响trace生成模式和结果可视化结果。

#### Step 1 : 生成trace

`python bin/get_ycsb_traces.py {dirname}`

*  *dirname* : 目录名，运行后将在bin目录下生成名为 *dirname* 的文件夹用以存放数据信息和实验结果。

#### Step 2 : 计算k-atomiciy

`python bin/atomicity_latency_calculation.py {dirname} > {dirname}/{dirname}.txt ` 

#### Step 3 : 结果可视化

`python bin/get_ycsb_traces.py {dirname}`

结果可视化注意事项见《ycsb负载设置》。



此外，可通过直接运行以下命令自动化上述 Step1～3：

`./auto_Exec.sh {info}`

此时，会根据当前系统时间*current_time*在*bin*目录下创建名为*current_time_info*的文件夹用以存放数据信息和实验结果。

