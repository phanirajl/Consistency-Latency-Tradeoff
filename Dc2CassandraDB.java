import com.datastax.driver.core.Cluster;
import com.datastax.driver.core.ColumnDefinitions;
import com.datastax.driver.core.ConsistencyLevel;
import com.datastax.driver.core.Host;
import com.datastax.driver.core.HostDistance;
import com.datastax.driver.core.Metadata;
import com.datastax.driver.core.ResultSet;
import com.datastax.driver.core.Row;
import com.datastax.driver.core.Session;
import com.datastax.driver.core.SimpleStatement;
import com.datastax.driver.core.Statement;
import com.datastax.driver.core.ColumnDefinitions.Definition;
import com.datastax.driver.core.policies.DCAwareRoundRobinPolicy;
import com.datastax.driver.core.policies.TokenAwarePolicy;
import com.datastax.driver.core.querybuilder.Insert;
import com.datastax.driver.core.querybuilder.QueryBuilder;
import com.datastax.driver.core.querybuilder.Select.Builder;
import com.datastax.driver.core.querybuilder.Select.Selection;
import com.yahoo.ycsb.ByteArrayByteIterator;
import com.yahoo.ycsb.ByteIterator;
import com.yahoo.ycsb.DB;
import com.yahoo.ycsb.DBException;
import com.yahoo.ycsb.Status;
import java.nio.ByteBuffer;
import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;
import java.util.Set;
import java.util.Vector;
import java.util.Map.Entry;
import java.util.concurrent.atomic.AtomicInteger;

public class Dc2CassandraDB extends DB {
  private static Cluster cluster = null;
  private static Session session = null;
  private static ConsistencyLevel readConsistencyLevel;
  private static ConsistencyLevel writeConsistencyLevel;
  private static boolean TwoQuorumRound;
  public static final String YCSB_KEY = "y_id";
  public static final String KEYSPACE_PROPERTY = "cassandra.keyspace";
  public static final String KEYSPACE_PROPERTY_DEFAULT = "ycsb";
  public static final String USERNAME_PROPERTY = "cassandra.username";
  public static final String PASSWORD_PROPERTY = "cassandra.password";
  public static final String HOSTS_PROPERTY = "hosts";
  public static final String PORT_PROPERTY = "port";
  public static final String PORT_PROPERTY_DEFAULT = "9042";
  public static final String READ_CONSISTENCY_LEVEL_PROPERTY = "cassandra.readconsistencylevel";
  public static final String READ_CONSISTENCY_LEVEL_PROPERTY_DEFAULT = "ONE";
  public static final String WRITE_CONSISTENCY_LEVEL_PROPERTY = "cassandra.writeconsistencylevel";
  public static final String WRITE_CONSISTENCY_LEVEL_PROPERTY_DEFAULT = "ONE";
  public static final String MAX_CONNECTIONS_PROPERTY = "cassandra.maxconnections";
  public static final String CORE_CONNECTIONS_PROPERTY = "cassandra.coreconnections";
  public static final String CONNECT_TIMEOUT_MILLIS_PROPERTY = "cassandra.connecttimeoutmillis";
  public static final String READ_TIMEOUT_MILLIS_PROPERTY = "cassandra.readtimeoutmillis";
  public static final String TRACING_PROPERTY = "cassandra.tracing";
  public static final String TRACING_PROPERTY_DEFAULT = "false";
  private static final AtomicInteger INIT_COUNT;
  private static boolean debug;
  private static boolean trace;

  private static HashMap localVer=new HashMap();

  public Dc2CassandraDB() {
  }

