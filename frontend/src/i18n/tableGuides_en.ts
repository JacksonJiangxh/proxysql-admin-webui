/**
 * ProxySQL Table Browser — Beginner's Guide (English)
 *
 * Each entry explains in plain language:
 * - What this table is for
 * - What data it contains
 * - When you might need to view or modify it
 *
 * Key naming: tables.guide.<table_name>
 */
export const tableGuidesEnUS: Record<string, string> = {
  // ═══════════════════════════════════════════
  // Memory Layer — MySQL Server Config
  // ═══════════════════════════════════════════
  'tables.guide.mysql_servers': `This table contains the list of backend MySQL database servers that ProxySQL knows about.

In simple terms: your app connects to ProxySQL, and ProxySQL forwards queries to actual MySQL databases. This table tells ProxySQL: "These are the MySQL servers to forward to, here are their addresses and ports."

Each row is one MySQL server. From here you can:
• See which backend MySQL servers are registered
• Adjust a server's weight (how much traffic it gets)
• Set the max number of connections
• Bring a server online or offline

⚠ Changes require "Apply to Runtime" to take effect.`,

  'tables.guide.mysql_users': `This table contains the user accounts that ProxySQL knows about.

In simple terms: when your app connects to ProxySQL it needs a username and password. ProxySQL also needs credentials to connect to the real MySQL databases. This table manages all of that account info.

🔁 Frontend-to-backend matching flow:
  App connects to ProxySQL (port 6033) as user1/pass1
    → ProxySQL looks for username=user1 in mysql_users, checks the password
    → Password matches! ProxySQL remembers "user1 belongs to hostgroup 0"
    → App sends: SELECT * FROM orders
    → ProxySQL routes this to a MySQL server in hostgroup 0 (per user1's default_hostgroup)
    → ProxySQL connects to that MySQL as user1/pass1
    → That MySQL must also have user1/pass1, or the connection fails

Key fields:
• username/password: Login credentials. MUST also exist on backend MySQL with same password.
• default_hostgroup: Which server group to route traffic to by default. This is a number, NOT a database name! It only decides which physical server handles the query — it does NOT restrict which tables you can access.
• default_schema: Auto-USE this database after connecting. Purely a convenience — you can still query other databases. Leave blank to skip auto-selection.
• frontend: Allow connections through ProxySQL's client port (6033) — app → ProxySQL
• backend: Allow ProxySQL to use this for connecting to MySQL — ProxySQL → MySQL
• schema_locked: If ON, the user is locked to default_schema and cannot switch databases
• max_connections: Per-user concurrent connection limit
• active: Enable/disable the user (disable = effectively "ban" the account)

⚠ Changes require "Apply to Runtime" to take effect.
⚠ Password must match the backend MySQL user password, or connections will fail.
⚠ Frontend/backend can be separated: W15 wizard shows how to let your app use one password for ProxySQL, while ProxySQL uses a different password for MySQL.`,

  'tables.guide.mysql_replication_hostgroups': `This table tells ProxySQL about your MySQL primary-replica architecture.

In simple terms: if your MySQL has one primary and several replicas, this table tells ProxySQL: "Group 0 is for writers (primary), Group 1 is for readers (replicas) — use the read_only variable to detect who is who."

Once configured, ProxySQL will automatically:
• Detect each MySQL server's role (primary vs replica)
• Send write operations to the writer group
• Send read operations to the reader group
• Adjust routing automatically after a failover

⚠ Prerequisite: you must have already registered your primary and replicas in the mysql_servers table.`,

  'tables.guide.mysql_group_replication_hostgroups': `This table tells ProxySQL about your MySQL Group Replication (MGR) cluster.

In simple terms: if you use MySQL's official high-availability solution MGR, this table defines which hostgroups your MGR nodes belong to, which can write, and which are read-only.

Once set up, ProxySQL automatically detects the primary and secondaries in your MGR cluster.`,

  'tables.guide.mysql_galera_hostgroups': `This table tells ProxySQL about your Galera cluster architecture.

In simple terms: if you use Percona XtraDB Cluster or MariaDB Galera (synchronous multi-primary clusters), this table defines your Galera node groupings.

Since Galera allows all nodes to read and write, the configuration differs from traditional primary-replica setups.`,

  'tables.guide.mysql_aws_aurora_hostgroups': `This table tells ProxySQL about your AWS Aurora cluster.

In simple terms: if you use Aurora MySQL on AWS, this table configures your cluster endpoint and hostgroups so ProxySQL can auto-discover the Aurora primary and read replicas.`,

  'tables.guide.mysql_hostgroup_attributes': `This table defines per-hostgroup behavior settings.

In simple terms: shared rules that apply to all servers in a group, such as:
• Max number of online servers in this group
• Whether to execute a SQL statement on every new connection (e.g. SET NAMES utf8)
• Throttle rate for new connections
• Whether to allow connection multiplexing

Changing settings here affects the entire group at once — no need to update each server individually.`,

  'tables.guide.mysql_servers_ssl_params': `This table stores SSL/TLS parameters for ProxySQL-to-backend-MySQL connections.

In simple terms: if you require encrypted connections between ProxySQL and your MySQL servers, configure the per-server certificates and keys here.

Most setups don't need to modify this unless security policy requires encrypted backend connections.`,

  // ═══════════════════════════════════════════
  // Memory Layer — Query Routing & Control
  // ═══════════════════════════════════════════
  'tables.guide.mysql_query_rules': `One of ProxySQL's most important tables — query routing rules.

In simple terms: where should each SQL query go? This table defines the rules. You can configure:
• "All SELECT queries → send to reader group"
• "All INSERT/UPDATE/DELETE → send to writer group"
• "Queries matching a pattern → cache results for 60 seconds"
• "Queries slower than 5 seconds → auto-kill"

Rules are evaluated in order by Rule ID. If a matching rule has "stop matching" (apply=1), further rules are skipped.

⚠ This is ProxySQL's most powerful feature, but also the easiest to misconfigure. Understand rule priority and matching logic before making changes.`,

  'tables.guide.mysql_query_rules_fast_routing': `The "fast routing table" — more direct and faster than mysql_query_rules.

In simple terms: if you know for certain that a given user accessing a given database always goes to a specific hostgroup, skip the regex matching and use this table instead. Performance is O(1) — lightning fast regardless of how many rules you have.

Use when you have thousands of rules and regex matching becomes a bottleneck.`,

  // ═══════════════════════════════════════════
  // Memory Layer — Security & Firewall
  // ═══════════════════════════════════════════
  'tables.guide.mysql_firewall_whitelist_users': `This table controls which users have the SQL firewall enabled.

In simple terms: like app permissions on your phone. You can enable the SQL firewall per user with three modes:
• OFF: All SQL allowed
• DETECTING: Monitor only, log but don't block (observe quietly for a few days)
• PROTECTING: Only whitelisted SQL is allowed; everything else is rejected

Tip: run in DETECTING mode first, confirm rules are correct, then switch to PROTECTING.`,

  'tables.guide.mysql_firewall_whitelist_rules': `This table defines the firewall "whitelist rules" — which SQL statements are allowed through.

In simple terms: when the firewall is active, all SQL is rejected by default. Use this table to tell ProxySQL: "This user's queries that match this pattern are allowed."

Each rule specifies username, database, and SQL pattern. Only whitelisted SQL gets through.

⚠ Use together with the firewall users table: detect → whitelist → protect.`,

  'tables.guide.mysql_firewall_whitelist_sqli_fingerprints': `This table stores "fingerprints" of SQL injection attack patterns.

In simple terms: ProxySQL can detect SQL injection attacks like "UNION SELECT" or "DROP TABLE". This table holds the attack fingerprint signatures. Usually no manual changes needed.`,

  // ═══════════════════════════════════════════
  // Memory Layer — Users & Authentication
  // ═══════════════════════════════════════════
  'tables.guide.mysql_ldap_mapping': `This table maps LDAP (company single sign-on) users to MySQL users.

In simple terms: if your company uses LDAP/Active Directory for user accounts, this table lets employees log in with their LDAP credentials and automatically maps them to the right MySQL database user.

Example: LDAP user "alice" → mapped to → MySQL user "app_readonly".`,

  'tables.guide.mysql_collations': `This table defines character set collation rules.

In simple terms: different languages sort strings differently. This table records which collations ProxySQL supports. Usually no changes needed.`,

  // ═══════════════════════════════════════════
  // Memory Layer — PostgreSQL Config
  // ═══════════════════════════════════════════
  'tables.guide.pgsql_servers': `The PostgreSQL version of the backend server list. Similar to mysql_servers.

In simple terms: if ProxySQL is proxying PostgreSQL, this table lists the PostgreSQL servers, their addresses, and ports. Each row is one PostgreSQL server. Default port is 5432.`,

  'tables.guide.pgsql_users': `The PostgreSQL version of the user account list. Similar to mysql_users.

In simple terms: user accounts that can connect to PostgreSQL through ProxySQL.`,

  'tables.guide.pgsql_query_rules': `The PostgreSQL version of query routing rules. Similar to mysql_query_rules.

In simple terms: define where PostgreSQL queries should be routed. Same matching logic as the MySQL version.`,

  'tables.guide.pgsql_replication_hostgroups': `This table tells ProxySQL about your PostgreSQL streaming replication architecture.

In simple terms: similar to MySQL replication config — tells ProxySQL which group is primary (writes) and which is replica (reads).`,

  // ═══════════════════════════════════════════
  // Memory Layer — ProxySQL Management & System
  // ═══════════════════════════════════════════
  'tables.guide.global_variables': `ProxySQL's global configuration — essentially the "Settings" panel.

In simple terms: all of ProxySQL's switches and parameters live here in "name=value" pairs. For example:
• mysql-max_connections: max connections to each backend MySQL
• mysql-monitor_username: which user account checks backend health
• mysql-query_cache_size_MB: how much memory the query cache can use

Changing variables here directly affects ProxySQL behavior. Many changes take effect immediately without a restart.`,

  'tables.guide.scheduler': `ProxySQL's scheduled task table — like Linux crontab.

In simple terms: you can make ProxySQL automatically run scripts on a schedule. For example:
• Check replication lag every hour
• Clean up expired data every minute
• Backup config daily at midnight

Each row is a scheduled task with an interval, script path, and arguments.`,

  'tables.guide.restapi_routes': `ProxySQL's custom HTTP API routes.

In simple terms: you can add your own HTTP endpoints to ProxySQL. Once configured, HTTP requests can trigger ProxySQL to run scripts:
• GET /api/health → return health check results
• POST /api/switch → trigger a failover script

Requires ProxySQL's web and REST API features to be enabled.`,

  'tables.guide.proxysql_servers': `ProxySQL cluster node management.

In simple terms: if you run multiple ProxySQL instances in a cluster (config auto-sync), this table records all the cluster members. Add or remove nodes here.

After joining a cluster, config changes on one node auto-sync to all others.`,

  'tables.guide.debug_levels': `Debug log level configuration for development.

In simple terms: controls how verbose each module's logs are. Only available in DEBUG builds. If you just want to see normal operational logs, you don't need this.`,

  // ═══════════════════════════════════════════
  // Runtime Layer — Running State
  // ═══════════════════════════════════════════
  'tables.guide.runtime_mysql_servers': `The currently effective backend MySQL server list.

In simple terms: this shows which MySQL servers ProxySQL is actually connected to right now. Unlike mysql_servers (the memory config table), changes only appear here after you "Apply to Runtime."

If you made changes but they aren't working, check this table to see if the changes have been applied.`,

  'tables.guide.runtime_mysql_users': `The currently effective MySQL user list.

In simple terms: the user accounts ProxySQL is actively using right now. Unlike mysql_users (the memory config), password/hostgroup changes only appear here after "Apply to Runtime."

Check here to confirm user changes have taken effect.`,

  'tables.guide.runtime_mysql_query_rules': `The currently effective query routing rules.

In simple terms: the rules ProxySQL is actively enforcing right now. Compare with mysql_query_rules to check: "did my rule changes actually go live?"

If you added a rule but queries aren't routing as expected, check here first.`,

  'tables.guide.runtime_global_variables': `The currently effective global configuration values.

In simple terms: the settings ProxySQL is actually using right now. Changes to global_variables only appear here after "Apply to Runtime."

If you changed a setting but behavior hasn't changed, check this table.`,

  'tables.guide.runtime_checksums_values': `Configuration checksums — used to detect differences between layers.

In simple terms: like file checksums (MD5). If Memory and Runtime checksums differ, there are unapplied changes. If two cluster nodes have different checksums, configs haven't synced.

Usually checked automatically by the Config Sync page — rarely viewed manually.`,

  // ═══════════════════════════════════════════
  // Stats Layer — Core Statistics
  // ═══════════════════════════════════════════
  'tables.guide.stats_mysql_query_digest': `ProxySQL's most important monitoring table — query digest statistics.

In simple terms: this records aggregated statistics for every SQL pattern that has passed through ProxySQL. Each row represents a "parameterized SQL pattern" and shows:
• How many times it executed
• Total time spent
• Average time per execution
• Maximum single execution time
• Rows returned
• When it was first seen

Use this to:
• Find the slowest queries → sort by average time
• Find the most frequent queries → sort by count
• Find the biggest time consumers → sort by total time
• Analyze your application's SQL composition

⚠ Read-only table. Data accumulates over time and is invaluable for performance analysis.`,

  'tables.guide.stats_mysql_query_rules': `Query routing rule hit statistics.

In simple terms: which routing rules are matching and how often? This table tells you.

If a rule shows 0 hits:
• The match pattern may be wrong
• There may be no matching SQL traffic
• An earlier rule with apply=1 may have intercepted`,

  'tables.guide.stats_mysql_commands_counters': `SQL command type breakdown (how many SELECTs, INSERTs, UPDATEs, DELETEs).

In simple terms: a "query type health report" showing the proportion of each command type your app is generating.

Use this to understand whether your app is read-heavy or write-heavy.`,

  'tables.guide.stats_mysql_connection_pool': `Real-time connection pool status for each backend MySQL.

In simple terms: how ProxySQL's connections to each backend MySQL are being used. Shows:
• Used / Free connections → is the pool sufficient?
• Total queries → how much traffic this server handles
• Network latency (ms) → is the network healthy?
• Error count → any connection problems?

If "used" approaches "max", increase connections or add more servers.
If a server's error count spikes, something is probably wrong.`,

  'tables.guide.stats_mysql_processlist': `Current client connection process list.

In simple terms: like MySQL's SHOW PROCESSLIST — who's connected through ProxySQL right now, what SQL they're running, how long they've been connected.

Use to:
• See who is holding connections
• Find long-running queries
• Spot suspicious connections (unusual IPs, durations)

⚠ Read-only, real-time snapshot.`,

  'tables.guide.stats_mysql_users': `Per-user connection and usage statistics.

In simple terms: which application account has the most connections, how many queries each has processed.

Use to:
• Spot apps with unusually high connections
• Decide whether to limit a user's connections
• Monitor per-user usage`,

  'tables.guide.stats_mysql_global': `ProxySQL global runtime status.

In simple terms: ProxySQL's "health report card":
• Client_Connections_connected: how many clients are connected
• Questions: total queries processed
• Backend_query_time_nsec: total time spent on backend queries
• ConnPool_memory_bytes: connection pool memory usage

Use this to gauge overall ProxySQL health.`,

  'tables.guide.stats_mysql_errors': `Backend query error statistics.

In simple terms: which queries sent through ProxySQL returned errors? Grouped by error code:
• 1045: Authentication failed (wrong password)
• 1062: Duplicate key (inserted duplicate data)
• 1205: Lock wait timeout
• 1213: Deadlock

Use to quickly identify backend database error patterns.`,

  'tables.guide.stats_memory_metrics': `ProxySQL's own memory usage breakdown.

In simple terms: how much memory ProxySQL is using, broken down by module (connection pool, query cache, query rules, etc.).

If ProxySQL's memory usage is high, check here to find which module is consuming the most.`,

  // ═══════════════════════════════════════════
  // Stats Layer — History
  // ═══════════════════════════════════════════
  'tables.guide.history_mysql_query_digest': `Historical snapshots of query statistics.

In simple terms: stats_mysql_query_digest data is periodically copied here for historical comparison. Compare "past query patterns" with "current query patterns." Data is saved incrementally by time.`,

  // ═══════════════════════════════════════════
  // Monitor Layer — Monitoring Database
  // ═══════════════════════════════════════════
  'tables.guide.mysql_server_connect_log': `Backend MySQL "can we connect?" check log.

In simple terms: ProxySQL's Monitor module periodically tries to connect to each backend MySQL. This table records the results: success or failure, how long it took, any error messages.

If a MySQL server goes down, you'll see connection failures here.`,

  'tables.guide.mysql_server_ping_log': `Backend MySQL ping check log.

In simple terms: ProxySQL periodically pings each backend MySQL to check latency and availability. This table records ping results and response times.

If a MySQL server has network issues, the ping latency here will spike.`,

  'tables.guide.mysql_server_read_only_log': `Backend MySQL read_only status check log.

In simple terms: ProxySQL periodically checks whether each backend MySQL has read_only=ON (read-only, aka replica) or read_only=OFF (writable, aka primary). ProxySQL uses this to determine who is the primary and who are the replicas.

After a failover, you'll see a server's read_only status change here.`,

  'tables.guide.mysql_server_replication_lag_log': `Backend MySQL replication lag check log.

In simple terms: after the primary writes data, replicas need time to catch up. This table records how many seconds each replica is behind the primary. If lag exceeds the threshold, ProxySQL stops sending queries to that replica.

Use to monitor replication health.`,

  'tables.guide.mysql_server_group_replication_log': `MySQL Group Replication (MGR) cluster check log.

In simple terms: if you use MGR clusters, the Monitor module periodically checks cluster member status. This table records each check's results.

Only relevant if you're running MGR clusters.`,

  // ═══════════════════════════════════════════
  // Disk Layer — Persisted Config
  // ═══════════════════════════════════════════
  'tables.guide.mysql_servers_disk': `The on-disk persisted version of mysql_servers.

In simple terms: when you "Save to Disk," the MySQL server configuration from memory is written here. ProxySQL loads from this table when it restarts.

This table's content should match the in-memory mysql_servers. If they differ, there are unsaved changes.`,

  'tables.guide.mysql_users_disk': `The on-disk persisted version of mysql_users. Works like mysql_servers_disk.

In simple terms: saved-to-disk user configuration. ProxySQL restores user data from here on restart.`,

  'tables.guide.mysql_query_rules_disk': `The on-disk persisted version of mysql_query_rules.

In simple terms: saved-to-disk query routing rules. ProxySQL restores rules from here on restart.`,

  'tables.guide.global_variables_disk': `The on-disk persisted version of global_variables.

In simple terms: saved-to-disk global settings. ProxySQL restores all settings from here on restart.`,

  // ═══════════════════════════════════════════
  // Stats History Layer
  // ═══════════════════════════════════════════
  'tables.guide.stats_history_history': `Historical statistics snapshots.

In simple terms: ProxySQL periodically (once per minute) saves a stats snapshot here. You can look back and ask "what did query patterns look like yesterday at 3 PM?"

Note: This database is only available in ProxySQL 2.x+.`,

  // ═══════════════════════════════════════════
  // Generic fallback
  // ═══════════════════════════════════════════
  'tables.guide._default': `No dedicated guide is available for this table yet.

You can browse the table data directly to understand its contents, or use the SQL Console to run SELECT queries for further analysis.`,
};
