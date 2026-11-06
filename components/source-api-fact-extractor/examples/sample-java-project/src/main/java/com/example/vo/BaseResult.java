package com.example.vo;

public class BaseResult<T> {
    private int code;
    private String message;
    private T data;

    public static <T> BaseResult<T> success(T data) {
        return new BaseResult<>();
    }
}
