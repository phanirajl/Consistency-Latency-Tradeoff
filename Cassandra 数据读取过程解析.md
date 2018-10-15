# Cassandra 数据读取过程解析

本文档简要解析Cassandra内部读取数据的流程，主要包括两部分：

* Cassandra内部读取数据的原过程

* 针对实验对读过程的修改
* 相关代码



## 数据读取

简单而言，Cassandra根据用户读请求的一致性水平(Consistency Level,简称CL)选择读取数据的方式。在SpeculativeRetry=NONE的设置下：

* CL=ONE: 只需等待一个节点的数据返回即可。向最近的一个副本节点发出DataRequest，请求完整数据。副本节点的远近距离由SnitchStrategy确定。

* CL>ONE: 比如TWO/QUORUM/ALL等. 假设CL所指定数量是R, 即至少需要等待R个副本数据返回，并需要满足R个数据一致性质方可完成读请求。Cassandra默认的流程是：先通过SnitchStrategy确定最近的R个副本节点，向最近的一个副本节点发送DataRequest请求完整数据，向剩下的(R-1)个节点发送DigestRequest请求摘要数据。

  * 如果返回的完整数据和所有摘要数据通过计算都满足一致，则直接返回完整数据，结束；

  * 若返回的数据中出现任何不一致，触发DigestMismatchException，待读修复完成后返回结果。

    > 读修复至少包括两轮：
    >
    > 1. CL=ALL的读请求，向所有副本节点发送完整数据读取请求DataRequest。通过返回的数据确定最新版本值，并记录需要修复的副本节点；
    > 2. 对版本陈旧的副本节点发送修复请求。

## 实验要求

实验需要满足：

* 准确&可调控的读写轮数。在读写轮数只有1和2的选项，实现中不可使用读修复；
* 在每一轮的节点访问过程中，只读取完整数据，不读摘要数据。

实验中设置CL = QUORUM, 需要改动的流程是：

* 读取R个完整数据，禁用摘要数据请求；
* 在merge过程中，禁用修复请求。



##  相关代码

### StorageProxy

存储服务代理org.apache.cassandra.service.StorageProxy 负责响应用户的读写请求，其通过协调其他节点来获取数据，并完成相应的数据存储，读取，更新操作。

其中关于用户读请求的部分相关代码：

```java
 /**
 Performs the actual reading of a row out of the StorageService, fetching a specific set of column names from a given column family.
 */
 
 public static PartitionIterator read(SinglePartitionReadCommand.Group group, ConsistencyLevel consistencyLevel, ClientState state)
    throws UnavailableException, IsBootstrappingException, ReadFailureException, ReadTimeoutException, InvalidRequestException
{
        if (StorageService.instance.isBootstrapMode() && !systemKeyspaceQuery(group.commands))
        {
            readMetrics.unavailables.mark();
            throw new IsBootstrappingException();
        }     
    return consistencyLevel.isSerialConsistency()
         ? readWithPaxos(group, consistencyLevel, state)
         : readRegular(group, consistencyLevel);  //注：非serial，执行此处
}

private static PartitionIterator readRegular(SinglePartitionReadCommand.Group group, ConsistencyLevel consistencyLevel)
throws UnavailableException, ReadFailureException, ReadTimeoutException
{
    long start = System.nanoTime();
    try
    {
    	//注：执行fetchRows()方法获得结果。
        PartitionIterator result = fetchRows(group.commands, consistencyLevel); 
        // If we have more than one command, then despite each read command honoring the limit, the total result
        // might not honor it and so we should enforce it
        if (group.commands.size() > 1)
            result = group.limits().filter(result, group.nowInSec());
        return result;
    }
    catch (UnavailableException e)
    {
        readMetrics.unavailables.mark();
        throw e;
    }
    catch (ReadTimeoutException e)
    {
        readMetrics.timeouts.mark();
        throw e;
    }
    catch (ReadFailureException e)
    {
        readMetrics.failures.mark();
        throw e;
    }
    finally
    {
        long latency = System.nanoTime() - start;
        readMetrics.addNano(latency);
        // TODO avoid giving every command the same latency number.  Can fix this in CASSADRA-5329
        for (ReadCommand command : group.commands)
	Keyspace.openAndGetStore(command.metadata()).metric.coordinatorReadLatency.update(latency, TimeUnit.NANOSECONDS);
    }
}
```
fetchaRows ()方法负责处理本地读取和跨节点远程读取过程，并等待结果返回。其主要包括以下几步：