  public void init() throws DBException {
    INIT_COUNT.incrementAndGet();
    AtomicInteger var1 = INIT_COUNT;
    synchronized(INIT_COUNT) {
      if (cluster == null) {
        try {
          debug = Boolean.parseBoolean(this.getProperties().getProperty("debug", "false"));
          trace = Boolean.valueOf(this.getProperties().getProperty("cassandra.tracing", "false")).booleanValue();
          String host = this.getProperties().getProperty("hosts");
          if (host == null) {
            throw new DBException(String.format("Required property \"%s\" missing for CassandraCQLClient", "hosts"));
          } else {
            String[] hosts = host.split(",");
            String port = this.getProperties().getProperty("port", "9042");
            String username = this.getProperties().getProperty("cassandra.username");
            String password = this.getProperties().getProperty("cassandra.password");
            String keyspace = this.getProperties().getProperty("cassandra.keyspace", "ycsb");
            readConsistencyLevel = ConsistencyLevel.valueOf(this.getProperties().getProperty("cassandra.readconsistencylevel", "ONE"));
            writeConsistencyLevel = ConsistencyLevel.valueOf(this.getProperties().getProperty("cassandra.writeconsistencylevel", "ONE"));
            if (username != null && !username.isEmpty()) {
              cluster = Cluster.builder().withCredentials(username, password).withPort(Integer.valueOf(port).intValue()).addContactPoints(hosts).withLoadBalancingPolicy(new TokenAwarePolicy(DCAwareRoundRobinPolicy.builder().withUsedHostsPerRemoteDc(2).build())).build();
            } else {
              cluster = Cluster.builder().withPort(Integer.valueOf(port).intValue()).addContactPoints(hosts).withLoadBalancingPolicy(new TokenAwarePolicy(DCAwareRoundRobinPolicy.builder().withUsedHostsPerRemoteDc(2).build())).build();
            }

            String maxConnections = this.getProperties().getProperty("cassandra.maxconnections");
            if (maxConnections != null) {
              cluster.getConfiguration().getPoolingOptions().setMaxConnectionsPerHost(HostDistance.LOCAL, Integer.valueOf(maxConnections).intValue());
            }

            String coreConnections = this.getProperties().getProperty("cassandra.coreconnections");
            if (coreConnections != null) {
              cluster.getConfiguration().getPoolingOptions().setCoreConnectionsPerHost(HostDistance.LOCAL, Integer.valueOf(coreConnections).intValue());
            }

            String connectTimoutMillis = this.getProperties().getProperty("cassandra.connecttimeoutmillis");
            if (connectTimoutMillis != null) {
              cluster.getConfiguration().getSocketOptions().setConnectTimeoutMillis(Integer.valueOf(connectTimoutMillis).intValue());
            }

            String readTimoutMillis = this.getProperties().getProperty("cassandra.readtimeoutmillis");
            if (readTimoutMillis != null) {
              cluster.getConfiguration().getSocketOptions().setReadTimeoutMillis(Integer.valueOf(readTimoutMillis).intValue());
            }

            Metadata metadata = cluster.getMetadata();
            System.err.printf("Connected to cluster: %s\n", metadata.getClusterName());
            Iterator var13 = metadata.getAllHosts().iterator();

            while(var13.hasNext()) {
              Host discoveredHost = (Host)var13.next();
              System.out.printf("Datacenter: %s; Host: %s; Rack: %s\n", discoveredHost.getDatacenter(), discoveredHost.getAddress(), discoveredHost.getRack());
            }

            session = cluster.connect(keyspace);
          }
        } catch (Exception var16) {
          throw new DBException(var16);
        }
      }
    }
  }

  public void cleanup() throws DBException {
    AtomicInteger var1 = INIT_COUNT;
    synchronized(INIT_COUNT) {
      int curInitCount = INIT_COUNT.decrementAndGet();
      if (curInitCount <= 0) {
        session.close();
        cluster.close();
        cluster = null;
        session = null;
      }

      if (curInitCount < 0) {
        throw new DBException(String.format("initCount is negative: %d", curInitCount));
      }
    }
  }

