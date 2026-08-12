# AskData产品V2.0备份与灾难恢复手册

> 产品基线覆盖本地H2完整演练；客户PostgreSQL、备份平台、KMS/Vault、HA、跨机房和RPO/RTO在M8按目标环境验证。

## 1. 不可拆分恢复包

每个恢复包必须同时包含：

1. `platform-database.zip`：平台数据库一致性脚本备份；
2. `database-inventory.properties`：Flyway版本、配置版本/当前发布、秘密引用、请求和审计数量，以及配置快照与秘密引用摘要；
3. `release-package.bin`：与数据库结构匹配的应用发布包；
4. `secret-recovery.bundle`：经批准且加密的KMS/Vault/密钥恢复材料，数据库中的秘密引用本身不能替代它；
5. `manifest.json`：备份ID、应用版本、源码提交、数据库类型和必备组件；
6. `SHA256SUMS`：以上所有文件的完整性摘要。

数据库、发布包或秘密材料不得单独恢复。恢复工具会先检查六项、全部SHA256、人工确认串和应用版本，再连接目标库；恢复后重新计算数据库清单并要求逐项一致。

## 2. 创建备份

先停止写入或进入批准的维护窗口，编译恢复工具并准备已加密的秘密恢复材料：

~~~bash
JAVA_HOME=/path/to/jdk21 ./platform-service/mvnw -f platform-service/pom.xml -q -DskipTests package

export ASKDATA_BACKUP_OUTPUT=/secure/backup/askdata-v2-YYYYMMDD
export ASKDATA_PLATFORM_DB_URL='jdbc:h2:file:/srv/askdata/platform-v2;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE'
export ASKDATA_PLATFORM_DB_USERNAME='...'
export ASKDATA_PLATFORM_DB_PASSWORD='...'
export ASKDATA_RELEASE_PACKAGE=/srv/releases/askdata-v2.jar
export ASKDATA_SECRET_BUNDLE=/secure/staging/secret-recovery.encrypted
export ASKDATA_APP_VERSION=2.0.0
export ASKDATA_SOURCE_COMMIT='<40位提交SHA>'
export ASKDATA_DB_ENGINE=h2
bash scripts/v2-backup.sh
~~~

输出目录必须不存在。工具使用`umask 077`；备份完成后仍应转移到加密、分权和受审计的介质，不得提交Git或放入Web目录。

## 3. 恢复

目标必须是空库，发布包和秘密材料输出路径必须不存在。先查看`manifest.json`中的`backupId`和版本，再进行显式确认：

~~~bash
export ASKDATA_BACKUP_INPUT=/secure/backup/askdata-v2-YYYYMMDD
export ASKDATA_RESTORE_CONFIRM='RESTORE:<backupId>'
export ASKDATA_RESTORE_DB_URL='jdbc:h2:file:/srv/askdata-restored/platform-v2;MODE=PostgreSQL;DATABASE_TO_LOWER=TRUE;AUTO_SERVER=TRUE'
export ASKDATA_RESTORE_DB_USERNAME='...'
export ASKDATA_RESTORE_DB_PASSWORD='...'
export ASKDATA_RESTORE_RELEASE_OUTPUT=/srv/askdata-restored/askdata-v2.jar
export ASKDATA_RESTORE_SECRET_OUTPUT=/secure/askdata-restored/secret-recovery.encrypted
export ASKDATA_EXPECTED_APP_VERSION=2.0.0
bash scripts/v2-restore.sh
~~~

只有出现`RESTORE_OK`并且后续健康检查、审计链校验和黄金问题通过，才允许切换流量。失败时保留恢复目标作诊断，另建空目标重试；禁止在半恢复库上继续写入。

## 4. 产品灾难演练

~~~bash
JAVA_HOME=/path/to/jdk21 bash scripts/v2-disaster-recovery-drill.sh
~~~

演练在唯一的`/tmp/askdata-v2-drill-*`目录创建源库和目标库，不接触开发库。它验证15版迁移、非空配置快照和秘密引用、组件摘要、完整恢复、清单一致、发布包/秘密材料字节一致，并验证缺秘密材料及应用版本不匹配必然拒绝。退出时清理其唯一临时目录。

## 5. 客户条件项

M8必须依据客户数据库和安全体系补齐：原生在线备份/时间点恢复、WAL/归档日志、KMS/Vault导出与重建流程、异地介质、保留和销毁、备份账号、恢复审批、故障切换、监控告警以及实测RPO/RTO。产品演练结果只证明恢复机制可复现，不代表客户生产RPO/RTO或HA承诺。
