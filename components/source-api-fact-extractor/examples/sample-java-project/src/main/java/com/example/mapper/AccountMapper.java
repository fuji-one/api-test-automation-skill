package com.example.mapper;

import com.example.dto.CreateAccountRequest;
import com.example.vo.AccountResponse;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface AccountMapper {
    boolean existsByUserId(Long userId);

    void insertAccount(CreateAccountRequest request);

    AccountResponse selectByUserId(Long userId);

    AccountResponse selectById(Long accountId);
}
