package com.microservice.anomaly.userservice.controller;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.ResourceAccessException;

import com.microservice.anomaly.userservice.dto.OrderResponse;
import com.microservice.anomaly.userservice.entity.User;
import com.microservice.anomaly.userservice.service.UserService;

@RestController
@RequestMapping("/users")
public class UserController {
	
	private final UserService userService;
	
	public UserController(UserService userService) {
		//super();
		this.userService = userService;
		
	}
	
	 @GetMapping
	 public List<User> getAllUsers() {
		 return userService.getAllUsers();
	 }
	 
	 @GetMapping("/{id}")
	 public User getUserById(@PathVariable Long id) {
		 return userService.getUserById(id);
	 }
	 
	 @PostMapping
	 public User createUser(@RequestBody User user) {
		 return userService.createUser(user);
	 }
	 @GetMapping("/{id}/orders")
	 public List<OrderResponse> getOrdersByUserId(@PathVariable Long id) {
	     return userService.getOrdersByUserId(id);
	 }
	 @ExceptionHandler(ResourceAccessException.class)
	 public ResponseEntity<Map<String, String>> handleOrderServiceUnavailable(
	         ResourceAccessException e) {

	     Map<String, String> response = new HashMap<>();
	     response.put("message", "Order Service is currently unavailable");

	     return ResponseEntity
	             .status(HttpStatus.SERVICE_UNAVAILABLE)
	             .body(response);
	 }
}
