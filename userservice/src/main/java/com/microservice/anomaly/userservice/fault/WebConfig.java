
package com.microservice.anomaly.userservice.fault;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.*;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    private final FaultInjectionInterceptor interceptor;

    public WebConfig(FaultInjectionInterceptor interceptor) {
        this.interceptor = interceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(interceptor)
                .addPathPatterns("/**")
                .excludePathPatterns(
                        "/faults/**",
                        "/actuator/**",
                        "/error");
    }
}
