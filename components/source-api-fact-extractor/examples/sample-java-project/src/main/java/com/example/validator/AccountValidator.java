package com.example.validator;

import com.example.dto.CreateAccountRequest;
import com.example.exception.BusinessException;
import com.example.exception.ErrorCode;
import java.math.BigDecimal;
import org.springframework.stereotype.Component;

@Component
public class AccountValidator {
    public void validateCreate(CreateAccountRequest request) {
        if (request.getInitialBalance() != null && request.getInitialBalance().compareTo(BigDecimal.ZERO) < 0) {
            throw new BusinessException(ErrorCode.NEGATIVE_BALANCE);
        }
    }
}
