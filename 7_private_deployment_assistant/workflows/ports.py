"""业务依赖合同；具体实现位于 services，测试时可注入替代实现。"""

from typing import Protocol


class RemoteDiagnostics(Protocol):
    def collect(self, connection_id: str, thread_id: str, checks: list[dict]) -> list[dict]:
        """以不含凭据的连接引用执行已授权检查，返回脱敏证据。"""
        ...


class ResolutionVerifier(Protocol):
    def verify(self, thread_id: str, proposal: dict, verification: dict) -> dict:
        """按原故障的功能验收条件返回 verified、evidence 和遗留事项。"""
        ...


class KnowledgePublisher(Protocol):
    def publish(self, thread_id: str, record: dict) -> dict:
        """仅对已验证案例查重、写本地文档、建立可重试的入库任务。"""
        ...
