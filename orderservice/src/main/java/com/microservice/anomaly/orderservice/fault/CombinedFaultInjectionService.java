package com.microservice.anomaly.orderservice.fault;

import jakarta.annotation.PreDestroy;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ThreadLocalRandom;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Semaphore;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Value;

@Service
public class CombinedFaultInjectionService {
    private volatile String combination = "NONE";
    private volatile Instant expiresAt = Instant.EPOCH;
    private volatile long delayMillis;
    private volatile long cpuMillis;
    private volatile int errorPercent;
    private volatile List<Thread> workerThreads = new ArrayList<>();
    private volatile ScheduledExecutorService trafficScheduler;
    private final AtomicBoolean trafficRunning = new AtomicBoolean(false);
    // Cap in-flight synthetic requests to protect the service if responses slow down.
    private final Semaphore trafficPermits = new Semaphore(50);
    private final HttpClient httpClient = HttpClient.newBuilder().connectTimeout(java.time.Duration.ofSeconds(3)).build();
    @Value("${server.port:${PORT:8080}}")
    private int serverPort;

    public synchronized void enable(String requestedCombination, int durationSeconds,
                                    long requestedDelayMillis, long requestedCpuMillis,
                                    int requestedErrorPercent, int requestedThreadCount, int requestedRequestRate) {
        String normalized = requestedCombination == null ? "" : requestedCombination.trim().toUpperCase();
        if (!List.of("CPU+RESPONSE_TIME", "REQUEST_RATE+ERROR_RATE", "ERROR_RATE+RESPONSE_TIME").contains(normalized)) {
            throw new IllegalArgumentException("Supported combinations: CPU+RESPONSE_TIME, THREAD_COUNT+ERROR_RATE, ERROR_RATE+RESPONSE_TIME");
        }
        if (durationSeconds < 1 || durationSeconds > 300) throw new IllegalArgumentException("Duration must be between 1 and 300 seconds");
        if (requestedDelayMillis < 0 || requestedDelayMillis > 6000) throw new IllegalArgumentException("Delay must be between 0 and 6000 ms");
        if (requestedCpuMillis < 0 || requestedCpuMillis > 200) throw new IllegalArgumentException("CPU work per request must be between 0 and 200 ms");
        if (requestedErrorPercent < 0 || requestedErrorPercent > 50) throw new IllegalArgumentException("Error percentage must be between 0 and 50");
        if (requestedThreadCount < 0 || requestedThreadCount > 25) throw new IllegalArgumentException("Thread count must be between 0 and 25");
        if (requestedRequestRate < 0 || requestedRequestRate > 20) throw new IllegalArgumentException("Request rate must be between 0 and 20 requests per second");
        if (normalized.equals("CPU+RESPONSE_TIME") && (requestedCpuMillis < 1 || requestedDelayMillis < 1)) throw new IllegalArgumentException("CPU and response delay must both be greater than zero");
        if (normalized.equals("REQUEST_RATE+ERROR_RATE") && (requestedRequestRate < 5 || requestedRequestRate > 20 || requestedErrorPercent < 1)) throw new IllegalArgumentException("Request rate must be between 5 and 20 requests per second and error percentage must be greater than zero");
        if (normalized.equals("ERROR_RATE+RESPONSE_TIME") && (requestedErrorPercent < 1 || requestedDelayMillis < 1)) throw new IllegalArgumentException("Error percentage and response delay must both be greater than zero");

        disable();
        delayMillis = requestedDelayMillis;
        cpuMillis = requestedCpuMillis;
        errorPercent = requestedErrorPercent;
        if (normalized.equals("REQUEST_RATE+ERROR_RATE")) {
            startRequestTraffic(requestedRequestRate);
        } else if (normalized.equals("THREAD_COUNT+ERROR_RATE")) {
            List<Thread> workers = new ArrayList<>();
            for (int i = 0; i < requestedThreadCount; i++) {
                Thread worker = new Thread(() -> {
                    try { while (!Thread.currentThread().isInterrupted()) Thread.sleep(1000); }
                    catch (InterruptedException e) { Thread.currentThread().interrupt(); }
                }, "combined-fault-worker-" + i);
                worker.setDaemon(true);
                workers.add(worker);
                worker.start();
            }
            workerThreads = workers;
        }
        expiresAt = Instant.now().plusSeconds(durationSeconds);
        combination = normalized;
    }

    public synchronized void disable() {
        combination = "NONE";
        expiresAt = Instant.EPOCH;

        // Stop only scheduled synthetic fault traffic. Normal incoming API requests remain available.
        trafficRunning.set(false);
        ScheduledExecutorService oldTraffic = trafficScheduler;
        trafficScheduler = null;
        if (oldTraffic != null) {
            oldTraffic.shutdownNow();
        }

        List<Thread> old = workerThreads;
        workerThreads = new ArrayList<>();
        for (Thread thread : old) thread.interrupt();
    }


    @PreDestroy
    public void shutdown() {
        // Stops only synthetic fault traffic and worker threads, not normal incoming requests.
        disable();
    }

    private void startRequestTraffic(int requestsPerSecond) {
        trafficRunning.set(true);
        URI target = URI.create("http://127.0.0.1:" + serverPort + "/orders");

        ScheduledExecutorService scheduler = Executors.newSingleThreadScheduledExecutor(task -> {
            Thread thread = new Thread(task, "combined-request-rate-scheduler");
            thread.setDaemon(true);
            return thread;
        });
        trafficScheduler = scheduler;

        long periodNanos = Math.max(1L, TimeUnit.SECONDS.toNanos(1) / requestsPerSecond);
        scheduler.scheduleAtFixedRate(() -> {
            if (!trafficRunning.get() || !trafficPermits.tryAcquire()) {
                return;
            }

            try {
                HttpRequest request = HttpRequest.newBuilder(target)
                        .timeout(java.time.Duration.ofSeconds(5))
                        .GET()
                        .build();

                httpClient.sendAsync(request, HttpResponse.BodyHandlers.discarding())
                        .whenComplete((response, error) -> trafficPermits.release());
            } catch (RuntimeException error) {
                trafficPermits.release();
            }
        }, 0, periodNanos, TimeUnit.NANOSECONDS);
    }

    private boolean isActive() {
        if (Instant.now().isAfter(expiresAt)) {
            synchronized (this) {
                if (Instant.now().isAfter(expiresAt)) disable();
            }
            return false;
        }
        return !"NONE".equals(combination);
    }

    public String getStatus() { return isActive() ? combination : "NONE"; }

    public void applyFault(HttpServletResponse response) throws Exception {
        if (!isActive()) return;
        String active = combination;
        if (active.equals("CPU+RESPONSE_TIME")) {
            long end = System.nanoTime() + cpuMillis * 1_000_000L;
            while (System.nanoTime() < end) Math.sqrt(ThreadLocalRandom.current().nextDouble());
            Thread.sleep(delayMillis);
        } else if (active.equals("ERROR_RATE+RESPONSE_TIME")) {
            Thread.sleep(delayMillis);
            if (ThreadLocalRandom.current().nextInt(100) < errorPercent) {
                response.sendError(503, "Combined error-rate fault injection");
            }
        } else if (active.equals("THREAD_COUNT+ERROR_RATE") || active.equals("REQUEST_RATE+ERROR_RATE")) {
            if (ThreadLocalRandom.current().nextInt(100) < errorPercent) {
                response.sendError(503, "Combined error-rate fault injection");
            }
        }
    }
}
