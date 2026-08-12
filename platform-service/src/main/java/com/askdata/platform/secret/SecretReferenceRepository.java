package com.askdata.platform.secret;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.util.Optional;

@Repository
public class SecretReferenceRepository {
    private final JdbcTemplate jdbc;

    public SecretReferenceRepository(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public long create(String code, String secretType, String providerType, String externalRef, String fingerprint) {
        jdbc.update("insert into ai_secret_ref(code, secret_type, provider_type, external_ref, fingerprint, status) values (?,?,?,?,?,'ACTIVE')",
                code, secretType, providerType, externalRef, fingerprint);
        return jdbc.queryForObject("select id from ai_secret_ref where code=?", Long.class, code);
    }

    public Optional<PublicSecretReference> findPublicByCode(String code) {
        return jdbc.query("select id, code, secret_type, provider_type, fingerprint, status from ai_secret_ref where code=?",
                (rs, row) -> new PublicSecretReference(rs.getLong("id"), rs.getString("code"), rs.getString("secret_type"),
                        rs.getString("provider_type"), rs.getString("fingerprint"), rs.getString("status")), code).stream().findFirst();
    }

    public record PublicSecretReference(long id, String code, String secretType, String providerType,
                                        String fingerprint, String status) {}
}
