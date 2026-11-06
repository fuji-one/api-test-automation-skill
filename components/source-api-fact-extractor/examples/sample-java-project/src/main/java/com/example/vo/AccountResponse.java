package com.example.vo;

import com.example.domain.AccountStatus;
import java.math.BigDecimal;

public class AccountResponse {
    private Long accountId;
    private Long userId;
    private AccountStatus status;
    private BigDecimal balance;

    public Long getAccountId() {
        return accountId;
    }

    public Long getUserId() {
        return userId;
    }

    public AccountStatus getStatus() {
        return status;
    }

    public BigDecimal getBalance() {
        return balance;
    }
}
