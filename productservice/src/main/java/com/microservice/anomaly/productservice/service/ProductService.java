package com.microservice.anomaly.productservice.service;

import java.util.List;

import org.springframework.stereotype.Service;

import com.microservice.anomaly.productservice.entity.Product;
import com.microservice.anomaly.productservice.repository.ProductRepository;

@Service
public class ProductService {
    private final ProductRepository productRepository;

    public ProductService(ProductRepository productRepository) {
        this.productRepository = productRepository;
    }

    public List<Product> getAllProducts() {
        return productRepository.findAll();
    }

    public Product getProductById(Long id) {
        return productRepository.findById(id).orElse(null);
    }

    public Product saveProduct(Product product) {
        return productRepository.save(product);
    }

    public void deleteProduct(Long id) {
        productRepository.deleteById(id);
    }

	public Product reduceStock(Long id, int quantity) {
		Product product = productRepository.findById(id)
	            .orElseThrow(() -> new RuntimeException("Product not found"));

	    product.setQuantity(product.getQuantity() - quantity);

	    return productRepository.save(product);
	}

}
