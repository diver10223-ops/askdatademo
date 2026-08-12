package com.askdata.platform.asset;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/v2/admin/assets/metrics")
public class AssetManagementController {
    private final AssetManagementService assets;

    public AssetManagementController(AssetManagementService assets) { this.assets = assets; }

    @GetMapping
    List<AssetManagementService.MetricView> list() { return assets.listMetrics(); }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    AssetManagementService.MetricView create(@Valid @RequestBody MetricRequest request,
                                              @RequestHeader(value = "X-Actor-Id", defaultValue = "0") long actorId) {
        return assets.createMetric(new AssetManagementService.MetricCommand(request.code, request.name, request.businessDefinition,
                request.calculationExpression, request.unit, request.aggregationType, request.classificationLevel, request.detailAllowed), actorId);
    }

    record MetricRequest(@NotBlank @Pattern(regexp = "[a-z][a-z0-9_-]{1,63}") String code,
                         @NotBlank @Size(max = 128) String name,
                         @NotBlank @Size(max = 4000) String businessDefinition,
                         @NotBlank @Size(max = 4000) String calculationExpression,
                         @NotBlank @Size(max = 32) String unit,
                         @Pattern(regexp = "SUM|AVG|MAX|MIN|RATIO|NONE") String aggregationType,
                         @Pattern(regexp = "PUBLIC|INTERNAL|SENSITIVE|SECRET|RESTRICTED") String classificationLevel,
                         boolean detailAllowed) {}
}
