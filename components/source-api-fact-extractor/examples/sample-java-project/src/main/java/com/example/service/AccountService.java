package com.example.service;

import com.example.dto.CreateAccountRequest;
import com.example.domain.AccountStatus;
import com.example.exception.BusinessException;
import com.example.exception.ErrorCode;
import com.example.mapper.AccountMapper;
import com.example.validator.AccountValidator;
import com.example.vo.AccountResponse;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AccountService {
    private final AccountValidator accountValidator;
    private final AccountMapper accountMapper;

    public AccountService(AccountValidator accountValidator, AccountMapper accountMapper) {
        this.accountValidator = accountValidator;
        this.accountMapper = accountMapper;
    }

    @Transactional
    public AccountResponse createAccount(CreateAccountRequest request) {
        accountValidator.validateCreate(request);
        if (accountMapper.existsByUserId(request.getUserId())) {
            throw new BusinessException(ErrorCode.ACCOUNT_EXISTS);
        }
        accountMapper.insertAccount(request);
        return accountMapper.selectByUserId(request.getUserId());
    }

    public AccountResponse getAccount(Long accountId) {
        AccountResponse account = accountMapper.selectById(accountId);
        if (account == null) {
            throw new BusinessException(ErrorCode.ACCOUNT_NOT_FOUND);
        }
        if (account.getStatus() == AccountStatus.FROZEN) {
            throw new BusinessException(ErrorCode.ACCOUNT_FROZEN);
        }
        return account;
    }
}