  //Attention: Query operation for single text-type column named "value". That is, the Set "fields" only has one element.
  public Status read(String table, String key, Set<String> fields, Map<String, ByteIterator> result) {
    try {
      Object selectBuilder;
      String col=new String("value");
      if (fields == null) {
        selectBuilder = QueryBuilder.select().all();
      } else {
        selectBuilder = QueryBuilder.select();
        Iterator var7 = fields.iterator();

        while(var7.hasNext()) {
          col = (String)var7.next();
          ((Selection)selectBuilder).column(col).writeTime(col);//add writeTime
        }
      }

      Statement stmt = ((Builder)selectBuilder).from(table).where(QueryBuilder.eq("y_id", key)).limit(1);
      stmt.setConsistencyLevel(readConsistencyLevel);

      if (debug) {
        System.out.println(stmt.toString());
      }

      if (trace) {
        stmt.enableTracing();
      }

      ResultSet rs = session.execute(stmt);
      if (rs.isExhausted()) {
        return Status.NOT_FOUND;
      }

      Row row = rs.one();
      ColumnDefinitions cd = row.getColumnDefinitions();
      Iterator var10 = cd.iterator();
      while(var10.hasNext()) {
        Definition def = (Definition)var10.next();
        ByteBuffer val = row.getBytesUnsafe(def.getName());
        if (val != null) {
          result.put(def.getName(), new ByteArrayByteIterator(val.array()));
        } else {
          result.put(def.getName(), (Object)null);
        }
      }

      if(TwoQuorumRound){
        //writeback:

        Insert insertStmt = QueryBuilder.insertInto(table).value("y_id", key).value(col,row.getString(col));
        insertStmt.setDefaultTimestamp(row.getTime("writetime("+col+")"));
        insertStmt.setConsistencyLevel(writeConsistencyLevel);
        if (debug) {
          System.out.println(insertStmt.toString());
        }

        if (trace) {
          insertStmt.enableTracing();
        }

        session.execute(insertStmt);

      }

      return Status.OK;
    } catch (Exception var13) {
      var13.printStackTrace();
      System.out.println("Error reading key: " + key);
      return Status.ERROR;
    }
  }

  public Status scan(String table, String startkey, int recordcount, Set<String> fields, Vector<HashMap<String, ByteIterator>> result) {
    try {
      Object selectBuilder;
      if (fields == null) {
        selectBuilder = QueryBuilder.select().all();
      } else {
        selectBuilder = QueryBuilder.select();
        Iterator var8 = fields.iterator();

        while(var8.hasNext()) {
          String col = (String)var8.next();
          ((Selection)selectBuilder).column(col);
        }
      }

      Statement stmt = ((Builder)selectBuilder).from(table);
      String initialStmt = stmt.toString();
      StringBuilder scanStmt = new StringBuilder();
      scanStmt.append(initialStmt.substring(0, initialStmt.length() - 1));
      scanStmt.append(" WHERE ");
      scanStmt.append(QueryBuilder.token("y_id"));
      scanStmt.append(" >= ");
      scanStmt.append("token('");
      scanStmt.append(startkey);
      scanStmt.append("')");
      scanStmt.append(" LIMIT ");
      scanStmt.append(recordcount);
      Statement stmt = new SimpleStatement(scanStmt.toString());
      stmt.setConsistencyLevel(readConsistencyLevel);
      if (debug) {
        System.out.println(stmt.toString());
      }

      if (trace) {
        stmt.enableTracing();
      }

      ResultSet rs = session.execute(stmt);

      while(!rs.isExhausted()) {
        Row row = rs.one();
        HashMap<String, ByteIterator> tuple = new HashMap();
        ColumnDefinitions cd = row.getColumnDefinitions();
        Iterator var14 = cd.iterator();

        while(var14.hasNext()) {
          Definition def = (Definition)var14.next();
          ByteBuffer val = row.getBytesUnsafe(def.getName());
          if (val != null) {
            tuple.put(def.getName(), new ByteArrayByteIterator(val.array()));
          } else {
            tuple.put(def.getName(), (Object)null);
          }
        }

        result.add(tuple);
      }

      return Status.OK;
    } catch (Exception var17) {
      var17.printStackTrace();
      System.out.println("Error scanning with startkey: " + startkey);
      return Status.ERROR;
    }
  }

