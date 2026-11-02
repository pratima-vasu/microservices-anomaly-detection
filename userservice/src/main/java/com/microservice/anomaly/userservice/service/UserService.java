package com.microservice.anomaly.userservice.service;

import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.client.RestClient;

import com.microservice.anomaly.userservice.dto.OrderResponse;
import com.microservice.anomaly.userservice.entity.User;
import com.microservice.anomaly.userservice.repository.UserRepository;

@Service
public class UserService {
	
	private final UserRepository userRepository;
	private final RestClient restClient;
    private final String orderServiceBaseUrl;

	public UserService(RestClient restClient, UserRepository userRepository,
            @Value("${services.order.base-url:http://localhost:8084}") String orderServiceBaseUrl) {
		this.restClient = restClient;
		this.userRepository = userRepository;
        this.orderServiceBaseUrl = orderServiceBaseUrl;
	}
	 public List<User> getAllUsers() {
		 return userRepository.findAll();
	 }
	 
	 public User getUserById(@PathVariable Long id) {
		 return userRepository.findById(id).orElse(null);
	 }
	 
	 public User createUser(@RequestBody User user) {
		 return userRepository.save(user);
	 }
	 
	 public List<OrderResponse> getOrdersByUserId(Long userId) {

		    return restClient.get()
		            .uri(orderServiceBaseUrl + "/orders/user/" + userId)
		            .retrieve()
		            .body(new ParameterizedTypeReference<List<OrderResponse>>() {});
		}
}
