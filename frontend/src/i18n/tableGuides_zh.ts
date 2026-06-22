/**
 * ProxySQL 表浏览器 — 小白说明（简体中文）
 *
 * 每个表的说明用最通俗的语言解释：
 * - 这张表是干什么的
 * - 它记录的是什么东西
 * - 你可能什么时候需要看/改它
 *
 * Key 命名：tables.guide.<table_name>
 */
export const tableGuidesZhCN: Record<string, string> = {
  // ═══════════════════════════════════════════
  // Memory 层 — MySQL 服务器配置
  // ═══════════════════════════════════════════
  'tables.guide.mysql_servers': `这张表记录了 ProxySQL 知道的"后端 MySQL 数据库服务器"名单。

通俗理解：你公司的应用程序连到 ProxySQL，ProxySQL 再把查询转发给真正的 MySQL 数据库。这张表就是告诉 ProxySQL："你要转发给哪些 MySQL，每台在哪、端口是多少"。

表中每条记录就是一台 MySQL 服务器。你可以在这里：
• 查看当前有哪些后端 MySQL
• 修改某台服务器的权重（控制分配多少流量给它）
• 修改最大连接数（限制同时连多少个）
• 把某台服务器设为在线/离线

⚠ 修改后需要"应用到运行时"才能生效。`,

  'tables.guide.mysql_users': `这张表记录了 ProxySQL 知道的"用户账号名单"。

通俗理解：你的应用程序连到 ProxySQL 时需要输入用户名密码，ProxySQL 用什么密码去连真正的 MySQL 也需要用户名密码。这张表就是管理和存储这些账号信息的地方。

🔁 前后端匹配流程：
  App 用 user1/pass1 连 ProxySQL（6033端口）
    → ProxySQL 在 mysql_users 里找 username=user1，用记录的密码验证
    → 验证通过，ProxySQL 内部记录"user1 属于主机组 0"
    → App 发来 SELECT * FROM orders
    → ProxySQL 根据 user1 的 default_hostgroup=0，把查询发给主机组 0 里的某台 MySQL
    → ProxySQL 以 user1/pass1 去连那台 MySQL
    → 那台 MySQL 上必须也有 user1/pass1 这个账号，否则报错

表中关键字段：
• username/password：登录凭据。⚠ 必须在后端 MySQL 中也创建同名同密用户
• default_hostgroup：默认把你发到哪个主机组。填数字，不是数据库名！只决定流量路由到哪台/哪组服务器，不限制你能查什么表
• default_schema：连上后自动 USE 的数据库，纯便利功能，填了也能查其他库
• frontend：是否允许通过 ProxySQL 的"服务端口"(6033) 连接（app→ProxySQL）
• backend：是否允许通过 ProxySQL 连接后端 MySQL（ProxySQL→MySQL）
• schema_locked：是否禁止切换数据库（锁死只能查 default_schema）
• max_connections：该用户最多同时开多少连接
• active：是否启用（关掉=封号）

⚠ 修改后需要"应用到运行时"才能生效。
⚠ 密码和后端 MySQL 不一致则连接失败。
⚠ 前后端可以分离：W15 向导演示了如何让 App 用一个密码连 ProxySQL，ProxySQL 用另一个密码连 MySQL。`,

  'tables.guide.mysql_replication_hostgroups': `这张表告诉 ProxySQL 你的 MySQL 主从架构是什么样子的。

通俗理解：你的 MySQL 可能有一主多从，主库负责写数据，从库负责读数据。这张表就是告诉 ProxySQL："0号组是写库（主库），1号组是读库（从库），你自动检测 read_only 来判断谁是主谁是从"。

设置好后，ProxySQL 会自动：
• 检测每台 MySQL 是主库还是从库
• 把写操作发给主库组
• 把读操作发给从库组
• 主从切换时自动调整路由

⚠ 前提：你已经在 mysql_servers 表中注册了主库和从库。`,

  'tables.guide.mysql_group_replication_hostgroups': `这张表告诉 ProxySQL 你的 MySQL Group Replication（MGR）集群架构。

通俗理解：如果你用的是 MySQL 官方高可用方案 MGR，这张表就是告诉 ProxySQL 你的 MGR 节点各在哪个主机组、哪些节点可以写、哪些只能读。

设置好后，ProxySQL 会自动检测 MGR 集群中哪个是主节点、哪些是从节点。`,

  'tables.guide.mysql_galera_hostgroups': `这张表告诉 ProxySQL 你的 Galera 集群架构。

通俗理解：如果你用的是 Percona XtraDB Cluster 或 MariaDB Galera（多主同步复制集群），这张表就是告诉 ProxySQL 你的 Galera 节点分组信息。

Galera 所有节点都可以读写，所以配置方式与普通主从不同。`,

  'tables.guide.mysql_aws_aurora_hostgroups': `这张表告诉 ProxySQL 你的 AWS Aurora 集群信息。

通俗理解：如果你在亚马逊云上用 Aurora MySQL，这张表配置 Aurora 集群的终点域名和分组，让 ProxySQL 自动发现 Aurora 的主节点和只读节点。`,

  'tables.guide.mysql_hostgroup_attributes': `这张表记录每个"主机组"的通用属性。

通俗理解：一组服务器（比如读库组）有哪些共同的行为规则，比如：
• 这个组最多同时在线多少台服务器
• 连接时是否自动执行一句 SQL（如 SET NAMES utf8）
• 新连接建立速度限制（每秒最多建多少个）
• 是否允许多个客户端共用同一条后端连接（多路复用）

改这里可以控制整组服务器的行为，不用逐台修改。`,

  'tables.guide.mysql_servers_ssl_params': `这张表记录 ProxySQL 连接后端 MySQL 时的 SSL/加密参数。

通俗理解：如果你要求 ProxySQL 到后端 MySQL 的连接必须加密（SSL/TLS），就从这里配置每台服务器的证书和密钥。

一般只有需要加密传输的安全环境才需要改这张表。`,

  // ═══════════════════════════════════════════
  // Memory 层 — 查询路由与控制
  // ═══════════════════════════════════════════
  'tables.guide.mysql_query_rules': `ProxySQL 最核心的表之一 — 查询路由规则。

通俗理解：应用程序发来的 SQL 该发到哪台 MySQL 去执行？这张表就是定义规则的。你可以设置：
• "所有 SELECT 查询发到读库组"
• "所有 INSERT/UPDATE/DELETE 发到写库组"
• "以 / * 慢查询 * / 开头的 SQL 直接拒绝"
• "针对某张表的查询缓存 60 秒"
• "超时超过 5 秒的查询自动杀掉"

规则按 ID 从小到大依次匹配。命中规则后如果勾了"停止匹配"，后续规则就不再检查。

⚠ 这是 ProxySQL 最强大的功能，但也最容易配错。改之前建议先理解规则的优先级和匹配逻辑。`,

  'tables.guide.mysql_query_rules_fast_routing': `这张表是"快速路由表"，比 mysql_query_rules 更直接更快。

通俗理解：如果你确切知道"某个用户"访问"某个数据库"时，查询一定发到某个主机组，就不需要用正则去匹配了，直接查这张表。速度是 O(1)（不管你配多少条都快）。

适用场景：规则数量非常多（上千条）时，用快速路由能显著降低 ProxySQL 的 CPU 消耗。`,

  // ═══════════════════════════════════════════
  // Memory 层 — 安全与防火墙
  // ═══════════════════════════════════════════
  'tables.guide.mysql_firewall_whitelist_users': `这张表控制哪些用户启用了 SQL 防火墙。

通俗理解：类似你手机上的应用权限管理。你可以给某个用户开启 SQL 防火墙，有三种模式：
• OFF：关闭，所有 SQL 随便执行
• DETECTING：检测模式，只记录不拦截（先悄悄观察几天）
• PROTECTING：保护模式，只允许白名单里的 SQL，其余全部拒绝

建议先用 DETECTING 观察一段时间，确认规则没问题再切 PROTECTING。`,

  'tables.guide.mysql_firewall_whitelist_rules': `这张表定义防火墙"白名单规则"——哪些 SQL 允许通过。

通俗理解：防火墙开启后，默认所有 SQL 被拒绝。你得在这张表里告诉 ProxySQL："这个用户的这种 SQL 可以放行"。

每条规则指定用户名、数据库、SQL 类型。只有在白名单里的 SQL 才能执行。

⚠ 建议配合防火墙用户表一起使用：先开检测模式收集正常 SQL，再加白名单，最后切保护模式。`,

  'tables.guide.mysql_firewall_whitelist_sqli_fingerprints': `这张表记录 SQL 注入攻击的特征"指纹"。

通俗理解：ProxySQL 可以检测像 "UNION SELECT"、"DROP TABLE" 这类 SQL 注入攻击的特征。这张表就是存放这些攻击指纹的地方。一般无需手动修改。`,

  // ═══════════════════════════════════════════
  // Memory 层 — 用户与认证
  // ═══════════════════════════════════════════
  'tables.guide.mysql_ldap_mapping': `这张表把 LDAP（公司统一登录）用户映射到 MySQL 用户。

通俗理解：如果你公司用 LDAP/AD 管理员工账号，这张表可以让员工用 LDAP 账号登录后，ProxySQL 自动转换成对应的 MySQL 数据库账号去访问数据。

例如：LDAP 用户 "zhangsan" 映射到 MySQL 用户 "app_readonly"。`,

  'tables.guide.mysql_collations': `这张表定义 MySQL 字符集排序规则。

通俗理解：不同语言对字符串排序的规则不同（比如中文按拼音排序，德语有特殊字符排序）。这张表记录 ProxySQL 支持哪些排序规则。一般不需要改。`,

  // ═══════════════════════════════════════════
  // Memory 层 — PostgreSQL 配置
  // ═══════════════════════════════════════════
  'tables.guide.pgsql_servers': `这张表是 PostgreSQL 版本的后端服务器名单，功能与 mysql_servers 类似。

通俗理解：如果 ProxySQL 用于代理 PostgreSQL 数据库，这张表记录有哪些 PostgreSQL 服务器、位置、端口等信息。

每条记录是一台 PostgreSQL 服务器。配置方式与 MySQL 类似，只是端口默认是 5432。`,

  'tables.guide.pgsql_users': `这张表是 PostgreSQL 版本的用户账号名单，功能与 mysql_users 类似。

通俗理解：记录可以通过 ProxySQL 连接 PostgreSQL 的用户账号信息。`,

  'tables.guide.pgsql_query_rules': `这张表是 PostgreSQL 版本的查询路由规则，功能与 mysql_query_rules 类似。

通俗理解：定义发往 PostgreSQL 的 SQL 应该路由到哪个主机组。规则匹配逻辑与 MySQL 版一致。`,

  'tables.guide.pgsql_replication_hostgroups': `这张表告诉 ProxySQL 你的 PostgreSQL 主从流复制架构。

通俗理解：与 MySQL 主从配置类似，告诉 ProxySQL 哪个组是主库组（写）、哪个组是从库组（读）。`,

  // ═══════════════════════════════════════════
  // Memory 层 — ProxySQL 管理与系统
  // ═══════════════════════════════════════════
  'tables.guide.global_variables': `ProxySQL 的全局配置参数表，相当于"设置面板"。

通俗理解：ProxySQL 的各种开关和参数都在这里，用 "变量名=值" 的形式存储。比如：
• mysql-max_connections：到每个后端 MySQL 最多开多少连接
• mysql-monitor_username：监控后端 MySQL 健康用哪个账号
• mysql-query_cache_size_MB：查询缓存最多占用多少内存

修改这里的变量会直接影响 ProxySQL 的行为。很多变量修改后不需要重启，立刻生效。`,

  'tables.guide.scheduler': `ProxySQL 的"定时任务"表，类似 Linux 的 crontab。

通俗理解：你可以让 ProxySQL 每隔一段时间自动执行一个脚本。比如：
• 每小时检查一次主从延迟
• 每分钟清理一次过期数据
• 每天凌晨备份一次配置

每条记录是一个定时任务，包含执行间隔、脚本路径和参数。`,

  'tables.guide.restapi_routes': `ProxySQL 的自定义 HTTP API 路由表。

通俗理解：你可以给 ProxySQL 添加自己的 HTTP 接口。配置后，通过 HTTP 请求就可以触发 ProxySQL 执行特定脚本，比如：
• GET /api/health → 返回健康检查结果
• POST /api/switch → 触发主从切换脚本

前提需要开启 ProxySQL 的 Web 功能和 REST API 功能。`,

  'tables.guide.proxysql_servers': `ProxySQL 集群节点管理表。

通俗理解：如果你有多台 ProxySQL 组成集群（配置自动同步），这张表记录集群中有哪些节点。添加/删除节点都在这里操作。

加入集群后，在一台 ProxySQL 上修改配置，会自动同步到所有节点。`,

  'tables.guide.debug_levels': `ProxySQL 的调试日志级别配置表。

通俗理解：用于开发调试，控制各种模块的日志详细程度。仅 DEBUG 编译版本可用。如果只是想看运行日志，不需要改这里。`,

  // ═══════════════════════════════════════════
  // Runtime 层 — 运行时状态
  // ═══════════════════════════════════════════
  'tables.guide.runtime_mysql_servers': `当前实际生效的后端 MySQL 服务器列表。

通俗理解：这张表显示 ProxySQL 此刻真正在连接的 MySQL 服务器。和 mysql_servers（内存配置表）的区别是：改了配置表后需要"应用到运行时"，数据才会出现在这里。

如果你改了配置但发现没生效，来这张表看看是不是还没应用。`,

  'tables.guide.runtime_mysql_users': `当前实际生效的 MySQL 用户账号列表。

通俗理解：ProxySQL 此刻真正在使用的用户账号信息。和 mysql_users（内存配置表）的区别是：改密码、改权限后需要"应用到运行时"，才会体现在这里。

检查用户修改是否生效就看这张表。`,

  'tables.guide.runtime_mysql_query_rules': `当前实际生效的查询路由规则列表。

通俗理解：ProxySQL 此刻真正在执行的查询路由规则。和 mysql_query_rules 的区别是：改了规则 → 应用 → 这里更新。

如果配了规则但没生效，先看这张表确认规则是否已经应用到运行时。`,

  'tables.guide.runtime_global_variables': `当前实际生效的全局配置参数。

通俗理解：ProxySQL 此刻正在使用的配置参数值。修改 global_variables 后需要"应用到运行时"才会在这里更新。

如果改了某项参数但行为没变，看这张表确认新值是否已经生效。`,

  'tables.guide.runtime_checksums_values': `配置的"校验和"（checksum），用来判断不同层之间是否一致。

通俗理解：类似文件的 MD5 值。ProxySQL 计算每层配置的校验和，如果 Memory 和 Runtime 的校验和不同，说明有修改还没应用。如果两个 ProxySQL 集群节点的校验和不同，说明配置没同步。

一般不需要手动查看，配置同步页面会自动比对。`,

  // ═══════════════════════════════════════════
  // Stats 层 — 核心统计
  // ═══════════════════════════════════════════
  'tables.guide.stats_mysql_query_digest': `ProxySQL 最重要的监控统计表 — 查询摘要统计。

通俗理解：这张表记录了经过 ProxySQL 的所有 SQL 查询的统计信息。每条记录是一种"参数化后的 SQL 模式"，显示：
• 这条 SQL 执行了多少次
• 总耗时多久
• 平均每次耗时多久
• 最长一次多久
• 返回了多少行
• 第一个看到这条 SQL 是什么时候

用途：
• 找最慢的查询 → 按平均耗时排序
• 找最频繁的查询 → 按执行次数排序
• 找总耗时最长的查询 → 按总耗时排序
• 分析业务 SQL 构成比例

⚠ 这是只读表，是分析问题的利器。数据会随着时间积累。`,

  'tables.guide.stats_mysql_query_rules': `查询路由规则的命中统计。

通俗理解：你配的那些路由规则，哪些被触发了、触发了几次？这张表告诉你答案。

每条规则显示命中次数。如果某条规则的命中次数是 0：
• 可能匹配条件写错了
• 可能没有对应的 SQL 流量
• 可能被前面的规则拦截了（前面的规则 apply=1 后，后面的不会执行）`,

  'tables.guide.stats_mysql_commands_counters': `SQL 命令类型统计（SELECT、INSERT、UPDATE、DELETE 各自多少）。

通俗理解：告诉你 ProxySQL 处理的查询中，SELECT 占多少、INSERT 占多少、UPDATE 占多少……像一份"查询类型体检报告"。

用途：了解你的应用主要是读多写少还是读写均衡。`,

  'tables.guide.stats_mysql_connection_pool': `每台后端 MySQL 的连接池实时状态。

通俗理解：ProxySQL 到每台后端 MySQL 的连接使用情况。显示：
• 已用连接数 / 空闲连接数 → 判断连接池是否够用
• 总查询数 → 看这台服务器处理了多少流量
• 网络延迟（毫秒）→ 网络是否正常
• 错误数 → 是否有连接故障

如果"已用连接"接近"最大连接"，说明需要调大连接数或加服务器。
如果某台服务器错误数飙升，说明可能出问题了。`,

  'tables.guide.stats_mysql_processlist': `当前所有客户端连接的"进程列表"。

通俗理解：类似 MySQL 的 SHOW PROCESSLIST，显示此刻谁在通过 ProxySQL 访问数据库、在跑什么 SQL、连了多久。

用途：
• 查看谁在占用连接
• 找到长时间运行的查询
• 发现异常连接（来源IP、时长异常）

⚠ 只读表，实时快照。`,

  'tables.guide.stats_mysql_users': `每个 ProxySQL 用户的连接和使用统计。

通俗理解：哪个应用账号连接数最多、处理了多少查询，都在这里。

用途：
• 发现哪个应用连接数异常高
• 判断是否需要限制某用户的连接数
• 监控用户级别的使用情况`,

  'tables.guide.stats_mysql_global': `ProxySQL 全局运行状态指标。

通俗理解：ProxySQL 的"体检单"：
• Client_Connections_connected：当前有多少客户端连着
• Questions：总共处理了多少条查询
• Backend_query_time_nsec：花在后端查询上的总时间
• ConnPool_memory_bytes：连接池占了多少内存

这是判断 ProxySQL 整体健康状况的参考。`,

  'tables.guide.stats_mysql_errors': `后端查询错误统计。

通俗理解：通过 ProxySQL 发给后端 MySQL 的查询，哪些返回了错误？按错误码汇总：
• 1045：认证失败（密码不对）
• 1062：主键重复（插入了重复数据）
• 1205：锁等待超时
• 1213：死锁

用于快速定位后端数据库的报错情况。`,

  'tables.guide.stats_memory_metrics': `ProxySQL 自身的内存使用详情。

通俗理解：ProxySQL 用了多少内存，各个模块分别用了多少（连接池、查询缓存、查询规则等）。

如果 ProxySQL 内存占用过高，来这里看是哪个模块吃内存最多。`,

  // ═══════════════════════════════════════════
  // Stats 层 — 历史统计
  // ═══════════════════════════════════════════
  'tables.guide.history_mysql_query_digest': `查询统计的历史快照。

通俗理解：定期把 stats_mysql_query_digest 的数据拷贝到这里保存。用于对比"以前的查询情况"和"现在的查询情况"。数据按时间增量保存，可以追溯历史。`,

  // ═══════════════════════════════════════════
  // Monitor 层 — 监控数据库
  // ═══════════════════════════════════════════
  'tables.guide.mysql_server_connect_log': `后端 MySQL "能否连接"的检测日志。

通俗理解：ProxySQL 的 Monitor 模块定期尝试连接每台后端 MySQL，看能不能连上。这张表记录了每次连接检测的结果：成功还是失败、耗时多久、错误信息是什么。

如果某台 MySQL 挂了，这里会看到连接失败记录。`,

  'tables.guide.mysql_server_ping_log': `后端 MySQL 的 Ping 检测日志。

通俗理解：ProxySQL 定期向每台后端 MySQL 发 Ping 包，检测网络延迟和服务器是否存活。这张表记录了每次 Ping 的结果和延迟时间。

如果某台 MySQL 网络有问题，Ping 延迟会飙升。`,

  'tables.guide.mysql_server_read_only_log': `后端 MySQL 的"只读状态"检测日志。

通俗理解：ProxySQL 定期检查每台后端 MySQL 的 read_only 变量是 ON 还是 OFF。read_only=ON 说明是只读（从库），OFF 说明可写（主库）。ProxySQL 据此判断谁是主库、谁是从库。

如果发生了主从切换，这里会看到某台服务器的 read_only 状态发生了变化。`,

  'tables.guide.mysql_server_replication_lag_log': `后端 MySQL 的"主从复制延迟"检测日志。

通俗理解：主库写入数据后，从库需要时间同步。这张表记录了每台从库落后主库多少秒。如果延迟太大，ProxySQL 会自动暂停向这台从库发查询。

用于监控主从同步是否健康。`,

  'tables.guide.mysql_server_group_replication_log': `MySQL Group Replication（MGR）集群检测日志。

通俗理解：如果你用的是 MGR 集群，Monitor 模块会定期检查集群成员状态。这张表记录了每次检查的结果。

一般只有使用 MGR 集群时才需要关注。`,

  // ═══════════════════════════════════════════
  // Disk 层 — 持久化配置
  // ═══════════════════════════════════════════
  'tables.guide.mysql_servers_disk': `这是 mysql_servers 的磁盘持久化版本。

通俗理解：当你"保存到磁盘"后，内存中的 MySQL 服务器配置会被写入这张表。ProxySQL 重启时会从这里读取配置。

这张表的内容应该和内存中的 mysql_servers 一致。如果不一致，说明有修改还没保存。`,

  'tables.guide.mysql_users_disk': `这是 mysql_users 的磁盘持久化版本。功能和 mysql_servers_disk 类似。

通俗理解：保存到磁盘后的用户配置。ProxySQL 重启后从这张表恢复用户数据。`,

  'tables.guide.mysql_query_rules_disk': `这是 mysql_query_rules 的磁盘持久化版本。

通俗理解：保存到磁盘后的查询规则配置。ProxySQL 重启后从这张表恢复路由规则。`,

  'tables.guide.global_variables_disk': `这是 global_variables 的磁盘持久化版本。

通俗理解：保存到磁盘后的全局参数配置。ProxySQL 重启后从这张表恢复所有设置。`,

  // ═══════════════════════════════════════════
  // Stats History 层 — 历史统计数据库
  // ═══════════════════════════════════════════
  'tables.guide.stats_history_history': `历史的统计快照记录表。

通俗理解：ProxySQL 定期（每分钟一次）把当时的查询统计快照存到这里。这样你可以回溯"昨天下午3点的查询情况是什么样的"。

注意：这个数据库在 ProxySQL 2.x+ 才有。`,

  // ═══════════════════════════════════════════
  // 通用回落：如果某个表没有专属说明
  // ═══════════════════════════════════════════
  'tables.guide._default': `该表暂无专门的说明文档。

你可以直接查看表数据了解其内容，或通过 SQL 控制台执行 SELECT 查询进一步分析。`,
};
