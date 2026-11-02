package com.microservice.anomaly.userservice.repository;

import org.springframework.stereotype.Repository;

import com.microservice.anomaly.userservice.entity.User;

import org.springframework.data.jpa.repository.JpaRepository;

@Repository
public interface UserRepository extends JpaRepository<User, Long>{

}
