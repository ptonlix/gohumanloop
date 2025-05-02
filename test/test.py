import json

a = json.dumps({
    "function_name": "human_review",
    "function_signature": ["state", "approval_data", "messages", "last_message", "review_message"],
    "arguments": {
        "messages": [
            {
                "type": "SystemMessage",
                "content": "你是一位专业的金融顾问助手，负责帮助用户处理金融交易请求。\n你的职责包括：\n1. 理解用户的金融交易需求\n2. 提供专业的金融建议\n3. 协助用户完成交易流程\n4. 确保交易安全和合规\n\n请根据用户的请求，提供清晰的交易建议和操作方案。你的回复将由人工审核后再执行。\n",
                "additional_kwargs": {},
                "response_metadata": {}
            },
            {
                "type": "HumanMessage",
                "content": "我想投资5万元购买一些低风险的基金产品，主要用于退休储蓄，期限大约10年。请给我一些建议？",
                "additional_kwargs": {},
                "response_metadata": {}
            },
            {
                "type": "AIMessage",
                "content": "尊敬的客户，感谢您的投资咨询。针对您5万元的低风险基金投资需求，我为您提供以下专业建议：\n\n1. 交易类型和金额确认\n- 交易类型：开放式基金申购\n- 金额确认：50,000元人民币\n- 投资期限：约10年\n- 投资目标：退休储蓄\n\n2. 交易风险评估\n- 风险等级：R2(中低风险)\n- 适合产品类型：债券型基金、货币市场基金、平衡型基金\n- 波动性评估：预计年化波动率3-6%\n- 最大回撤评估：预计不超过10%\n\n3. 执行建议和注意事项\n\n推荐配置方案：\na) 40%配置于优质债券型基金(年化预期收益3-5%)\nb) 30%配置于平衡型基金(年化预期收益4-7%)\nc) 30%配置于货币市场基金(保持流动性)\n\n注意事项：\n1) 建议选择大型基金公司的产品，关注3年以上稳定业绩\n2) 推荐采用定期定额投资方式降低择时风险\n3) 每年至少进行一次投资组合再平衡\n4) 关注基金费用率，控制在1.2%以下\n5) 保留3-6个月的生活费作为应急资金\n\n4. 是否建议执行此交易：是\n\n理由：\n1) 符合您的风险偏好和投资目标\n2) 10年期限足够平滑市场波动\n3) 基金组合方式能较好平衡收益与风险\n4) 当前市场环境下债券类资产具有配置价值\n5) 退休储蓄需要稳健增长的投资方式\n\n建议后续步骤：\n1) 完成风险测评问卷确认风险承受能力\n2) 提供具体基金产品推荐清单供选择\n3) 签署相关投资协议文件\n4) 建立定期检视机制\n\n请注意，以上建议仅供参考，具体投资决策需结合您的完整财务状况。市场有风险，投资需谨慎。",
                "additional_kwargs": {"refusal": None},
                "response_metadata": {
                    "token_usage": {
                        "completion_tokens": 411,
                        "prompt_tokens": 175,
                        "total_tokens": 586,
                        "completion_tokens_details": None,
                        "prompt_tokens_details": {
                            "audio_tokens": None,
                            "cached_tokens": 128
                        },
                        "prompt_cache_hit_tokens": 128,
                        "prompt_cache_miss_tokens": 47
                    },
                    "model_name": "deepseek-chat",
                    "system_fingerprint": "fp_8802369eaa_prod0425fp8",
                    "id": "b7915cbf-7f24-4791-bac3-1819023bb6e6",
                    "finish_reason": "stop",
                    "logprobs": None
                },
                "id": "run-13e19865-afeb-4db3-97d6-036457332b54-0",
                "usage_metadata": {
                    "input_tokens": 175,
                    "output_tokens": 411,
                    "total_tokens": 586,
                    "input_token_details": {"cache_read": 128},
                    "output_token_details": {}
                }
            }
        ],
        "next": "human_review"
    },
    "keyword_arguments": {},
    "documentation": "人工审核节点"
}, indent=2, ensure_ascii=False)
print(a)