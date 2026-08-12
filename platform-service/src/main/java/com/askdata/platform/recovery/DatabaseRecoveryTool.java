package com.askdata.platform.recovery;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.sql.DriverManager;
import java.util.HexFormat;
import java.util.List;

/** Minimal vendor-local recovery helper. It deliberately has no Spring dependency. */
public final class DatabaseRecoveryTool {
    private DatabaseRecoveryTool() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 6 || !List.of("backup-h2","restore-h2","inventory","seed-drill").contains(args[0])) {
            throw new IllegalArgumentException("usage: <backup-h2|restore-h2|inventory|seed-drill> <jdbc-url> <user> <password> <file> <engine>");
        }
        var operation=args[0];var url=args[1];var user=args[2];var password=args[3];var file=Path.of(args[4]).toAbsolutePath().normalize();var engine=args[5];
        if(operation.equals("backup-h2")){require(engine.equals("h2"),"backup-h2只支持H2");backupH2(url,user,password,file);}
        else if(operation.equals("restore-h2")){require(engine.equals("h2"),"restore-h2只支持H2");restoreH2(url,user,password,file);}
        else if(operation.equals("inventory"))inventory(url,user,password,file,engine);
        else seedDrill(url,user,password);
    }

    static void backupH2(String url,String user,String password,Path output)throws Exception{
        require(!Files.exists(output),"备份文件已存在");Files.createDirectories(output.getParent());
        try(var connection=DriverManager.getConnection(url,user,password);var statement=connection.createStatement()){
            statement.execute("SCRIPT TO '"+sqlPath(output)+"' COMPRESSION ZIP");
        }
        require(Files.isRegularFile(output)&&Files.size(output)>0,"H2备份未生成");
    }
    static void restoreH2(String url,String user,String password,Path input)throws Exception{
        require(Files.isRegularFile(input),"H2备份不存在");
        try(var connection=DriverManager.getConnection(url,user,password)){
            try(var check=connection.createStatement();var result=check.executeQuery("select count(*) from information_schema.tables where lower(table_schema)='public' and table_type='BASE TABLE'")){
                result.next();require(result.getInt(1)==0,"恢复目标不是空库");
            }
            try(var statement=connection.createStatement()){statement.execute("RUNSCRIPT FROM '"+sqlPath(input)+"' COMPRESSION ZIP");}
        }
    }
    static void inventory(String url,String user,String password,Path output,String engine)throws Exception{
        Files.createDirectories(output.getParent());
        try(var connection=DriverManager.getConnection(url,user,password)){
            var flyway=text(connection,"select version from flyway_schema_history where success=true order by installed_rank desc fetch first 1 row only");
            var releases=number(connection,"select count(*) from cfg_release");
            var current=number(connection,"select count(*) from cfg_current_release");
            var secrets=number(connection,"select count(*) from ai_secret_ref");
            var requests=number(connection,"select count(*) from run_request");
            var audits=number(connection,"select count(*) from audit_operation_log");
            var seedImports=number(connection,"select count(*) from cfg_seed_import");
            var roles=number(connection,"select count(*) from iam_role");
            var scenarios=number(connection,"select count(*) from flow_scenario");
            var cases=number(connection,"select count(*) from flow_scenario_case");
            var turns=number(connection,"select count(*) from flow_scenario_turn");
            var releaseItems=number(connection,"select count(*) from cfg_release_item");
            var orgScopes=number(connection,"select count(*) from iam_role_org_scope");
            var metricScopes=number(connection,"select count(*) from iam_role_metric_scope");
            var tableScopes=number(connection,"select count(*) from iam_role_table_scope");
            var migrationAudits=number(connection,"select count(*) from audit_operation_log where action='MIGRATE_LEGACY_BASELINE' and result='SUCCEEDED'");
            var orphanLinks=number(connection,"select "
                    + "(select count(*) from flow_scenario_role x left join flow_scenario s on s.id=x.scenario_id left join iam_role r on r.id=x.role_id where s.id is null or r.id is null)+"
                    + "(select count(*) from flow_scenario_case x left join flow_scenario s on s.id=x.scenario_id left join iam_role r on r.id=x.role_id where s.id is null or r.id is null)+"
                    + "(select count(*) from flow_scenario_turn x left join flow_scenario_case c on c.id=x.case_id where c.id is null)+"
                    + "(select count(*) from cfg_current_release x left join cfg_release r on r.id=x.release_id where r.id is null)");
            var releaseMaterial=text(connection,"select coalesce(string_agg(release_no||':'||snapshot_hash,',' order by release_no),'') from cfg_release");
            var secretMaterial=text(connection,"select coalesce(string_agg(code||':'||fingerprint||':'||status,',' order by code),'') from ai_secret_ref");
            var content="engine="+safe(engine)+"\nflyway.version="+safe(flyway)+"\nrelease.count="+releases+"\ncurrent.release.count="+current
                    +"\nsecret.reference.count="+secrets+"\nrequest.count="+requests+"\naudit.count="+audits
                    +"\nseed.import.count="+seedImports+"\nrole.count="+roles+"\nscenario.count="+scenarios
                    +"\nscenario.case.count="+cases+"\nscenario.turn.count="+turns+"\nrelease.item.count="+releaseItems
                    +"\nrole.org.scope.count="+orgScopes+"\nrole.metric.scope.count="+metricScopes
                    +"\nrole.table.scope.count="+tableScopes+"\nmigration.audit.count="+migrationAudits
                    +"\norphan.link.count="+orphanLinks
                    +"\nrelease.snapshot.digest="+hash(releaseMaterial)+"\nsecret.reference.digest="+hash(secretMaterial)+"\n";
            Files.writeString(output,content,StandardCharsets.UTF_8);
        }
    }
    static void seedDrill(String url,String user,String password)throws Exception{
        try(var connection=DriverManager.getConnection(url,user,password);var statement=connection.createStatement()){
            statement.executeUpdate("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash) values ('drill-release','灾备演练版本','PUBLISHED','{\"drill\":true}','"+"a".repeat(64)+"')");
            statement.executeUpdate("insert into cfg_current_release(environment,release_id) select 'TEST',id from cfg_release where release_no='drill-release'");
            statement.executeUpdate("insert into ai_secret_ref(code,secret_type,provider_type,external_ref,fingerprint,status) values ('drill-secret-ref','API_KEY','TEST','vault://drill/reference','"+"b".repeat(64)+"','ACTIVE')");
        }
    }
    private static long number(java.sql.Connection connection,String sql)throws Exception{try(var s=connection.createStatement();var r=s.executeQuery(sql)){r.next();return r.getLong(1);}}
    private static String text(java.sql.Connection connection,String sql)throws Exception{try(var s=connection.createStatement();var r=s.executeQuery(sql)){r.next();return r.getString(1);}}
    private static String hash(String value)throws Exception{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value.getBytes(StandardCharsets.UTF_8)));}
    private static String safe(String value){return value==null?"":value.replace("\n","").replace("\r","");}
    private static String sqlPath(Path path){return path.toString().replace("'","''");}
    private static void require(boolean condition,String message){if(!condition)throw new IllegalStateException(message);}
}
