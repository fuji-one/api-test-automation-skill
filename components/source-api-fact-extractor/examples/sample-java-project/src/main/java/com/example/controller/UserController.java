package com.example.controller;

import com.example.vo.BaseResult;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/users")
public class UserController {
    @GetMapping("/{userId}/profile")
    public BaseResult<MissingUserProfileResponse> profile(@PathVariable Long userId) {
        return BaseResult.success(null);
    }
}
