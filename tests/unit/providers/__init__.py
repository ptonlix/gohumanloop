"""
## 提供者模块测试 (providers) 

tests/unit/providers/test_base.py
- 测试 BaseProvider 类的初始化
- 测试请求ID生成功能
- 测试请求存储功能
- 测试请求状态更新功能
- 测试超时任务创建功能
- 测试取消请求功能
- 测试取消对话功能 

tests/unit/providers/test_api_provider.py
- 测试 APIProvider 类的初始化
- 测试API请求发送功能
- 测试请求人机循环功能
- 测试检查请求状态功能
- 测试继续人机循环功能
- 测试轮询任务功能
- 测试错误处理功能
- 测试重试机制 

tests/unit/providers/test_email_provider.py
- 测试 EmailProvider 类的初始化
- 测试邮件发送功能
- 测试邮件检查功能
- 测试请求人机循环功能
- 测试邮件内容解析功能
- 测试多语言模板功能
- 测试邮件回复处理功能 

tests/unit/providers/test_terminal_provider.py
- 测试 TerminalProvider 类的初始化
- 测试终端交互功能
- 测试请求人机循环功能
- 测试终端输入处理功能
- 测试终端输出格式化功能 

tests/unit/providers/test_ghl_provider.py
- 测试 GoHumanLoopProvider 类的初始化
- 测试环境变量配置功能
- 测试与 GoHumanLoop 平台的连接功能
"""