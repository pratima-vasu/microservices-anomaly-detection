package com.microservice.anomaly.productservice.fault;

import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Value;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.concurrent.atomic.AtomicBoolean;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;

@Service
public class FaultInjectionService {

    private volatile String type = "NONE";
    private volatile Instant expiresAt = Instant.EPOCH;

    private volatile long delayMillis = 0;
    private volatile int errorPercent = 0;
    private volatile long cpuMillis = 0;
    private volatile List<Thread> workerThreads = new ArrayList<>();
    private volatile Thread requestRateThread;
    private final AtomicBoolean requestRateRunning = new AtomicBoolean(false);
    private final HttpClient requestRateClient = HttpClient.newBuilder().connectTimeout(java.time.Duration.ofSeconds(3)).build();
    @Value("${server.port:${PORT:8080}}")
    private int serverPort;

    public synchronized void enable(
            String requestedType,
            int durationSeconds,
            long requestedDelayMillis,
            int requestedErrorPercent,
            long requestedCpuMillis,
            int requestedRequestRate) {

        String normalized = requestedType.toUpperCase();

        if (!normalized.equals("RESPONSE_TIME")
                && !normalized.equals("ERROR_RATE")
                && !normalized.equals("CPU")
                && !normalized.equals("REQUEST_RATE")) {
            throw new IllegalArgumentException(
                    "Supported types: RESPONSE_TIME, ERROR_RATE, CPU, REQUEST_RATE");
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

        if (requestedCpuMillis < 0 || requestedCpuMillis > 200) {
            throw new IllegalArgumentException(
                    "CPU work per request must be between 0 and 200 ms");
        }

        if (requestedRequestRate < 1 || requestedRequestRate > 20) {
            throw new IllegalArgumentException("Request rate must be between 1 and 20 requests per second");
        }

        delayMillis = requestedDelayMillis;
        errorPercent = requestedErrorPercent;
        cpuMillis = requestedCpuMillis;

        disable();

        if ("REQUEST_RATE".equals(normalized)) {
            if (requestedRequestRate < 1 || requestedRequestRate > 20) throw new IllegalArgumentException("requestRate must be between 1 and 20");
            startRequestRate(requestedRequestRate, "/products");
        }

        expiresAt = Instant.now().plusSeconds(durationSeconds);
        type = normalized;
    }

    public synchronized void disable() {
        type = "NONE";
        expiresAt = Instant.EPOCH;
        List<Thread> threads = workerThreads;
        workerThreads = new ArrayList<>();
        for (Thread worker : threads) {
            worker.interrupt();
        }
    }

    private void startRequestRate(int requestsPerSecond, String endpoint) {
        stopRequestRate();
        requestRateRunning.set(true);
        Thread generator = new Thread(() -> {
            long intervalNanos = 1_000_000_000L / requestsPerSecond;
            URI target = URI.create("http://127.0.0.1:" + serverPort + "/products");
            while (requestRateRunning.get() && !Thread.currentThread().isInterrupted()) {
                long started = System.nanoTime();
                try {
                    HttpRequest request = HttpRequest.newBuilder(target).timeout(java.time.Duration.ofSeconds(5)).GET().build();
                    requestRateClient.send(request, HttpResponse.BodyHandlers.discarding());
                } catch (Exception ignored) { }
                long remaining = intervalNanos - (System.nanoTime() - started);
                if (remaining > 0) {
                    try { java.util.concurrent.TimeUnit.NANOSECONDS.sleep(remaining); }
                    catch (InterruptedException e) { Thread.currentThread().interrupt(); break; }
                }
            }
        }, "request-rate-generator");
        generator.setDaemon(true); requestRateThread = generator; generator.start();
    }

    private void stopRequestRate() {
        requestRateRunning.set(false);
        Thread generator = requestRateThread; requestRateThread = null;
        if (generator != null) generator.interrupt();
    }

    public String getStatus() {
        if (!isActive()) {
            return "NONE";
        }
        return type;
    }

    private boolean isActive() {
        if (Instant.now().isAfter(expiresAt)) {
            synchronized (this) {
                if (Instant.now().isAfter(expiresAt)) {
                    type = "NONE";
                    expiresAt = Instant.EPOCH;
                    List<Thread> threads = workerThreads;
                    workerThreads = new ArrayList<>();
                    for (Thread worker : threads) {
                        worker.interrupt();
                    }
                }
            }
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
