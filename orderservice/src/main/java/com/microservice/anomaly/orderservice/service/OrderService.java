package com.microservice.anomaly.orderservice.service;

import java.util.List;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import com.microservice.anomaly.orderservice.dto.ProductResponse;
import com.microservice.anomaly.orderservice.dto.UserResponse;
import com.microservice.anomaly.orderservice.entity.Order;
import com.microservice.anomaly.orderservice.exception.InsufficientStockException;
import com.microservice.anomaly.orderservice.exception.ProductNotFoundException;
import com.microservice.anomaly.orderservice.exception.UserNotFoundException;
import com.microservice.anomaly.orderservice.repository.OrderRepository;


@Service
public class OrderService {

    private final OrderRepository orderRepository;
    private final RestClient restClient;
    private final String userServiceBaseUrl;
    private final String productServiceBaseUrl;

    public OrderService(OrderRepository orderRepository, RestClient restClient,
            @Value("${services.user.base-url:http://localhost:8082}") String userServiceBaseUrl,
            @Value("${services.product.base-url:http://localhost:8083}") String productServiceBaseUrl) {
        this.orderRepository = orderRepository;
		this.restClient = restClient;
        this.userServiceBaseUrl = userServiceBaseUrl;
        this.productServiceBaseUrl = productServiceBaseUrl;
    }

    public List<Order> getAllOrders() {
        return orderRepository.findAll();
    }

    public Order getOrderById(Long id) {
        return orderRepository.findById(id).orElse(null);
    }

	public Order saveOrder(Order order) {
		// Validate order quantity
	    if (order.getQuantity() <= 0) {
	        throw new IllegalArgumentException("Quantity must be greater than 0");
	    }
		// Check if user exists
	    UserResponse user;

	    try {
	        user = getUser(order.getUserId());
	    } catch (Exception e) {
	        throw new UserNotFoundException(
	                "User not found with id: " + order.getUserId());
	    }

	    if (user == null) {
	        throw new UserNotFoundException(
	                "User not found with id: " + order.getUserId());
	    }
		// Get product details
	    ProductResponse product;

	    try {
	        product = getProduct(order.getProductId());
	    } catch (Exception e) {
	        throw new ProductNotFoundException(
	                "Product not found with id: " + order.getProductId());
	    }

	    if (product == null) {
	        throw new ProductNotFoundException(
	                "Product not found with id: " + order.getProductId());
	    }

	    // Check available quantity
	    if (order.getQuantity() > product.getQuantity()) {
	        throw new InsufficientStockException(
	                "Insufficient product quantity. Available quantity: "
	                        + product.getQuantity());
	    }


		// Calculate total amount
		double totalAmount = product.getPrice() * order.getQuantity();

		order.setTotalAmount(totalAmount);
		order.setStatus("CREATED");
		
		// Deduct product quantity
	    restClient.put()
	            .uri(productServiceBaseUrl + "/products/"
	                    + order.getProductId()
	                    + "/reduce-stock?quantity="
	                    + order.getQuantity())
	            .retrieve()
	            .body(ProductResponse.class);

		return orderRepository.save(order);
	}

    public void deleteOrder(Long id) {
        orderRepository.deleteById(id);
    }
    public UserResponse getUser(Long userId) {

        return restClient.get()
                .uri(userServiceBaseUrl + "/users/" + userId)
                .retrieve()
                .body(UserResponse.class);
    }
    public ProductResponse getProduct(Long productId) {

        return restClient.get()
                .uri(productServiceBaseUrl + "/products/" + productId)
                .retrieve()
                .body(ProductResponse.class);
    }

    public List<Order> getOrdersByUserId(Long userId) {
        return orderRepository.findByUserId(userId);
    }
}