1. 通过snitch的响应时间确定最近的R个节点
2. 向最近的一个节点请求完整数据，向剩余(R-1)个节点请求摘要信息
3. 等待R个数据返回
4. 如果任何返回数据发生不一致，触发读修复机制
5. 等待所有数据返回并返回结果

```java
/**
 * This function executes local and remote reads, and blocks for the results:
 *
 * 1. Get the replica locations, sorted by response time according to the snitch
 * 2. Send a data request to the closest replica, and digest requests to either
 *    a) all the replicas, if read repair is enabled
 *    b) the closest R-1 replicas, where R is the number required to satisfy the ConsistencyLevel
 * 3. Wait for a response from R replicas
 * 4. If the digests (if any) match the data return the data
 * 5. else carry out read repair by getting data from all the nodes.
 */
private static PartitionIterator fetchRows(List<SinglePartitionReadCommand> commands, ConsistencyLevel consistencyLevel)
throws UnavailableException, ReadFailureException, ReadTimeoutException
{
    int cmdCount = commands.size();

    SinglePartitionReadLifecycle[] reads = new SinglePartitionReadLifecycle[cmdCount];
    for (int i = 0; i < cmdCount; i++)
        reads[i] = new SinglePartitionReadLifecycle(commands.get(i), consistencyLevel);

    for (int i = 0; i < cmdCount; i++)
        reads[i].doInitialQueries();

    for (int i = 0; i < cmdCount; i++)
        reads[i].maybeTryAdditionalReplicas();

    for (int i = 0; i < cmdCount; i++)
        reads[i].awaitResultsAndRetryOnDigestMismatch();

    for (int i = 0; i < cmdCount; i++)
        if (!reads[i].isDone())
            reads[i].maybeAwaitFullDataRead();

    List<PartitionIterator> results = new ArrayList<>(cmdCount);
    for (int i = 0; i < cmdCount; i++)
    {
        assert reads[i].isDone();
        results.add(reads[i].getResult());
    }

    return PartitionIterators.concat(results);
}
```

```java
private static class SinglePartitionReadLifecycle
{
    private final SinglePartitionReadCommand command;
    private final AbstractReadExecutor executor;
    private final ConsistencyLevel consistency;

    private PartitionIterator result;
    private ReadCallback repairHandler;

    SinglePartitionReadLifecycle(SinglePartitionReadCommand command, ConsistencyLevel consistency)
    {
        this.command = command;
        this.executor = AbstractReadExecutor.getReadExecutor(command, consistency);
        this.consistency = consistency;
    }

    boolean isDone()
    {
        return result != null;
    }

    void doInitialQueries()
    {
        executor.executeAsync();
    }

    void maybeTryAdditionalReplicas()
    {
        executor.maybeTryAdditionalReplicas();
    }

    void awaitResultsAndRetryOnDigestMismatch() throws ReadFailureException, ReadTimeoutException
    {
        try
        {
            result = executor.get();
        }
        catch (DigestMismatchException ex)
        {
            Tracing.trace("Digest mismatch: {}", ex);

            ReadRepairMetrics.repairedBlocking.mark();


            // Do a full data read to resolve the correct response (and repair node that need be)
            Keyspace keyspace = Keyspace.open(command.metadata().ksName);
            DataResolver resolver = new DataResolver(keyspace, command, ConsistencyLevel.ALL, executor.handler.endpoints.size());
            repairHandler = new ReadCallback(resolver,
                                             ConsistencyLevel.ALL,
                                             executor.getContactedReplicas().size(),
                                             command,
                                             keyspace,
                                             executor.handler.endpoints);

            for (InetAddress endpoint : executor.getContactedReplicas())
            {
                MessageOut<ReadCommand> message = command.createMessage(MessagingService.instance().getVersion(endpoint));
                Tracing.trace("Enqueuing full data read to {}", endpoint);
                MessagingService.instance().sendRRWithFailure(message, endpoint, repairHandler);
                //MessagingService.instance().sendRR(message, endpoint, repairHandler);
            }
        }
    }

    void maybeAwaitFullDataRead() throws ReadTimeoutException
    {
        // There wasn't a digest mismatch, we're good
        if (repairHandler == null)
            return;

        // Otherwise, get the result from the full-data read and check that it's not a short read
        try
        {
            result = repairHandler.get();
        }
        catch (DigestMismatchException e)
        {
            throw new AssertionError(e); // full data requested from each node here, no digests should be sent
        }
        catch (ReadTimeoutException e)
        {
            if (Tracing.isTracing())
                Tracing.trace("Timed out waiting on digest mismatch repair requests");
            else
                logger.trace("Timed out waiting on digest mismatch repair requests");
            // the caught exception here will have CL.ALL from the repair command,
            // not whatever CL the initial command was at (CASSANDRA-7947)
            int blockFor = consistency.blockFor(Keyspace.open(command.metadata().ksName));
            throw new ReadTimeoutException(consistency, blockFor-1, blockFor, true);
        }
    }

    PartitionIterator getResult()
    {
        assert result != null;
        return result;
    }
}
```

