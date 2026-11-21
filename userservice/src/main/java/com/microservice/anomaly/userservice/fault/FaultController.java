
package com.microservice.anomaly.userservice.fault;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/faults")
public class FaultController {

    private final FaultInjectionService faultService;
    private final CombinedFaultInjectionService combinedFaultService;

    public FaultController(FaultInjectionService faultService, CombinedFaultInjectionService combinedFaultService) {
        this.faultService = faultService;
        this.combinedFaultService = combinedFaultService;
    }

    public record FaultRequest(
            String type,
            int durationSeconds,
            long delayMillis,
            int errorPercent,
            long cpuMillis,
            int requestRate) {}

    @PostMapping("/enable")
    public ResponseEntity<?> enable(@RequestBody FaultRequest request) {
        try {
            combinedFaultService.disable();
            faultService.enable(
                    request.type(),
                    request.durationSeconds(),
                    request.delayMillis(),
                    request.errorPercent(),
                    request.cpuMillis(),
                    request.requestRate());

            return ResponseEntity.ok(
                    "Fault enabled: " + faultService.getStatus());
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(e.getMessage());
        }
    }

    @PostMapping("/disable")
    public ResponseEntity<String> disable() {
        faultService.disable();
        return ResponseEntity.ok("Fault disabled");
    }

    @GetMapping("/status")
    public ResponseEntity<String> status() {
        return ResponseEntity.ok(faultService.getStatus());
    }
}
