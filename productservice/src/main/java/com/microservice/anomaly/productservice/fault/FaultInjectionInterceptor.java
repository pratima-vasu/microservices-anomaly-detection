package com.microservice.anomaly.productservice.fault;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

@Component
public class FaultInjectionInterceptor implements HandlerInterceptor {

    private final FaultInjectionService faultService;

    public FaultInjectionInterceptor(FaultInjectionService faultService) {
        this.faultService = faultService;
    }

    @Override
    public boolean preHandle(
            HttpServletRequest request,
            HttpServletResponse response,
            Object handler) throws Exception {

        faultService.applyFault(response);

        return response.getStatus() < 400
                && !response.isCommitted();
    }
}
