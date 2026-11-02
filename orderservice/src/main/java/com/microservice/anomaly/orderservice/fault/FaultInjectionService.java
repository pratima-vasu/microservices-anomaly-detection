
package com.microservice.anomaly.orderservice.fault;

import org.springframework.stereotype.Service;

import jakarta.annotation.PreDestroy;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.TimeUnit;

@Service
public class FaultInjectionService {

    private volatile String type = "NONE";
    private volatile Instant expiresAt = Instant.EPOCH;

    private volatile long delayMillis = 0;
    private volatile int errorPercent = 0;
    private volatile long cpuMillis = 0;

    private volatile byte[][] memoryBlocks = new byte[0][];
    private volatile ExecutorService threadExecutor;
    private volatile List<Thread> workerThreads = new ArrayList<>();

    public synchronized void enable(
            String requestedType,
            int durationSeconds,
            long requestedDelayMillis,
            int requestedErrorPercent,
            long requestedCpuMillis,
            int requestedMemoryMb,
            int requestedThreadCount) {

        if (requestedType == null || requestedType.isBlank()) {
            throw new IllegalArgumentException("Fault type is required");
        }

        String normalized = requestedType.trim().toUpperCase();

        if (!List.of(
                "RESPONSE_TIME",
                "ERROR_RATE",
                "CPU",
                "JVM_MEMORY",
                "THREAD_COUNT"
        ).contains(normalized)) {
            throw new IllegalArgumentException(
                    "Supported types: RESPONSE_TIME, ERROR_RATE, CPU, "
                    + "JVM_MEMORY, THREAD_COUNT");
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

        if (requestedMemoryMb < 0 || requestedMemoryMb > 100) {
            throw new IllegalArgumentException(
                    "Memory must be between 0 and 100 MB");
        }

        if (requestedThreadCount < 0 || requestedThreadCount > 10) {
            throw new IllegalArgumentException(
                    "Thread count must be between 0 and 10");
        }

        disable();

        delayMillis = requestedDelayMillis;
        errorPercent = requestedErrorPercent;
        cpuMillis = requestedCpuMillis;

        try {
            if ("JVM_MEMORY".equals(normalized)) {
                if (requestedMemoryMb < 1) {
                    throw new IllegalArgumentException(
                            "memoryMb must be at least 1 for JVM_MEMORY");
                }

                int blockSize = 1024 * 1024;
                byte[][] blocks = new byte[requestedMemoryMb][];

                for (int i = 0; i < requestedMemoryMb; i++) {
                    blocks[i] = new byte[blockSize];

                    // Touch each page so the allocation is backed by memory.
                    for (int j = 0; j < blockSize; j += 4096) {
                        blocks[i][j] = 1;
                    }
                }

                memoryBlocks = blocks;
            }

            if ("THREAD_COUNT".equals(normalized)) {
                if (requestedThreadCount < 1) {
                    throw new IllegalArgumentException(
                            "threadCount must be at least 1 for THREAD_COUNT");
                }

                ExecutorService executor =
                        Executors.newFixedThreadPool(requestedThreadCount);

                List<Thread> threads = new ArrayList<>();

                for (int i = 0; i < requestedThreadCount; i++) {
                    Thread worker = new Thread(() -> {
                        try {
                            while (!Thread.currentThread().isInterrupted()) {
                                Thread.sleep(1000);
                            }
                        } catch (InterruptedException e) {
                            Thread.currentThread().interrupt();
                        }
                    }, "fault-worker-" + i);

                    worker.setDaemon(true);
                    threads.add(worker);
                    worker.start();
                }

                threadExecutor = executor;
                workerThreads = threads;
            }

            expiresAt = Instant.now().plusSeconds(durationSeconds);
            type = normalized;

        } catch (RuntimeException e) {
            cleanupResources();
            type = "NONE";
            expiresAt = Instant.EPOCH;
            throw e;
        }
    }

    public synchronized void disable() {
        type = "NONE";
        expiresAt = Instant.EPOCH;
        cleanupResources();
    }

    private synchronized void cleanupResources() {
        memoryBlocks = new byte[0][];

        List<Thread> threads = workerThreads;
        workerThreads = new ArrayList<>();

        for (Thread worker : threads) {
            worker.interrupt();
        }

        ExecutorService executor = threadExecutor;
        threadExecutor = null;

        if (executor != null) {
            executor.shutdownNow();
        }
    }

    @PreDestroy
    public void shutdown() {
        disable();
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
                    cleanupResources();
                }
            }

            return false;
        }

        return !"NONE".equals(type);
    }

    public void applyFault(HttpServletResponse response)
            throws IOException {

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
            long end = System.nanoTime()
                    + cpuMillis * 1_000_000L;

            while (System.nanoTime() < end) {
                Math.sqrt(ThreadLocalRandom.current().nextDouble());
            }
        }
    }
}
