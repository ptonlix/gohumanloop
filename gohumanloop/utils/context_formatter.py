from typing import Dict, Any
import json


class ContextFormatter:
    """上下文格式化工具"""

    @staticmethod
    def format_for_human(context: Dict[str, Any]) -> str:
        """将上下文格式化为人类可读的文本"""
        result = []

        # 添加标题（如果有）
        if "title" in context:
            result.append(f"# {context['title']}\n")

        # 添加描述（如果有）
        if "description" in context:
            result.append(f"{context['description']}\n")

        # 添加任务信息
        if "task" in context:
            result.append(f"## 任务\n{context['task']}\n")

        # 添加代理信息
        if "agent" in context:
            result.append(f"## 代理\n{context['agent']}\n")

        # 添加操作信息
        if "action" in context:
            result.append(f"## 请求的操作\n{context['action']}\n")

        # 添加原因
        if "reason" in context:
            result.append(f"## 原因\n{context['reason']}\n")

        # 添加其他键值对
        other_keys = [
            k
            for k in context.keys()
            if k not in ["title", "description", "task", "agent", "action", "reason"]
        ]
        if other_keys:
            result.append("## 附加信息\n")
            for key in other_keys:
                value = context[key]
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, indent=2)
                result.append(f"### {key}\n```\n{value}\n```\n")

        return "\n".join(result)

    @staticmethod
    def format_for_api(context: Dict[str, Any]) -> Dict[str, Any]:
        """将上下文格式化为API友好的格式"""
        # 复制上下文以避免修改原始数据
        formatted = context.copy()

        # 确保所有值都是可序列化的
        for key, value in formatted.items():
            if not isinstance(value, (str, int, float, bool, list, dict, type(None))):
                formatted[key] = str(value)

        return formatted
