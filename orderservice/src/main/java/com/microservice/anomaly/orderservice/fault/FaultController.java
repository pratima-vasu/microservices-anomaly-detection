
package com.microservice.anomaly.orderservice.fault;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/faults")
public class FaultController {

    private final FaultInjectionService faultService;

    public FaultController(FaultInjectionService faultService) {
        this.faultService = faultService;
    }

    public record FaultRequest(
            String type,
            int durationSeconds,
            long delayMillis,
            int errorPercent,
            long cpuMillis,
            int memoryMb,
            int threadCount) {
    }

    @PostMapping("/enable")
    public ResponseEntity<?> enable(@RequestBody FaultRequest request) {
        try {
            faultService.enable(
                    request.type(),
                    request.durationSeconds(),
                    request.delayMillis(),
                    request.errorPercent(),
                    request.cpuMillis(),
                    request.memoryMb(),
                    request.threadCount());

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
