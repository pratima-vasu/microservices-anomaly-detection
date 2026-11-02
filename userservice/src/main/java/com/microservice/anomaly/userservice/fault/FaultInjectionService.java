
package com.microservice.anomaly.userservice.fault;

import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.concurrent.ThreadLocalRandom;

@Service
public class FaultInjectionService {

    private volatile String type = "NONE";
    private volatile Instant expiresAt = Instant.EPOCH;

    private volatile long delayMillis = 0;
    private volatile int errorPercent = 0;
    private volatile long cpuMillis = 0;

    public synchronized void enable(
            String requestedType,
            int durationSeconds,
            long requestedDelayMillis,
            int requestedErrorPercent,
            long requestedCpuMillis) {

        String normalized = requestedType.toUpperCase();

        if (!normalized.equals("RESPONSE_TIME")
                && !normalized.equals("ERROR_RATE")
                && !normalized.equals("CPU")) {
            throw new IllegalArgumentException(
                    "Supported types: RESPONSE_TIME, ERROR_RATE, CPU");
        }

        if (durationSeconds < 1 || durationSeconds > 300) {
            throw new IllegalArgumentException(
                    "Duration must be between 1 and 300 seconds");
        }

        if (requestedDelayMillis < 0 || requestedDelayMillis > 3000) {
            throw new IllegalArgumentException(
                    "Delay must be between 0 and 3000 ms");
        }

        if (requestedErrorPercent < 0 || requestedErrorPercent > 50) {
            throw new IllegalArgumentException(
                    "Error percentage must be between 0 and 50");
        }

        if (requestedCpuMillis < 0 || requestedCpuMillis > 100) {
            throw new IllegalArgumentException(
                    "CPU work per request must be between 0 and 100 ms");
        }

        delayMillis = requestedDelayMillis;
        errorPercent = requestedErrorPercent;
        cpuMillis = requestedCpuMillis;

        expiresAt = Instant.now().plusSeconds(durationSeconds);
        type = normalized;
    }

    public synchronized void disable() {
        type = "NONE";
        expiresAt = Instant.EPOCH;
    }

    public String getStatus() {
        if (!isActive()) {
            return "NONE";
        }
        return type;
    }

    private boolean isActive() {
        if (Instant.now().isAfter(expiresAt)) {
            type = "NONE";
            return false;
        }
        return !"NONE".equals(type);
    }

    public void applyFault(
            jakarta.servlet.http.HttpServletResponse response)
            throws java.io.IOException {

        if (!isActive()) {
            return;
        }

        String currentType = type;

        if ("RESPONSE_TIME".equals(currentType)) {
            try {
                Thread.sleep(delayMillis);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                response.sendError(503, "Request interrupted");
            }
        }

        if ("ERROR_RATE".equals(currentType)
                && ThreadLocalRandom.current().nextInt(100)
                   < errorPercent) {
            response.sendError(503, "Controlled fault injection");
            return;
        }

        if ("CPU".equals(currentType)) {
            long end = System.nanoTime() + cpuMillis * 1_000_000L;
            while (System.nanoTime() < end) {
                Math.sqrt(ThreadLocalRandom.current().nextDouble());
            }
        }
    }
}
