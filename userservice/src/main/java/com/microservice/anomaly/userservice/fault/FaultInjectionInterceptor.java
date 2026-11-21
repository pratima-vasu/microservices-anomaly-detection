
package com.microservice.anomaly.userservice.fault;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

@Component
public class FaultInjectionInterceptor implements HandlerInterceptor {

    private final FaultInjectionService faultService;
    private final CombinedFaultInjectionService combinedFaultService;

    public FaultInjectionInterceptor(FaultInjectionService faultService, CombinedFaultInjectionService combinedFaultService) {
        this.faultService = faultService;
        this.combinedFaultService = combinedFaultService;
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
