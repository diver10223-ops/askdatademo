package com.askdata.platform.provider;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v2/admin/providers")
public class ProviderManagementController {
    private final ProviderManagementService service;
    public ProviderManagementController(ProviderManagementService service){this.service=service;}
    @PostMapping("/secrets") @ResponseStatus(HttpStatus.CREATED) public ProviderManagementService.SecretView createSecret(@RequestBody ProviderManagementService.SecretCommand command,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.createSecret(command,actor);}
    @PostMapping("/secrets/{code}/rotate") public ProviderManagementService.SecretView rotate(@PathVariable String code,@RequestBody ProviderManagementService.RotateSecretCommand command,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.rotateSecret(code,command,actor);}
    @PostMapping("/secrets/{code}/revoke") public ProviderManagementService.SecretView revoke(@PathVariable String code,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.revokeSecret(code,actor);}
    @GetMapping("/secrets/{code}") public ProviderManagementService.SecretView secret(@PathVariable String code){return service.secret(code);}
    @PostMapping("/models") @ResponseStatus(HttpStatus.CREATED) public ProviderManagementService.ModelView createModel(@RequestBody ProviderManagementService.ModelCommand command,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.createModel(command,actor);}
    @PostMapping("/models/{code}/diagnose") public ProviderManagementService.DiagnosticView diagnoseModel(@PathVariable String code,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.diagnoseModel(code,actor);}
    @PostMapping("/models/{code}/enable") public ProviderManagementService.ModelView enableModel(@PathVariable String code,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.enableModel(code,actor);}
    @PostMapping("/data-sources") @ResponseStatus(HttpStatus.CREATED) public ProviderManagementService.DataSourceView createDataSource(@RequestBody ProviderManagementService.DataSourceCommand command,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.createDataSource(command,actor);}
    @PostMapping("/data-sources/{code}/diagnose") public ProviderManagementService.DiagnosticView diagnoseDataSource(@PathVariable String code,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.diagnoseDataSource(code,actor);}
    @PostMapping("/data-sources/{code}/enable") public ProviderManagementService.DataSourceView enableDataSource(@PathVariable String code,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.enableDataSource(code,actor);}
    @PostMapping("/runtime-profiles") @ResponseStatus(HttpStatus.CREATED) public ProviderManagementService.RuntimeView createRuntime(@RequestBody ProviderManagementService.RuntimeCommand command,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.createRuntime(command,actor);}
    @PostMapping("/runtime-profiles/{code}/enable") public ProviderManagementService.RuntimeView enableRuntime(@PathVariable String code,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.enableRuntime(code,actor);}
}