### AbstractReadExecutor

```java
/**
 * @return an executor appropriate for the configured speculative read policy
 */
public static AbstractReadExecutor getReadExecutor(SinglePartitionReadCommand command, ConsistencyLevel consistencyLevel) throws UnavailableException
{
    Keyspace keyspace = Keyspace.open(command.metadata().ksName);
    List<InetAddress> allReplicas = StorageProxy.getLiveSortedEndpoints(keyspace, command.partitionKey());
    ReadRepairDecision repairDecision = command.metadata().newReadRepairDecision();
    List<InetAddress> targetReplicas = consistencyLevel.filterForQuery(keyspace, allReplicas, repairDecision);

    // Throw UAE early if we don't have enough replicas.
    consistencyLevel.assureSufficientLiveNodes(keyspace, targetReplicas);

    if (repairDecision != ReadRepairDecision.NONE)
    {
        Tracing.trace("Read-repair {}", repairDecision);
        ReadRepairMetrics.attempted.mark();
    }

    ColumnFamilyStore cfs = keyspace.getColumnFamilyStore(command.metadata().cfId);
    SpeculativeRetryParam retry = cfs.metadata.params.speculativeRetry;

    // Speculative retry is disabled *OR* there are simply no extra replicas to speculate.
    if (retry.equals(SpeculativeRetryParam.NONE) || consistencyLevel.blockFor(keyspace) == allReplicas.size())
        return new NeverSpeculatingReadExecutor(keyspace, command, consistencyLevel, targetReplicas);

    if (targetReplicas.size() == allReplicas.size())
    {
        // CL.ALL, RRD.GLOBAL or RRD.DC_LOCAL and a single-DC.
        // We are going to contact every node anyway, so ask for 2 full data requests instead of 1, for redundancy
        // (same amount of requests in total, but we turn 1 digest request into a full blown data request).
        return new AlwaysSpeculatingReadExecutor(keyspace, cfs, command, consistencyLevel, targetReplicas);
    }

    // RRD.NONE or RRD.DC_LOCAL w/ multiple DCs.
    InetAddress extraReplica = allReplicas.get(targetReplicas.size());
    // With repair decision DC_LOCAL all replicas/target replicas may be in different order, so
    // we might have to find a replacement that's not already in targetReplicas.
    if (repairDecision == ReadRepairDecision.DC_LOCAL && targetReplicas.contains(extraReplica))
    {
        for (InetAddress address : allReplicas)
        {
            if (!targetReplicas.contains(address))
            {
                extraReplica = address;
                break;
            }
        }
    }
    targetReplicas.add(extraReplica);

    if (retry.equals(SpeculativeRetryParam.ALWAYS))
        return new AlwaysSpeculatingReadExecutor(keyspace, cfs, command, consistencyLevel, targetReplicas);
    else // PERCENTILE or CUSTOM.
        return new SpeculatingReadExecutor(keyspace, cfs, command, consistencyLevel, targetReplicas);
}
```

```java
public static class NeverSpeculatingReadExecutor extends AbstractReadExecutor
    {
        public NeverSpeculatingReadExecutor(Keyspace keyspace, ReadCommand command, ConsistencyLevel consistencyLevel, List<InetAddress> targetReplicas)
        {
            super(keyspace, command, consistencyLevel, targetReplicas);
        }

/*        public void executeAsync()
        {
            makeDataRequests(targetReplicas.subList(0, 1));
            if (targetReplicas.size() > 1)
                makeDigestRequests(targetReplicas.subList(1, targetReplicas.size()));
        }
*/        
		//改动：向所有节点发送完整数据请求
        public void executeAsync()
        {
            makeDataRequests(targetReplicas.subList(0, targetReplicas.size()));
        }
        
        public void maybeTryAdditionalReplicas()
        {
            // no-op
        }

        public Collection<InetAddress> getContactedReplicas()
        {
            return targetReplicas;
        }
    }
```

