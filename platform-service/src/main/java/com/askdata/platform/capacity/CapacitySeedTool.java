package com.askdata.platform.capacity;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.DriverManager;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/** Creates synthetic, credential-free capacity sessions in an isolated product database. */
public final class CapacitySeedTool {
    private CapacitySeedTool() {}

    public static void main(String[] args) throws Exception {
        if (args.length != 6 || !List.of("sessions", "events").contains(args[0])) {
            throw new IllegalArgumentException("usage: <sessions|events> <jdbc-url> <user> <password> <count|request-id> <output|event-count>");
        }
        if (args[0].equals("events")) {
            seedEvents(args[1], args[2], args[3], args[4], Integer.parseInt(args[5]));
            return;
        }
        var count = Integer.parseInt(args[4]);
        if (count < 1 || count > 10_000) throw new IllegalArgumentException("count must be 1..10000");
        var output = Path.of(args[5]).toAbsolutePath().normalize();
        var sessionIds = new ArrayList<String>();
        try (var connection = DriverManager.getConnection(args[1], args[2], args[3])) {
            connection.setAutoCommit(false);
            var releaseId = number(connection, "select id from cfg_release where release_no='official-demo-baseline-v1'");
            var roleId = number(connection, "select id from iam_role where code='admin'");
            var orgId = number(connection, "select id from iam_org where code='org-all'");
            try (var user = connection.prepareStatement("insert into iam_user(public_id,username,display_name,user_type,org_id,identity_provider_code,external_subject,status) values (?,?,?,?,?,'capacity',?,'ENABLED')", java.sql.Statement.RETURN_GENERATED_KEYS);
                 var userRole = connection.prepareStatement("insert into iam_user_role(user_id,role_id) values (?,?)");
                 var session = connection.prepareStatement("insert into run_session(public_id,user_id,role_snapshot_json,permission_snapshot_json,permission_version,config_release_id,execution_mode) values (?,?,'[\"admin\"]',?,1,?,'DEMO')")) {
                for (int index = 0; index < count; index++) {
                    var publicId = UUID.nameUUIDFromBytes(("capacity-user-" + index).getBytes(StandardCharsets.UTF_8)).toString();
                    user.setString(1, publicId); user.setString(2, "capacity-" + index); user.setString(3, "Capacity " + index);
                    user.setString(4, "BUSINESS"); user.setLong(5, orgId); user.setString(6, publicId); user.executeUpdate();
                    try (var keys = user.getGeneratedKeys()) { keys.next(); var userId = keys.getLong(1);
                        userRole.setLong(1, userId); userRole.setLong(2, roleId); userRole.executeUpdate();
                        var sessionId = UUID.nameUUIDFromBytes(("capacity-session-" + index).getBytes(StandardCharsets.UTF_8)).toString();
                        session.setString(1, sessionId); session.setLong(2, userId);
                        session.setString(3, "{\"orgs\":[\"全行\"],\"metrics\":[\"贷款投放\"],\"tables\":[\"dws_loan_aggr_wide\"],\"fields\":[],\"permissionVersion\":1}");
                        session.setLong(4, releaseId); session.executeUpdate(); sessionIds.add(sessionId);
                    }
                }
            }
            connection.commit();
        }
        Files.write(output, sessionIds, StandardCharsets.UTF_8);
        System.out.println("CAPACITY_SEED_PASS sessions=" + sessionIds.size() + " output=" + output);
    }

    private static void seedEvents(String url, String user, String password, String requestId, int count) throws Exception {
        if (count < 1 || count > 100) throw new IllegalArgumentException("event count must be 1..100");
        try (var connection = DriverManager.getConnection(url, user, password)) {
            var databaseId = number(connection, "select id from run_request where public_id='" + requestId.replace("'", "''") + "'");
            try (var statement = connection.prepareStatement("insert into run_sse_event(request_id,event_id,event_type,payload_json,created_at) values (?,?,?,?,current_timestamp)")) {
                for (int eventId = 1; eventId <= count; eventId++) {
                    statement.setLong(1, databaseId); statement.setInt(2, eventId);
                    statement.setString(3, eventId == count ? "capacity.ready" : "capacity.progress");
                    statement.setString(4, "{\"sequence\":" + eventId + "}"); statement.executeUpdate();
                }
            }
        }
        System.out.println("CAPACITY_EVENT_SEED_PASS request=" + requestId + " events=" + count);
    }

    private static long number(java.sql.Connection connection, String sql) throws Exception {
        try (var statement = connection.createStatement(); var result = statement.executeQuery(sql)) {
            result.next(); return result.getLong(1);
        }
    }
}
