package com.askdata.platform.seed;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class LegacySeedImporter {
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper = new ObjectMapper();

    public LegacySeedImporter(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional
    public ImportSummary importDirectory(Path directory) throws IOException {
        var baselinePath = directory.resolve("official_baseline_v1.json");
        var runtimePath = directory.resolve("demo_runtime_defaults.json");
        var resourcesPath = directory.resolve("legacy_admin_resources_v1.json");
        var baselineBytes = Files.readAllBytes(baselinePath);
        var runtimeBytes = Files.readAllBytes(runtimePath);
        var resourcesBytes = Files.readAllBytes(resourcesPath);
        var baseline = mapper.readTree(baselineBytes);
        var runtime = mapper.readTree(runtimeBytes);
        var resources = mapper.readTree(resourcesBytes);
        var baselineHash = sha256(baselineBytes);
        var runtimeHash = sha256(runtimeBytes);
        var resourcesHash = sha256(resourcesBytes);

        // 已导入的相同种子只做对账并直接返回，绝不覆盖数据库中的日常管理事实。
        if (importedWithHash("official_baseline", baselineHash)
                && importedWithHash("runtime_defaults", runtimeHash)
                && importedWithHash("legacy_admin_resources", resourcesHash)) {
            return new ImportSummary(baseline.get("roles").size(), baseline.get("scenarios").size(),
                    countCases(baseline), countTurns(baseline), resources.size(), baselineHash, runtimeHash);
        }
        if (count("select count(*) from cfg_seed_import") > 0) {
            throw new IllegalStateException("数据库已导入不同版本的种子；禁止覆盖，灾备恢复必须使用独立恢复流程");
        }

        upsertRelease(baseline, baselineHash);
        importIdentity(baseline);
        importAssets(baseline);
        importFlow(baseline);
        importReleaseItem("runtime_defaults", "demo-runtime-defaults", runtime, runtimeHash);
        for (var resource : resources) {
            importReleaseItem("legacy_admin:" + resource.get("kind").asText(), resource.get("id").asText(),
                    resource, sha256(mapper.writeValueAsBytes(resource)));
        }
        upsertLedger("official_baseline", baselinePath, baselineHash, countBaselineRows(baseline));
        upsertLedger("runtime_defaults", runtimePath, runtimeHash, runtime.size());
        upsertLedger("frontend_baseline", baselinePath, baselineHash, countBaselineRows(baseline));
        upsertLedger("legacy_admin_resources", resourcesPath, resourcesHash, resources.size());
        return new ImportSummary(baseline.get("roles").size(), baseline.get("scenarios").size(),
                countCases(baseline), countTurns(baseline), resources.size(), baselineHash, runtimeHash);
    }

    private boolean importedWithHash(String sourceCode, String sourceHash) {
        return count("select count(*) from cfg_seed_import where source_code=? and source_hash=?", sourceCode, sourceHash) == 1;
    }

    private void upsertRelease(JsonNode baseline, String hash) throws IOException {
        var existing = count("select count(*) from cfg_release where release_no=?", baseline.get("id").asText());
        var snapshot = mapper.writeValueAsString(baseline);
        if (existing == 0) {
            jdbc.update("insert into cfg_release(release_no,name,status,snapshot_json,snapshot_hash,change_summary,published_at) values (?,?,?,?,?,?,?)",
                    baseline.get("id").asText(), "一期二期官方基线", "PUBLISHED", snapshot, hash, "P323幂等迁移", OffsetDateTime.now());
        } else {
            jdbc.update("update cfg_release set snapshot_json=?, snapshot_hash=? where release_no=?", snapshot, hash, baseline.get("id").asText());
        }
        var releaseId = releaseId();
        if (count("select count(*) from cfg_current_release where environment='DEMO'") == 0) {
            jdbc.update("insert into cfg_current_release(environment,release_id) values ('DEMO',?)", releaseId);
        } else {
            jdbc.update("update cfg_current_release set release_id=?, updated_at=current_timestamp where environment='DEMO'", releaseId);
        }
    }

    private void importIdentity(JsonNode baseline) {
        var orgs = new LinkedHashSet<String>();
        baseline.get("roles").forEach(role -> role.get("orgs").forEach(org -> orgs.add(org.asText())));
        int sort = 0;
        for (var name : orgs) {
            var code = orgCode(name);
            if (count("select count(*) from iam_org where code=?", code) == 0) {
                jdbc.update("insert into iam_org(code,name,org_type,path,level_no,sort_no,status) values (?,?,?,?,?,?,?)",
                        code, name, name.equals("全行") ? "HEAD_OFFICE" : "BRANCH", "/" + code, name.equals("全行") ? 0 : 1, sort++, "ENABLED");
            }
        }
        for (var role : baseline.get("roles")) {
            var code = role.get("id").asText();
            if (count("select count(*) from iam_role where code=?", code) == 0) {
                jdbc.update("insert into iam_role(code,name,role_type,priority,status) values (?,?,?,?,?)",
                        code, role.get("name").asText(), code.equals("admin") ? "ADMIN" : "BUSINESS", code.equals("admin") ? 100 : 10, "ENABLED");
            }
            var userPublicId = UUID.nameUUIDFromBytes(("demo:" + code).getBytes(StandardCharsets.UTF_8)).toString();
            if (count("select count(*) from iam_user where public_id=?", userPublicId) == 0) {
                var orgId = id("select id from iam_org where code=?", orgCode(role.get("orgs").get(0).asText()));
                jdbc.update("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values (?,?,?,?,?,?,?,?)",
                        userPublicId, code, role.get("name").asText(), code.equals("admin") ? "ADMIN" : "BUSINESS", orgId, "demo-local", code, "ENABLED");
            }
            var roleId = id("select id from iam_role where code=?", code);
            var userId = id("select id from iam_user where public_id=?", userPublicId);
            if (count("select count(*) from iam_user_role where user_id=? and role_id=?", userId, roleId) == 0) {
                jdbc.update("insert into iam_user_role(user_id,role_id) values (?,?)", userId, roleId);
            }
            for (var feature : role.get("features")) {
                var permissionCode = "feature:" + feature.asText();
                if (count("select count(*) from iam_permission where code=?", permissionCode) == 0) {
                    jdbc.update("insert into iam_permission(code,name,permission_type,status) values (?,?,?,?)", permissionCode, feature.asText(), "FEATURE", "ENABLED");
                }
                var permissionId = id("select id from iam_permission where code=?", permissionCode);
                if (count("select count(*) from iam_role_permission where role_id=? and permission_id=?", roleId, permissionId) == 0) {
                    jdbc.update("insert into iam_role_permission(role_id,permission_id,effect) values (?,?,'ALLOW')", roleId, permissionId);
                }
            }
        }
    }

    private void importAssets(JsonNode baseline) {
        var metrics = Map.of("贷款投放", "loan_cur", "零售贷款", "retail_cur", "对公贷款", "corporate_cur");
        baseline.at("/assets/metrics").forEach(metric -> {
            var name = metric.asText();
            if (count("select count(*) from meta_metric where code=?", metrics.get(name)) == 0) {
                jdbc.update("insert into meta_metric(code,name,business_definition,calculation_expression,unit,aggregation_type,classification_level,detail_allowed,status) values (?,?,?,?,?,?,?,?,?)",
                        metrics.get(name), name, name + "官方演示口径", metrics.get(name), "元", "SUM", "INTERNAL", false, "ENABLED");
            }
        });
        var dimensions = Map.of("机构", "org", "统计日期", "stat_dt");
        baseline.at("/assets/dimensions").forEach(dimension -> {
            var name = dimension.asText();
            if (count("select count(*) from meta_dimension where code=?", dimensions.get(name)) == 0) {
                jdbc.update("insert into meta_dimension(code,name,dimension_type,status) values (?,?,?,?)", dimensions.get(name), name, "STANDARD", "ENABLED");
            }
        });
        if (count("select count(*) from meta_data_source where code='official-demo-source'") == 0) {
            jdbc.update("insert into meta_data_source(code,name,source_type,environment,endpoint,database_name,username,tls_enabled,read_only,max_rows,timeout_seconds,status) values ('official-demo-source','官方演示数据源','SQLITE','TEST','file:demo-warehouse','demo','readonly',false,true,1000,30,'ENABLED')");
        }
        var sourceId = id("select id from meta_data_source where code='official-demo-source'");
        var tableName = baseline.at("/assets/table").asText();
        if (count("select count(*) from meta_data_table where data_source_id=? and schema_name='main' and table_name=?", sourceId, tableName) == 0) {
            jdbc.update("insert into meta_data_table(data_source_id,schema_name,table_name,display_name,table_type,query_priority,allowed,classification_level,status) values (?,'main',?,'贷款指标宽表','WIDE',100,true,'INTERNAL','ENABLED')", sourceId, tableName);
        }
        var tableId = id("select id from meta_data_table where data_source_id=? and schema_name='main' and table_name=?", sourceId, tableName);
        var fieldRoles = Map.of("stat_dt","TIME","org_name","ORG","loan_cur","METRIC","loan_last","METRIC","retail_cur","METRIC","retail_last","METRIC","corporate_cur","METRIC","corporate_last","METRIC");
        for (var entry : fieldRoles.entrySet()) {
            if (count("select count(*) from meta_data_field where table_id=? and field_name=?", tableId, entry.getKey()) == 0) {
                jdbc.update("insert into meta_data_field(table_id,field_name,display_name,data_type,nullable,field_role,classification_level,masking_required,status) values (?,?,?,?,false,?,'INTERNAL',false,'ENABLED')",
                        tableId, entry.getKey(), entry.getKey(), entry.getKey().equals("stat_dt") ? "DATE" : entry.getKey().equals("org_name") ? "VARCHAR" : "DECIMAL", entry.getValue());
            }
        }
        for (var entry : metrics.entrySet()) {
            var metricId = id("select id from meta_metric where code=?", entry.getValue());
            var currentField = id("select id from meta_data_field where table_id=? and field_name=?", tableId, entry.getValue());
            var previousField = id("select id from meta_data_field where table_id=? and field_name=?", tableId, entry.getValue().replace("_cur", "_last"));
            if (count("select count(*) from meta_metric_mapping where metric_id=? and table_id=?", metricId, tableId) == 0) {
                jdbc.update("insert into meta_metric_mapping(metric_id,table_id,current_field_id,previous_field_id,priority,status) values (?,?,?,?,100,'ENABLED')", metricId, tableId, currentField, previousField);
                jdbc.update("insert into meta_lineage_edge(source_type,source_id,target_type,target_id,relation_type,status) values ('FIELD',?,'METRIC',?,'CALCULATES','ENABLED')", currentField, metricId);
            }
        }
        var dimensionFields = Map.of("org", "org_name", "stat_dt", "stat_dt");
        for (var entry : dimensionFields.entrySet()) {
            var dimensionId = id("select id from meta_dimension where code=?", entry.getKey());
            var fieldId = id("select id from meta_data_field where table_id=? and field_name=?", tableId, entry.getValue());
            if (count("select count(*) from meta_dimension_mapping where dimension_id=? and table_id=?", dimensionId, tableId) == 0) {
                jdbc.update("insert into meta_dimension_mapping(dimension_id,table_id,field_id,status) values (?,?,?,'ENABLED')", dimensionId, tableId, fieldId);
            }
        }
        baseline.at("/assets/synonyms").properties().forEach(entry -> {
            if (count("select count(*) from meta_synonym where term=? and canonical_term=?", entry.getKey(), entry.getValue().asText()) == 0) {
                jdbc.update("insert into meta_synonym(term,canonical_term,priority,status) values (?,?,100,'ENABLED')", entry.getKey(), entry.getValue().asText());
            }
        });
        baseline.at("/assets/recommendations").properties().forEach(entry -> {
            var roleId = id("select id from iam_role where code=?", entry.getKey());
            for (var question : entry.getValue()) {
                if (count("select count(*) from meta_recommendation where role_id=? and question_template=?", roleId, question.asText()) == 0) {
                    jdbc.update("insert into meta_recommendation(role_id,keyword,question_template,priority,status) values (?,?,?,100,'ENABLED')", roleId, "贷款", question.asText());
                }
            }
        });
        var sql = baseline.at("/assets/sql_template").asText();
        if (count("select count(*) from flow_sql_template where code='official-loan-query'") == 0) {
            jdbc.update("insert into flow_sql_template(code,name,template_type,sql_text,dialect,max_rows,timeout_seconds,checksum,status) values (?,?,?,?,?,?,?,?,?)",
                    "official-loan-query", "官方贷款查询", "PARAMETERIZED", sql, "SQLITE", 1000, 30, sha256(sql.getBytes(StandardCharsets.UTF_8)), "ENABLED");
        }
    }

    private void importFlow(JsonNode baseline) {
        for (int layer = 1; layer <= 7; layer++) {
            var code = "L" + layer;
            if (count("select count(*) from flow_layer_config where layer_code=?", code) == 0) {
                jdbc.update("insert into flow_layer_config(layer_code,layer_name,sequence_no,handler_code,provider_type,timeout_seconds,status) values (?,?,?,?,?,30,'ENABLED')",
                        code, "七层-" + code, layer, "python:" + code.toLowerCase(), layer == 2 || layer == 7 ? "MODEL_OPTIONAL" : "DETERMINISTIC");
            }
        }
        var parameters = Map.of("org", "机构", "date", "统计日期", "metric", "指标");
        for (var entry : parameters.entrySet()) {
            if (count("select count(*) from flow_parameter_rule where parameter_code=?", entry.getKey()) == 0) {
                jdbc.update("insert into flow_parameter_rule(parameter_code,name,data_type,required_flag,missing_prompt,option_source,status) values (?,?, 'STRING',true,?,?, 'ENABLED')",
                        entry.getKey(), entry.getValue(), "请补充" + entry.getValue(), "PUBLISHED_ASSET");
            }
        }
        for (var scenario : baseline.get("scenarios")) {
            var code = scenario.get("id").asText();
            var terminal = maxTerminalLayer(scenario);
            var intentCode = "intent-" + code;
            if (count("select count(*) from flow_intent_rule where code=?", intentCode) == 0) {
                jdbc.update("insert into flow_intent_rule(code,name,intent_type,keyword_pattern,priority,terminal_layer,handler_code,status) values (?,?,?,?,100,?,?,'ENABLED')",
                        intentCode, scenario.get("name").asText(), code.toUpperCase().replace('-', '_'), scenario.get("name").asText(), terminal, "scenario:" + code);
            }
            if (count("select count(*) from flow_scenario where code=?", code) == 0) {
                jdbc.update("insert into flow_scenario(code,name,terminal_layer,fallback_policy,sort_no,status,intent_rule_id) values (?,?,?,?,?,?,?)",
                        code, scenario.get("name").asText(), terminal, "NONE", scenario.get("number").asInt(), "ENABLED", id("select id from flow_intent_rule where code=?", intentCode));
            } else {
                jdbc.update("update flow_scenario set intent_rule_id=? where code=?", id("select id from flow_intent_rule where code=?", intentCode), code);
            }
            var scenarioId = id("select id from flow_scenario where code=?", code);
            if (terminal.equals("L7") && count("select count(*) from flow_scenario_sql where scenario_id=?", scenarioId) == 0) {
                jdbc.update("insert into flow_scenario_sql(scenario_id,sql_template_id,sequence_no,purpose,required_flag) values (?,?,1,?,true)",
                        scenarioId, id("select id from flow_sql_template where code='official-loan-query'"), "官方基线查询");
            }
            if (terminal.equals("L7")) {
                var sourceId = id("select id from meta_data_source where code='official-demo-source'");
                var tableId = id("select id from meta_data_table where data_source_id=? and table_name=?", sourceId, baseline.at("/assets/table").asText());
                for (var metric : List.of("loan_cur", "retail_cur", "corporate_cur")) {
                    var metricId = id("select id from meta_metric where code=?", metric);
                    if (count("select count(*) from flow_scenario_asset where scenario_id=? and table_id=? and metric_id=?", scenarioId, tableId, metricId) == 0) {
                        jdbc.update("insert into flow_scenario_asset(scenario_id,data_source_id,table_id,metric_id,priority) values (?,?,?,?,100)", scenarioId, sourceId, tableId, metricId);
                    }
                }
                for (var parameter : parameters.keySet()) {
                    var parameterId = id("select id from flow_parameter_rule where parameter_code=?", parameter);
                    if (count("select count(*) from flow_scenario_param where scenario_id=? and parameter_rule_id=?", scenarioId, parameterId) == 0) {
                        jdbc.update("insert into flow_scenario_param(scenario_id,parameter_rule_id,required_override,sort_no) values (?,?,true,?)", scenarioId, parameterId, parameter.equals("org") ? 1 : parameter.equals("date") ? 2 : 3);
                    }
                }
            }
            for (var scenarioCase : scenario.get("cases")) {
                var roleId = id("select id from iam_role where code=?", scenarioCase.get("role_id").asText());
                if (count("select count(*) from flow_scenario_role where scenario_id=? and role_id=?", scenarioId, roleId) == 0) {
                    jdbc.update("insert into flow_scenario_role(scenario_id,role_id,allowed_modes_json) values (?,?,?)", scenarioId, roleId, "[\"DEMO\",\"POC\"]");
                }
                var caseCode = scenarioCase.get("id").asText();
                if (count("select count(*) from flow_scenario_case where case_code=?", caseCode) == 0) {
                    jdbc.update("insert into flow_scenario_case(scenario_id,role_id,case_code,is_default,status) values (?,?,?,?,?)",
                            scenarioId, roleId, caseCode, scenarioCase.get("default").asBoolean(), "ENABLED");
                }
                var caseId = id("select id from flow_scenario_case where case_code=?", caseCode);
                for (var turn : scenarioCase.get("turns")) {
                    if (count("select count(*) from flow_scenario_turn where case_id=? and turn_no=?", caseId, turn.get("turn").asInt()) == 0) {
                        jdbc.update("insert into flow_scenario_turn(case_id,turn_no,question,expected_status,expected_last_layer,expected_execution,final_display) values (?,?,?,?,?,?,?)",
                                caseId, turn.get("turn").asInt(), turn.get("question").asText(), turn.get("expected_status").asText(),
                                turn.get("expected_last_layer").asText(), turn.get("execution").asText(), turn.get("final_display").asText());
                    }
                }
            }
        }
        var scenario1 = id("select id from flow_scenario where code='scenario-1'");
        baseline.at("/assets/recommendations").properties().forEach(entry -> {
            var roleId = id("select id from iam_role where code=?", entry.getKey());
            int sort = 0;
            for (var question : entry.getValue()) {
                if (count("select count(*) from flow_quick_question where scenario_id=? and role_id=? and preset_question=?", scenario1, roleId, question.asText()) == 0) {
                    jdbc.update("insert into flow_quick_question(scenario_id,role_id,button_name,preset_question,tag,sort_no,status) values (?,?,?,?,?,?, 'ENABLED')",
                            scenario1, roleId, question.asText(), question.asText(), "official", sort++);
                }
            }
        });
        if (count("select count(*) from flow_dashboard where code='official-dashboard'") == 0) {
            jdbc.update("insert into flow_dashboard(code,name,url,tag,status) values ('official-dashboard','经营驾驶舱',?,'official','ENABLED')", baseline.at("/assets/dashboard").asText());
            var dashboardId = id("select id from flow_dashboard where code='official-dashboard'");
            baseline.get("roles").forEach(role -> jdbc.update("insert into flow_dashboard_role(dashboard_id,role_id) values (?,?)", dashboardId, id("select id from iam_role where code=?", role.get("id").asText())));
        }
        if (count("select count(*) from flow_fixture where code='official-warehouse-fixture'") == 0) {
            try { jdbc.update("insert into flow_fixture(code,fixture_json,allowed_modes_json,status) values ('official-warehouse-fixture',?,'[\"DEMO\"]','ENABLED')", mapper.writeValueAsString(baseline.get("warehouse_rows"))); }
            catch (Exception exception) { throw new IllegalStateException(exception); }
        }
        if (count("select count(*) from flow_wording where code='waiting-input-default'") == 0) {
            jdbc.update("insert into flow_wording(code,scene,language,content,status) values ('waiting-input-default','WAITING_INPUT','zh-CN','请补充缺失的机构、日期或指标。','ENABLED')");
        }
    }

    private void importReleaseItem(String type, String resourceId, JsonNode payload, String hash) throws IOException {
        var releaseId = releaseId();
        var json = mapper.writeValueAsString(payload);
        if (count("select count(*) from cfg_release_item where release_id=? and resource_type=? and resource_id=?", releaseId, type, resourceId) == 0) {
            jdbc.update("insert into cfg_release_item(release_id,resource_type,resource_id,operation,after_json,content_hash) values (?,?,?,'CREATE',?,?)",
                    releaseId, type, resourceId, json, hash);
        } else {
            jdbc.update("update cfg_release_item set after_json=?,content_hash=? where release_id=? and resource_type=? and resource_id=?",
                    json, hash, releaseId, type, resourceId);
        }
    }

    private void upsertLedger(String code, Path path, String hash, int rows) {
        if (count("select count(*) from cfg_seed_import where source_code=?", code) == 0) {
            jdbc.update("insert into cfg_seed_import(source_code,source_path,source_hash,imported_rows) values (?,?,?,?)", code, path.toString(), hash, rows);
        } else {
            jdbc.update("update cfg_seed_import set source_path=?,source_hash=?,imported_rows=?,imported_at=current_timestamp where source_code=?", path.toString(), hash, rows, code);
        }
    }

    private long releaseId() { return id("select id from cfg_release where release_no='official-demo-baseline-v1'"); }
    private long id(String sql, Object... args) { return jdbc.queryForObject(sql, Long.class, args); }
    private int count(String sql, Object... args) { return jdbc.queryForObject(sql, Integer.class, args); }
    private int countCases(JsonNode baseline) { int n=0; for(var s:baseline.get("scenarios")) n+=s.get("cases").size(); return n; }
    private int countTurns(JsonNode baseline) { int n=0; for(var s:baseline.get("scenarios")) for(var c:s.get("cases")) n+=c.get("turns").size(); return n; }
    private int countBaselineRows(JsonNode baseline) { return baseline.get("roles").size()+baseline.get("scenarios").size()+countCases(baseline)+countTurns(baseline); }
    private String orgCode(String name) { return switch (name) { case "全行" -> "org-all"; case "北京分行" -> "org-beijing"; case "上海分行" -> "org-shanghai"; default -> "org-" + sha256(name.getBytes(StandardCharsets.UTF_8)).substring(0, 12); }; }
    private String maxTerminalLayer(JsonNode scenario) { int max=1; for(var c:scenario.get("cases")) for(var t:c.get("turns")) max=Math.max(max, Integer.parseInt(t.get("expected_last_layer").asText().substring(1))); return "L"+max; }
    private String sha256(byte[] bytes) { try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes)); } catch (Exception e) { throw new IllegalStateException(e); } }

    public record ImportSummary(int roles, int scenarios, int cases, int turns, int legacyResources,
                                String baselineSha256, String runtimeSha256) {}
}
