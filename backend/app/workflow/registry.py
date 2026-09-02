from collections.abc import Callable

from app.agents.base import BaseAgent

WorkflowAgentFactory = Callable[[int], BaseAgent]


class WorkflowAgentRegistrationError(ValueError):
    """节点 Agent 注册重复或无效。"""


class WorkflowAgentNotFoundError(LookupError):
    """工作流节点没有可执行 Agent。"""


class WorkflowAgentRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, WorkflowAgentFactory] = {}

    @property
    def registered_types(self) -> frozenset[str]:
        return frozenset(self._factories)

    def register(self, node_type: str, factory: WorkflowAgentFactory) -> None:
        normalized = node_type.strip()
        if not normalized or normalized in self._factories:
            raise WorkflowAgentRegistrationError("节点 Agent 类型无效或重复")
        self._factories[normalized] = factory

    def create(self, node_type: str, *, max_tokens: int) -> BaseAgent:
        factory = self._factories.get(node_type)
        if factory is None:
            raise WorkflowAgentNotFoundError(f"未注册节点类型 {node_type}")
        if max_tokens < 1:
            raise ValueError("节点 max_tokens 必须大于 0")
        agent = factory(max_tokens)
        if agent.agent_type != node_type:
            raise WorkflowAgentRegistrationError("节点 Agent 类型与注册键不一致")
        return agent