  //Attention: Update operation for existed single text-type column named "value". That is, the Hashmap "values" only has one pair.
  public Status update(String table, String key, Map<String, ByteIterator> values) {

    try {

      String col = "value";

      long ver = localVer.containsKey(key) ?Long.valueOf(String.valueOf(localVer.get(key))).longValue(): 0L ;

      if(TwoQuorumRound){

        // Query writetime:
        Object selectBuilder;
        selectBuilder = QueryBuilder.select();

        //Only used for single column query.
        for (Entry<String, ByteIterator> entry : values.entrySet()) {
          col =entry.getKey();
          ((Selection)selectBuilder).writeTime(col);
        }

        //query timestamp/version:
        Statement stmt = ((Builder)selectBuilder).from(table).where(QueryBuilder.eq("y_id", key)).limit(1);
        stmt.setConsistencyLevel(readConsistencyLevel);

        if (debug) {
          System.out.println(stmt.toString());
        }

        if (trace) {
          stmt.enableTracing();
        }

        ResultSet rs = session.execute(stmt);
        if (rs.isExhausted()) {
          return Status.NOT_FOUND;
        }

        Row row = rs.one();
        ver = row.getTime("writetime("+col+")") ;

      }

      //updateVersion:
      ver = ver + 1;
      localVer.put(key , ver);

      Insert insertStmt = QueryBuilder.insertInto(table);
      insertStmt.value("y_id", key);
      Iterator var5 = values.entrySet().iterator();

      while(var5.hasNext()) {
        Entry<String, ByteIterator> entry = (Entry)var5.next();
        ByteIterator byteIterator = (ByteIterator)entry.getValue();
        Object value = byteIterator.toString();
        insertStmt.value((String)entry.getKey(), value);
      }

      insertStmt.setDefaultTimestamp(ver);
      insertStmt.setConsistencyLevel(writeConsistencyLevel);
      if (debug) {
        System.out.println(insertStmt.toString());
      }

      if (trace) {
        insertStmt.enableTracing();
      }

      session.execute(insertStmt);
      return Status.OK;
    } catch (Exception var9) {
      var9.printStackTrace();
      return Status.ERROR;
    }
  }

  public Status insert(String table, String key, Map<String, ByteIterator> values) {
    try {
      Insert insertStmt = QueryBuilder.insertInto(table);
      insertStmt.value("y_id", key);
      Iterator var5 = values.entrySet().iterator();

      while(var5.hasNext()) {
        Entry<String, ByteIterator> entry = (Entry)var5.next();
        ByteIterator byteIterator = (ByteIterator)entry.getValue();
        Object value = byteIterator.toString();
        insertStmt.value((String)entry.getKey(), value);
      }

      insertStmt.setConsistencyLevel(writeConsistencyLevel);
      if (debug) {
        System.out.println(insertStmt.toString());
      }

      if (trace) {
        insertStmt.enableTracing();
      }

      session.execute(insertStmt);
      return Status.OK;
    } catch (Exception var9) {
      var9.printStackTrace();
      return Status.ERROR;
    }
  }

  public Status delete(String table, String key) {
    try {
      Statement stmt = QueryBuilder.delete().from(table).where(QueryBuilder.eq("y_id", key));
      stmt.setConsistencyLevel(writeConsistencyLevel);
      if (debug) {
        System.out.println(stmt.toString());
      }

      if (trace) {
        stmt.enableTracing();
      }

      session.execute(stmt);
      return Status.OK;
    } catch (Exception var4) {
      var4.printStackTrace();
      System.out.println("Error deleting key: " + key);
      return Status.ERROR;
    }
  }

  static {
    readConsistencyLevel = ConsistencyLevel.QUORUM;
    writeConsistencyLevel = ConsistencyLevel.QUORUM;
    INIT_COUNT = new AtomicInteger(0);
    debug = false;
    trace = false;
    TwoQuorumRound = true;
  }
}
