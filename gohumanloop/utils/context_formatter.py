import inspect
from typing import Callable, Any, Dict, Union, cast


def _param_detail_zh(p: inspect.Parameter) -> str:
    return (
        f"    {p.name}: "
        + (f"类型[{p.annotation}] " if p.annotation != p.empty else "")
        + (f"(默认值={p.default})" if p.default != p.empty else "")
    )


def _param_detail_en(p: inspect.Parameter) -> str:
    return (
        f"    {p.name}: "
        + (f"Type[{p.annotation}] " if p.annotation != p.empty else "")
        + (f"(default={p.default})" if p.default != p.empty else "")
    )


def generate_function_summary(
    fn: Callable,
    *args: Any,
    language: str = "zh",
    **kwargs: Any,
) -> str:
    """生成支持中英文切换的函数说明模板

    Args:
        fn: 目标函数
        *args: 位置参数示例
        **kwargs: 关键字参数示例
        language: 输出语言 ('zh'/'en')

    Returns:
        纯文本格式的函数说明
    """

    # 定义翻译类型

    # 语言配置
    translations: Dict[
        str, Dict[str, Union[str, Callable[[inspect.Parameter], str]]]
    ] = {
        "zh": {
            "title": "函数说明",
            "name": "函数名称",
            "module": "所属模块",
            "description": "功能描述",
            "params": "参数列表",
            "param_detail": _param_detail_zh,
            "return": "返回值类型",
            "current_input": "当前输入",
            "positional_args": "位置参数",
            "keyword_args": "关键字参数",
            "usage": "调用方式",
            "approval": "审批状态",
            "no_doc": "无文档说明",
        },
        "en": {
            "title": "Function Documentation",
            "name": "Function Name",
            "module": "Module",
            "description": "Description",
            "params": "Parameters",
            "param_detail": _param_detail_en,
            "return": "Return Type",
            "current_input": "Current Input",
            "positional_args": "Positional Args",
            "keyword_args": "Keyword Args",
            "usage": "Usage",
            "approval": "Approval Status",
            "no_doc": "No documentation",
        },
    }

    lang = translations.get(language, translations["zh"])

    # 明确告诉类型检查器这是一个可调用对象
    param_detail_func = cast(Callable[[inspect.Parameter], str], lang["param_detail"])

    # 获取函数信息
    func_name = fn.__name__
    module_obj = inspect.getmodule(fn)
    module = module_obj.__name__ if module_obj is not None else str(lang["no_doc"])
    doc = (fn.__doc__ or str(lang["no_doc"])).strip()
    sig = inspect.signature(fn)

    # 构建模板
    template = (
        f"""
- {lang['title']}: {func_name}
- {lang['name']}: {func_name}
- {lang['module']}: {module}

- {lang['description']}:
{doc}

- {lang['params']}:
"""
        + "\n".join(param_detail_func(p) for p in sig.parameters.values())
        + f"""

- {lang['return']}: {sig.return_annotation if sig.return_annotation != sig.empty else lang['no_doc']}

- {lang['current_input']}:
{lang['positional_args']}: {args}
{lang['keyword_args']}: {kwargs}

- {lang['usage']}: {func_name}(*{args}, **{kwargs})

"""
    )
    return template.strip()


if __name__ == "__main__":
    # 示例函数
    def calculate(a: int, b: float = 1.0) -> float:
        """计算两个数的乘积/Calculate the product of two numbers"""
        return a * b

    # 中文输出
    print("==== 中文版 ====")
    print(generate_function_summary(calculate, 3, b=2.5))

    # 英文输出
    print("\n==== English Version ====")
    print(
        generate_function_summary(
            calculate,
            3,
            language="en",
            b=2.5,
        )
    )