```java
AbstractReadExecutor(Keyspace keyspace, ReadCommand command, ConsistencyLevel consistencyLevel, List<InetAddress> targetReplicas)
 {
     this.command = command;
     this.targetReplicas = targetReplicas;
    
     /*
     this.handler = new ReadCallback(new DigestResolver(keyspace, command, consistencyLevel, targetReplicas.size()), consistencyLevel, command, targetReplicas);
     */
     //改动：
     this.handler = new ReadCallback(new DataResolver(keyspace, command, consistencyLevel, targetReplicas.size()), consistencyLevel, command, targetReplicas);
     this.traceState = Tracing.instance.get();

     /*
     // Set the digest version (if we request some digests). This is the smallest version amongst all our target replicas since new nodes
     // knows how to produce older digest but the reverse is not true.
     // TODO: we need this when talking with pre-3.0 nodes. So if we preserve the digest format moving forward, we can get rid of this once
     // we stop being compatible with pre-3.0 nodes.
     int digestVersion = MessagingService.current_version;
     for (InetAddress replica : targetReplicas)
         digestVersion = Math.min(digestVersion, MessagingService.instance().getVersion(replica));
     command.setDigestVersion(digestVersion);
 	*/
 }
```

```java
protected void makeDataRequests(Iterable<InetAddress> endpoints)
{
    makeRequests(command, endpoints);

}

protected void makeDigestRequests(Iterable<InetAddress> endpoints)
{
    makeRequests(command.copy().setIsDigestQuery(true), endpoints);
}

private void makeRequests(ReadCommand readCommand, Iterable<InetAddress> endpoints)
{
    boolean hasLocalEndpoint = false;

    for (InetAddress endpoint : endpoints)
    {
        if (StorageProxy.canDoLocalRequest(endpoint))
        {
            hasLocalEndpoint = true;
            continue;
        }

        if (traceState != null)
            traceState.trace("reading {} from {}", readCommand.isDigestQuery() ? "digest" : "data", endpoint);
        logger.trace("reading {} from {}", readCommand.isDigestQuery() ? "digest" : "data", endpoint);
        MessageOut<ReadCommand> message = readCommand.createMessage(MessagingService.instance().getVersion(endpoint));
        MessagingService.instance().sendRRWithFailure(message, endpoint, handler);
        //MessagingService.instance().sendRR(message, endpoint, handler);
    }

    // We delay the local (potentially blocking) read till the end to avoid stalling remote requests.
    if (hasLocalEndpoint)
    {
        logger.trace("reading {} locally", readCommand.isDigestQuery() ? "digest" : "data");
        StageManager.getStage(Stage.READ).maybeExecuteImmediately(new LocalReadRunnable(command, handler));
    }
}
```



### DataResolver

```java
public PartitionIterator getData()
{
    ReadResponse response = responses.iterator().next().payload;
    return UnfilteredPartitionIterators.filter(response.makeIterator(command), command.nowInSec());
}

public PartitionIterator resolve()
{
    // We could get more responses while this method runs, which is ok (we're happy to ignore any response not here
    // at the beginning of this method), so grab the response count once and use that through the method.
    int count = responses.size();
    List<UnfilteredPartitionIterator> iters = new ArrayList<>(count);
    InetAddress[] sources = new InetAddress[count];
    for (int i = 0; i < count; i++)
    {
        MessageIn<ReadResponse> msg = responses.get(i);
        iters.add(msg.payload.makeIterator(command));
        sources[i] = msg.from;
    }

    // Even though every responses should honor the limit, we might have more than requested post reconciliation,
    // so ensure we're respecting the limit.
    DataLimits.Counter counter = command.limits().newCounter(command.nowInSec(), true);

    return counter.applyTo(mergeWithShortReadProtection(iters, sources, counter));
}
```

