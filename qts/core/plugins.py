from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator, TypeVar

import pluggy

hookspec = pluggy.HookspecMarker("qts")
hookimpl = pluggy.HookimplMarker("qts")

if TYPE_CHECKING:
    from .factor.base import FactorAdapter
    from .optimize.optimizers.base import OptimizerAdapter
    from .portfolio.allocators.base import AllocatorAdapter
    from .strategy.base import StrategyAdapter


class QTSPluginSpec:
    """QTS 核心扩展点定义。"""

    @hookspec
    def qts_register_factors(self) -> list[object]:
        """返回因子实现列表。"""

    @hookspec
    def qts_register_strategies(self) -> list[object]:
        """返回策略构建器列表。"""

    @hookspec
    def qts_register_optimizers(self, capped_cap: float) -> list[object]:
        """返回优化器实现列表。"""

    @hookspec
    def qts_register_allocators(self) -> list[object]:
        """返回资金分配器实现列表。"""


AdapterT = TypeVar("AdapterT")


@dataclass
class PluginRuntime:
    manager: pluggy.PluginManager

    @classmethod
    def build(cls, *, load_entrypoints: bool = False, entrypoint_group: str = "qts") -> "PluginRuntime":
        manager = pluggy.PluginManager("qts")
        manager.add_hookspecs(QTSPluginSpec)

        from .builtin_plugins import BuiltinQTSPlugin

        manager.register(BuiltinQTSPlugin(), name="qts-builtin")
        if load_entrypoints:
            manager.load_setuptools_entrypoints(entrypoint_group)
        return cls(manager=manager)


_DEFAULT_RUNTIME = PluginRuntime.build()
_ACTIVE_RUNTIME: ContextVar[PluginRuntime] = ContextVar("qts_active_plugin_runtime", default=_DEFAULT_RUNTIME)


def get_plugin_manager() -> pluggy.PluginManager:
    """返回全局插件管理器。"""
    return _ACTIVE_RUNTIME.get().manager


def build_plugin_runtime(*, load_entrypoints: bool = False, entrypoint_group: str = "qts") -> PluginRuntime:
    """构建一个隔离的插件运行时。"""
    return PluginRuntime.build(load_entrypoints=load_entrypoints, entrypoint_group=entrypoint_group)


@contextmanager
def activate_plugin_runtime(runtime: PluginRuntime) -> Iterator[PluginRuntime]:
    """在当前上下文中临时激活指定插件运行时。"""
    token: Token[PluginRuntime] = _ACTIVE_RUNTIME.set(runtime)
    try:
        yield runtime
    finally:
        _ACTIVE_RUNTIME.reset(token)


@contextmanager
def plugin_context(
    plugins: list[tuple[object, str | None]] | None = None,
    *,
    load_entrypoints: bool = False,
    entrypoint_group: str = "qts",
) -> Iterator[PluginRuntime]:
    """创建并激活一个隔离的插件上下文。"""
    runtime = build_plugin_runtime(load_entrypoints=load_entrypoints, entrypoint_group=entrypoint_group)
    if plugins:
        for plugin, name in plugins:
            runtime.manager.register(plugin, name=name)
    with activate_plugin_runtime(runtime):
        yield runtime


def _current_runtime() -> PluginRuntime:
    return _ACTIVE_RUNTIME.get()


def register_plugin(plugin: object, *, name: str | None = None) -> str | None:
    """在当前隔离插件上下文中注册一个插件对象。"""
    runtime = _current_runtime()
    if runtime is _DEFAULT_RUNTIME:
        raise RuntimeError("默认插件运行时不可变；请使用 plugin_context 或 activate_plugin_runtime")
    return runtime.manager.register(plugin, name=name)


def unregister_plugin(plugin: object | None = None, *, name: str | None = None) -> object | None:
    """在当前隔离插件上下文中按对象或名称注销插件。"""
    runtime = _current_runtime()
    if runtime is _DEFAULT_RUNTIME:
        raise RuntimeError("默认插件运行时不可变；请使用 plugin_context 或 activate_plugin_runtime")
    manager = runtime.manager
    if name is not None:
        target = manager.get_plugin(name)
        if target is None:
            return None
        manager.unregister(target)
        return target
    if plugin is None:
        raise ValueError("plugin 和 name 至少需要提供一个")
    manager.unregister(plugin)
    return plugin


def _flatten_named(items: list[list[AdapterT] | None]) -> dict[str, AdapterT]:
    named: dict[str, AdapterT] = {}
    for group in items:
        if not group:
            continue
        for item in group:
            name = getattr(item, "name", None)
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"插件返回了无效名称: {item!r}")
            normalized = name.strip()
            if normalized in named:
                raise ValueError(f"检测到重复插件名称: {normalized}")
            named[normalized] = item
    return named


def _collect_typed(
    items: list[list[AdapterT] | None],
    *,
    expected_type: type[AdapterT],
    kind_label: str,
    attr_name: str,
) -> dict[str, AdapterT]:
    typed_groups: list[list[AdapterT] | None] = []
    for group in items:
        if not group:
            typed_groups.append(group)
            continue
        typed_group: list[AdapterT] = []
        for item in group:
            if not isinstance(item, expected_type):
                raise TypeError(f"{kind_label} 插件返回了错误类型 type={type(item).__name__}")
            typed_group.append(item)
        typed_groups.append(typed_group)
    named = _flatten_named(typed_groups)
    for name, item in named.items():
        attr = getattr(item, attr_name, None)
        if not callable(attr):
            raise TypeError(f"{kind_label} 插件缺少可调用属性 name={name} attr={attr_name}")
    return named


def collect_factor_adapters() -> dict[str, FactorAdapter]:
    """收集当前所有因子实现。"""
    from .factor.base import FactorAdapter

    return _collect_typed(
        get_plugin_manager().hook.qts_register_factors(),
        expected_type=FactorAdapter,
        kind_label="factor",
        attr_name="run",
    )


def collect_strategy_adapters() -> dict[str, StrategyAdapter]:
    """收集当前所有策略实现。"""
    from .strategy.base import StrategyAdapter

    return _collect_typed(
        get_plugin_manager().hook.qts_register_strategies(),
        expected_type=StrategyAdapter,
        kind_label="strategy",
        attr_name="build",
    )


def collect_optimizer_adapters(*, capped_cap: float) -> dict[str, OptimizerAdapter]:
    """收集当前所有优化器实现。"""
    from .optimize.optimizers.base import OptimizerAdapter

    return _collect_typed(
        get_plugin_manager().hook.qts_register_optimizers(capped_cap=capped_cap),
        expected_type=OptimizerAdapter,
        kind_label="optimizer",
        attr_name="run",
    )


def collect_allocator_adapters() -> dict[str, AllocatorAdapter]:
    """收集当前所有资金分配器实现。"""
    from .portfolio.allocators.base import AllocatorAdapter

    return _collect_typed(
        get_plugin_manager().hook.qts_register_allocators(),
        expected_type=AllocatorAdapter,
        kind_label="allocator",
        attr_name="run",
    )
