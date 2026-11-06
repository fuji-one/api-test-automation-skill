package com.example.controller;

import com.example.dto.CreateAccountRequest;
import com.example.service.AccountService;
import com.example.vo.AccountResponse;
import com.example.vo.BaseResult;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/accounts")
public class AccountController {
    private final AccountService accountService;

    public AccountController(AccountService accountService) {
        this.accountService = accountService;
    }

    @PostMapping
    public BaseResult<AccountResponse> create(@Valid @RequestBody CreateAccountRequest request) {
        return BaseResult.success(accountService.createAccount(request));
    }

    @GetMapping("/{accountId}")
    public BaseResult<AccountResponse> get(@PathVariable Long accountId) {
        return BaseResult.success(accountService.getAccount(accountId));
    }
}