```java
private PartitionIterator mergeWithShortReadProtection(List<UnfilteredPartitionIterator> results, InetAddress[] sources, DataLimits.Counter resultCounter)
{
    // If we have only one results, there is no read repair to do and we can't get short reads
    if (results.size() == 1)
        return UnfilteredPartitionIterators.filter(results.get(0), command.nowInSec());

    UnfilteredPartitionIterators.MergeListener listener = new RepairMergeListener(sources);

    // So-called "short reads" stems from nodes returning only a subset of the results they have for a partition due to the limit,
    // but that subset not being enough post-reconciliation. So if we don't have limit, don't bother.
    if (!command.limits().isUnlimited())
    {
        for (int i = 0; i < results.size(); i++)
            results.set(i, Transformation.apply(results.get(i), new ShortReadProtection(sources[i], resultCounter)));
    }

    return UnfilteredPartitionIterators.mergeAndFilter(results, command.nowInSec(), listener);
}
```

```java
    private class RepairMergeListener implements UnfilteredPartitionIterators.MergeListener
    {
        private final InetAddress[] sources;

        public RepairMergeListener(InetAddress[] sources)
        {
            this.sources = sources;
        }

        public UnfilteredRowIterators.MergeListener getRowMergeListener(DecoratedKey partitionKey, List<UnfilteredRowIterator> versions)
        {
            return new MergeListener(partitionKey, columns(versions), isReversed(versions));
        }

        private PartitionColumns columns(List<UnfilteredRowIterator> versions)
        {
            Columns statics = Columns.NONE;
            Columns regulars = Columns.NONE;
            for (UnfilteredRowIterator iter : versions)
            {
                if (iter == null)
                    continue;

                PartitionColumns cols = iter.columns();
                statics = statics.mergeTo(cols.statics);
                regulars = regulars.mergeTo(cols.regulars);
            }
            return new PartitionColumns(statics, regulars);
        }

        private boolean isReversed(List<UnfilteredRowIterator> versions)
        {
            for (UnfilteredRowIterator iter : versions)
            {
                if (iter == null)
                    continue;

                // Everything will be in the same order
                return iter.isReverseOrder();
            }

            assert false : "Expected at least one iterator";
            return false;
        }

        public void close()
        {
            try
            {
                FBUtilities.waitOnFutures(repairResults, DatabaseDescriptor.getWriteRpcTimeout());
            }
            catch (TimeoutException ex)
            {
                // We got all responses, but timed out while repairing
                int blockFor = consistency.blockFor(keyspace);
                if (Tracing.isTracing())
                    Tracing.trace("Timed out while read-repairing after receiving all {} data and digest responses", blockFor);
                else
                    logger.debug("Timeout while read-repairing after receiving all {} data and digest responses", blockFor);

                throw new ReadTimeoutException(consistency, blockFor-1, blockFor, true);
            }
        }

        private class MergeListener implements UnfilteredRowIterators.MergeListener
        {
            private final DecoratedKey partitionKey;
            private final PartitionColumns columns;
            private final boolean isReversed;
            private final PartitionUpdate[] repairs = new PartitionUpdate[sources.length];

            private final Row.Builder[] currentRows = new Row.Builder[sources.length];
            private final RowDiffListener diffListener;

            private final ClusteringBound[] markerOpen = new ClusteringBound[sources.length];
            private final DeletionTime[] markerTime = new DeletionTime[sources.length];

            public MergeListener(DecoratedKey partitionKey, PartitionColumns columns, boolean isReversed)
            {
                this.partitionKey = partitionKey;
                this.columns = columns;
                this.isReversed = isReversed;

                this.diffListener = new RowDiffListener()
                {
                    public void onPrimaryKeyLivenessInfo(int i, Clustering clustering, LivenessInfo merged, LivenessInfo original)
                    {
                        if (merged != null && !merged.equals(original))
                            currentRow(i, clustering).addPrimaryKeyLivenessInfo(merged);
                    }

                    public void onDeletion(int i, Clustering clustering, Row.Deletion merged, Row.Deletion original)
                    {
                        if (merged != null && !merged.equals(original))
                            currentRow(i, clustering).addRowDeletion(merged);
                    }

                    public void onComplexDeletion(int i, Clustering clustering, ColumnDefinition column, DeletionTime merged, DeletionTime original)
                    {
                        if (merged != null && !merged.equals(original))
                            currentRow(i, clustering).addComplexDeletion(column, merged);
                    }

                    public void onCell(int i, Clustering clustering, Cell merged, Cell original)
                    {
                        if (merged != null && !merged.equals(original) && isQueried(merged))
                            currentRow(i, clustering).addCell(merged);
                    }

                    private boolean isQueried(Cell cell)
                    {
                        // When we read, we may have some cell that have been fetched but are not selected by the user. Those cells may
                        // have empty values as optimization (see CASSANDRA-10655) and hence they should not be included in the read-repair.
                        // This is fine since those columns are not actually requested by the user and are only present for the sake of CQL
                        // semantic (making sure we can always distinguish between a row that doesn't exist from one that do exist but has
                        /// no value for the column requested by the user) and so it won't be unexpected by the user that those columns are
                        // not repaired.
                        ColumnDefinition column = cell.column();
                        ColumnFilter filter = command.columnFilter();
                        return column.isComplex() ? filter.fetchedCellIsQueried(column, cell.path()) : filter.fetchedColumnIsQueried(column);
                    }
                };
            }

            private PartitionUpdate update(int i)
            {
                if (repairs[i] == null)
                    repairs[i] = new PartitionUpdate(command.metadata(), partitionKey, columns, 1);
                return repairs[i];
            }

            private Row.Builder currentRow(int i, Clustering clustering)
            {
                if (currentRows[i] == null)
                {
                    currentRows[i] = BTreeRow.sortedBuilder();
                    currentRows[i].newRow(clustering);
                }
                return currentRows[i];
            }
/*
            public void onMergedPartitionLevelDeletion(DeletionTime mergedDeletion, DeletionTime[] versions)
            {
                for (int i = 0; i < versions.length; i++)
                {
                    if (mergedDeletion.supersedes(versions[i]))
                        update(i).addPartitionDeletion(mergedDeletion);
                }
            }

            public void onMergedRows(Row merged, Row[] versions)
            {
                // If a row was shadowed post merged, it must be by a partition level or range tombstone, and we handle
                // those case directly in their respective methods (in other words, it would be inefficient to send a row
                // deletion as repair when we know we've already send a partition level or range tombstone that covers it).
                if (merged.isEmpty())
                    return;

                Rows.diff(diffListener, merged, versions);
                for (int i = 0; i < currentRows.length; i++)
                {
                    if (currentRows[i] != null)
                        update(i).add(currentRows[i].build());
                }
                Arrays.fill(currentRows, null);
            }

            public void onMergedRangeTombstoneMarkers(RangeTombstoneMarker merged, RangeTombstoneMarker[] versions)
            {
                for (int i = 0; i < versions.length; i++)
                {
                    RangeTombstoneMarker marker = versions[i];
                    // Note that boundaries are both close and open, so it's not one or the other
                    if (merged.isClose(isReversed) && markerOpen[i] != null)
                    {
                        ClusteringBound open = markerOpen[i];
                        ClusteringBound close = merged.closeBound(isReversed);
                        update(i).add(new RangeTombstone(Slice.make(isReversed ? close : open, isReversed ? open : close), markerTime[i]));
                    }
                    if (merged.isOpen(isReversed) && (marker == null || merged.openDeletionTime(isReversed).supersedes(marker.openDeletionTime(isReversed))))
                    {
                        markerOpen[i] = merged.openBound(isReversed);
                        markerTime[i] = merged.openDeletionTime(isReversed);
                    }
                }
            }

            public void close()
            {
                for (int i = 0; i < repairs.length; i++)
                {
                    if (repairs[i] == null)
                        continue;

                    // use a separate verb here because we don't want these to be get the white glove hint-
                    // on-timeout behavior that a "real" mutation gets
                    Tracing.trace("Sending read-repair-mutation to {}", sources[i]);

                    //
                    //MessageOut<Mutation> msg = new Mutation(repairs[i]).createMessage(MessagingService.Verb.READ_REPAIR);
                    //repairResults.add(MessagingService.instance().sendRR(msg, sources[i]));
                }
            }
*/

			//禁止自动修复。
            public void onMergedPartitionLevelDeletion(DeletionTime mergedDeletion, DeletionTime[] versions)
            {
            }

            public void onMergedRows(Row merged, Row[] versions)
            {
            }

            public void onMergedRangeTombstoneMarkers(RangeTombstoneMarker merged, RangeTombstoneMarker[] versions)
            {
            }

            public void close()
            {
            }

        }
    }
```

