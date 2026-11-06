"""注册模板合同测试使用的 pytest 标记，避免专项回归产生无效告警。"""


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "main_flow: 模板主流程标记")
    config.addinivalue_line("markers", "branch_flow: 模板分支流程标记")
    config.addinivalue_line("markers", "preconditions(rules): 模板前置数据规则标记")
    config.addinivalue_line("markers", "cleanup(rules): 模板清理规则标记")
