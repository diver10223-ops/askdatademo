package com.askdata.platform.flow;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v2/admin/flows/scenarios")
public class FlowManagementController {
    private final FlowManagementService flows;
    public FlowManagementController(FlowManagementService flows){this.flows=flows;}
    @GetMapping List<FlowManagementService.ScenarioView> list(){return flows.list();}
    @PostMapping @ResponseStatus(HttpStatus.CREATED)
    FlowManagementService.ScenarioView create(@Valid @RequestBody ScenarioRequest request,@RequestHeader(value="X-Actor-Id",defaultValue="0")long actorId){
        return flows.create(new FlowManagementService.ScenarioCommand(request.code,request.name,request.description,request.terminalLayer,request.fallbackPolicy,request.sortNo),actorId);
    }
    record ScenarioRequest(@NotBlank @Pattern(regexp="[a-z][a-z0-9_-]{1,63}")String code,
                           @NotBlank @Size(max=128)String name,@Size(max=500)String description,
                           @Pattern(regexp="L[1-7]")String terminalLayer,
                           @Pattern(regexp="NONE|FIXTURE|AUDITED_FIXTURE")String fallbackPolicy,int sortNo){}
}
