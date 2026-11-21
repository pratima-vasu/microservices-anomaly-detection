package com.microservice.anomaly.userservice.fault;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/faults/combined")
public class CombinedFaultController {
    private final FaultInjectionService faultService;
    private final CombinedFaultInjectionService combinedService;

    public CombinedFaultController(FaultInjectionService faultService, CombinedFaultInjectionService combinedService) {
        this.faultService = faultService;
        this.combinedService = combinedService;
    }

    public record CombinedFaultRequest(String combination, int durationSeconds, long delayMillis,
                                       long cpuMillis, int errorPercent, int threadCount, int requestRate) {}

    @PostMapping("/enable")
    public ResponseEntity<?> enable(@RequestBody CombinedFaultRequest request) {
        try {
            faultService.disable();
            combinedService.enable(request.combination(), request.durationSeconds(), request.delayMillis(),
                    request.cpuMillis(), request.errorPercent(), request.threadCount(), request.requestRate());
            return ResponseEntity.ok("Combined fault enabled: " + combinedService.getStatus());
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    @PostMapping("/disable")
    public ResponseEntity<String> disable() {
        combinedService.disable();
        return ResponseEntity.ok("Combined fault disabled");
    }

    @GetMapping("/status")
    public ResponseEntity<String> status() {
        return ResponseEntity.ok(combinedService.getStatus());
    }
}