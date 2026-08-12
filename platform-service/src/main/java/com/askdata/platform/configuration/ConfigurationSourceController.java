package com.askdata.platform.configuration;

import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v2/admin/configuration-source")
public class ConfigurationSourceController {
    private final ConfigurationSourceService service;
    public ConfigurationSourceController(ConfigurationSourceService service){this.service=service;}
    @GetMapping public ConfigurationSourceService.SourceState current(){return service.current();}
    @PostMapping("/disable-legacy-read") public ConfigurationSourceService.SourceState disableLegacyRead(@RequestHeader(value="X-Actor-Id",defaultValue="0")long actor){return service.disableLegacyRead(actor);}
}
