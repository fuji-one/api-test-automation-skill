from __future__ import annotations


def create_api(facts):
    return next(api for api in facts["apis"] if api["entry"]["method_name"] == "create")


def get_api(facts):
    return next(api for api in facts["apis"] if api["entry"]["method_name"] == "get")


def test_db_side_effects_detect_mapper_insert(facts):
    effects = create_api(facts)["db_side_effects"]
    assert any(effect["operation_type"] == "CREATE" for effect in effects)
    assert any(effect["tables"] == "account" for effect in effects)
    assert any(effect["side_effect_level"] == "CONFIRMED" for effect in effects)


def test_db_side_effects_detect_mapper_select(facts):
    effects = get_api(facts)["db_side_effects"]
    assert any(effect["operation_type"] == "READ" for effect in effects)
    assert any(effect["sql_operation"] == "select" for effect in effects)
    assert any(effect["side_effect_level"] == "NONE" for effect in effects)


def test_db_side_effects_resolve_repository_impl_mapper_entity_table(tmp_path):
    from scan_source import scan

    write_file(
        tmp_path / "src/main/java/com/example/controller/OrderController.java",
        """
package com.example.controller;

import com.example.service.OrderService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderController {
    private final OrderService orderService;

    public OrderController(OrderService orderService) {
        this.orderService = orderService;
    }

    @PostMapping("/orders")
    public Long create() {
        return orderService.create();
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/service/OrderService.java",
        """
package com.example.service;

import com.example.domain.OrderRepository;
import org.springframework.stereotype.Service;

@Service
public class OrderService {
    private final OrderRepository orderRepository;

    public OrderService(OrderRepository orderRepository) {
        this.orderRepository = orderRepository;
    }

    public Long create() {
        return orderRepository.insert();
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/domain/OrderRepository.java",
        """
package com.example.domain;

public interface OrderRepository {
    Long insert();
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/infra/OrderRepositoryImpl.java",
        """
package com.example.infra;

import com.example.domain.OrderRepository;
import com.example.mapper.OrderMapper;
import org.springframework.stereotype.Repository;

@Repository
public class OrderRepositoryImpl implements OrderRepository {
    private final OrderMapper mapper;

    public OrderRepositoryImpl(OrderMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public Long insert() {
        OrderDO order = new OrderDO();
        mapper.insert(order);
        return order.getId();
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/mapper/OrderMapper.java",
        """
package com.example.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.infra.OrderDO;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OrderMapper extends BaseMapper<OrderDO> {
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/infra/OrderDO.java",
        """
package com.example.infra;

import com.baomidou.mybatisplus.annotation.TableName;

@TableName("orders")
public class OrderDO {
    private Long id;

    public Long getId() {
        return id;
    }
}
""",
    )

    facts = scan(tmp_path, tmp_path / "out")
    api = next(item for item in facts["apis"] if item["entry"]["path"] == "/orders")
    effects = api["db_side_effects"]

    assert any(effect["operation_type"] == "CREATE" for effect in effects)
    assert any(effect["tables"] == "orders" for effect in effects)
    assert any(effect["entity_or_do"] == "OrderDO" for effect in effects)
    assert any(effect["side_effect_level"] == "CONFIRMED" for effect in effects)
    assert all(effect["evidence"] != "UNKNOWN" for effect in effects)


def test_db_side_effects_trace_same_class_private_overload_and_helper(tmp_path):
    from scan_source import scan

    write_file(
        tmp_path / "src/main/java/com/example/controller/VerifyController.java",
        """
package com.example.controller;

import com.example.dto.VerifyReq;
import com.example.service.VerifyService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class VerifyController {
    private final VerifyService verifyService;

    public VerifyController(VerifyService verifyService) {
        this.verifyService = verifyService;
    }

    @PostMapping("/verify")
    public Boolean verify(@RequestBody VerifyReq req) {
        return verifyService.verify(req);
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/dto/VerifyReq.java",
        """
package com.example.dto;

public class VerifyReq {
    private Long orderId;
    private String token;

    public Long getOrderId() {
        return orderId;
    }

    public String getToken() {
        return token;
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/service/VerifyService.java",
        """
package com.example.service;

import com.example.domain.Detail;
import com.example.domain.DetailRepository;
import com.example.domain.Order;
import com.example.domain.OrderRepository;
import com.example.dto.VerifyReq;
import org.springframework.stereotype.Service;

@Service
public class VerifyService {
    private final OrderRepository orderRepository;
    private final DetailRepository detailRepository;

    public VerifyService(OrderRepository orderRepository, DetailRepository detailRepository) {
        this.orderRepository = orderRepository;
        this.detailRepository = detailRepository;
    }

    public Boolean verify(VerifyReq req) {
        return verify(req.getOrderId(), req.getToken());
    }

    private Boolean verify(Long orderId, String token) {
        Order order = orderRepository.findById(orderId);
        order.verify(token);
        orderRepository.update(order);
        saveDetail(orderId);
        return true;
    }

    private void saveDetail(Long orderId) {
        Detail detail = Detail.create(orderId);
        detailRepository.insert(detail);
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/domain/OrderRepository.java",
        """
package com.example.domain;

public interface OrderRepository {
    Order findById(Long id);
    void update(Order order);
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/domain/DetailRepository.java",
        """
package com.example.domain;

public interface DetailRepository {
    void insert(Detail detail);
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/domain/Order.java",
        """
package com.example.domain;

public class Order {
    public void verify(String token) {
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/domain/Detail.java",
        """
package com.example.domain;

public class Detail {
    public static Detail create(Long orderId) {
        return new Detail();
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/infra/OrderRepositoryImpl.java",
        """
package com.example.infra;

import com.example.domain.Order;
import com.example.domain.OrderRepository;
import com.example.mapper.OrderMapper;
import org.springframework.stereotype.Repository;

@Repository
public class OrderRepositoryImpl implements OrderRepository {
    private final OrderMapper orderMapper;

    public OrderRepositoryImpl(OrderMapper orderMapper) {
        this.orderMapper = orderMapper;
    }

    public Order findById(Long id) {
        orderMapper.selectById(id);
        return new Order();
    }

    public void update(Order order) {
        orderMapper.updateById(new OrderDO());
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/infra/DetailRepositoryImpl.java",
        """
package com.example.infra;

import com.example.domain.Detail;
import com.example.domain.DetailRepository;
import com.example.mapper.DetailMapper;
import org.springframework.stereotype.Repository;

@Repository
public class DetailRepositoryImpl implements DetailRepository {
    private final DetailMapper detailMapper;

    public DetailRepositoryImpl(DetailMapper detailMapper) {
        this.detailMapper = detailMapper;
    }

    public void insert(Detail detail) {
        detailMapper.insert(new DetailDO());
    }
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/mapper/OrderMapper.java",
        """
package com.example.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.infra.OrderDO;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface OrderMapper extends BaseMapper<OrderDO> {
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/mapper/DetailMapper.java",
        """
package com.example.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.example.infra.DetailDO;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface DetailMapper extends BaseMapper<DetailDO> {
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/infra/OrderDO.java",
        """
package com.example.infra;

import com.baomidou.mybatisplus.annotation.TableName;

@TableName("orders")
public class OrderDO {
}
""",
    )
    write_file(
        tmp_path / "src/main/java/com/example/infra/DetailDO.java",
        """
package com.example.infra;

import com.baomidou.mybatisplus.annotation.TableName;

@TableName("order_detail")
public class DetailDO {
}
""",
    )

    facts = scan(tmp_path, tmp_path / "out")
    api = next(item for item in facts["apis"] if item["entry"]["path"] == "/verify")
    effects = api["db_side_effects"]

    assert any(effect["operation_type"] == "READ" and effect["tables"] == "orders" for effect in effects)
    assert any(effect["operation_type"] == "UPDATE" and effect["tables"] == "orders" for effect in effects)
    assert any(effect["operation_type"] == "CREATE" and effect["tables"] == "order_detail" for effect in effects)
    assert any(call["class_name"] == "VerifyService" and call["method_name"] == "saveDetail" for call in api["call_chain"])


def write_file(path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip(), encoding="utf-8")
