# 智能合约分析工具套件

这个项目实现了四个核心的智能合约数据收集工具，为智能合约行为理解提供全面的分析能力。

## 工具概述

### 1. Source Code Fetcher Tool (源代码获取工具)
- **文件**: `source_code_fetcher.py`
- **功能**: 通过字节码模式分析和实现槽检查来解析代理合约关系
- **特性**:
  - 支持 EIP-1967、EIP-1822、OpenZeppelin 等代理标准
  - 维持时间一致性的历史区块查询
  - 自动检测代理模式和实现地址
  - 批量获取多个合约信息

### 2. Constructor Parameter Tool (构造函数参数工具)
- **文件**: `constructor_parameter_tool.py`  
- **功能**: 分析部署交易calldata重构初始化参数
- **特性**:
  - 自动查找合约创建交易
  - 解码构造函数参数
  - 提供人类可读的参数值格式
  - 支持各种参数类型的智能解析

### 3. State Reader Tool (状态读取工具)
- **文件**: `state_reader_tool.py`
- **功能**: ABI分析识别所有公共和外部view函数，批量获取合约状态
- **特性**:
  - 自动提取所有view/pure函数
  - 批量并发调用状态函数
  - 状态快照对比功能
  - 支持历史区块状态查询

### 4. Code Sanitizer Tool (代码清理工具)
- **文件**: `code_sanitizer_tool.py`
- **功能**: 清理非必要元素如注释、未使用代码和多余库依赖
- **特性**:
  - 智能注释过滤（保留重要注释）
  - 未使用函数和变量检测
  - 调试代码移除
  - 优化影响分析报告

## 主要接口

### SmartContractAnalyzer (智能合约综合分析器)
- **文件**: `smart_contract_analyzer.py`
- **功能**: 整合所有四个工具的主要接口
- **特性**:
  - 一键式全面分析
  - 批量分析多个合约
  - 生成详细分析报告
  - JSON格式结果导出

## 安装和使用

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 基本使用

```python
import asyncio
from smart_contract_analyzer import SmartContractAnalyzer

async def main():
    # 初始化分析器
    analyzer = SmartContractAnalyzer(
        web3_provider="YOUR_WEB3_PROVIDER_URL",
        etherscan_api_key="YOUR_ETHERSCAN_API_KEY"
    )
    
    # 执行全面分析
    contract_address = "0x..."
    analysis = await analyzer.comprehensive_analysis(contract_address)
    
    # 生成报告
    report = analyzer.generate_analysis_report(analysis)
    print(report)
    
    # 导出结果
    analyzer.export_analysis_to_json(analysis, "analysis_result.json")

asyncio.run(main())
```

### 3. 单独使用各个工具

#### 源代码获取
```python
from source_code_fetcher import SourceCodeFetcher

fetcher = SourceCodeFetcher(web3_provider, etherscan_api_key)
contract_info = await fetcher.fetch_contract_info(contract_address)
```

#### 构造函数参数分析
```python
from constructor_parameter_tool import ConstructorParameterTool

tool = ConstructorParameterTool(web3_provider, etherscan_api_key)
deployment_info = await tool.analyze_constructor_params(contract_address)
```

#### 状态读取
```python
from state_reader_tool import StateReaderTool

reader = StateReaderTool(web3_provider, etherscan_api_key)
snapshot = await reader.capture_state_snapshot(contract_address)
```

#### 代码清理
```python
from code_sanitizer_tool import CodeSanitizerTool

sanitizer = CodeSanitizerTool()
result = sanitizer.sanitize_solidity_code(source_code)
```

## 配置要求

### 必需的API密钥
- **Web3 Provider**: Alchemy、Infura或其他以太坊节点提供商
- **Etherscan API Key**: 用于获取合约源代码和ABI

### 环境变量设置
```bash
export WEB3_PROVIDER_URL="https://eth-mainnet.alchemyapi.io/v2/YOUR_API_KEY"
export ETHERSCAN_API_KEY="YOUR_ETHERSCAN_API_KEY"
```

## 输出格式

### 分析报告示例
```
=== 智能合约综合分析报告 ===

合约地址: 0x...
分析时间: 1699123456

=== 基本信息 ===
合约类型: proxy
验证状态: 已验证
有源代码: 是
有ABI: 是

=== 代理信息 ===
代理类型: EIP-1967
实现地址: 0x...
管理员地址: 0x...

=== 部署信息 ===
部署者: 0x...
部署区块: 18500000
Gas使用: 2,500,000
构造参数数量: 3

=== 状态快照 ===
快照区块: 18600000
视图函数数量: 15
成功调用: 12
失败调用: 3

=== 代码优化 ===
大小减少: 15,234 字节 (23.5%)
移除注释: 45 个
移除函数: 3 个
移除导入: 2 个
移除变量: 1 个
```

## 注意事项

1. **API限制**: 请注意Etherscan API的调用限制
2. **网络延迟**: 大量合约分析可能需要较长时间
3. **内存使用**: 处理大型合约时注意内存占用
4. **错误处理**: 工具会优雅处理各种错误情况

## 扩展功能

- 支持多链分析（BSC、Polygon等）
- 集成更多代理标准检测
- 增强的静态分析能力
- 可视化分析结果
- 批量报告生成

## 贡献

欢迎提交问题和功能请求。如需贡献代码，请遵循项目的编码规范。

## 许可证

MIT License

