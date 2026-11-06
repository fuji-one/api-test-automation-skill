package com.example.dto;

import com.example.domain.AccountStatus;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.math.BigDecimal;

public class CreateAccountRequest {
    @NotNull(message = "userId is required")
    private Long userId;

    @NotBlank(message = "accountName is required")
    private String accountName;

    @NotNull(message = "status is required")
    private AccountStatus status;

    @DecimalMin(value = "0.00", message = "initialBalance must not be negative")
    private BigDecimal initialBalance;

    public Long getUserId() {
        return userId;
    }

    public String getAccountName() {
        return accountName;
    }

    public AccountStatus getStatus() {
        return status;
    }

    public BigDecimal getInitialBalance() {
        return initialBalance;
    }
}
