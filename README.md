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

## 项目结构

```
script_zyc/
├── extract_contract_data.py        # 🌟 主要数据提取脚本
├── tool_1_source_code_fetcher.py   # 🔧 工具1: 源代码获取工具
├── tool_2_constructor_parameter.py # 🔧 工具2: 构造函数参数分析工具
├── tool_3_state_reader.py          # 🔧 工具3: 状态读取工具
├── tool_4_code_sanitizer.py        # 🔧 工具4: 代码清理工具
├── smart_contract_analyzer.py      # 📊 分析器核心引擎
├── config.py                       # ⚙️ 配置管理模块
├── requirements.txt                # 📦 项目依赖
├── .env                           # 🔐 环境变量配置文件
├── .gitignore                     # 🚫 Git忽略文件
└── README.md                      # 📖 项目文档
```

## 文件详细说明

### 🌟 主要脚本
- **`extract_contract_data.py`** - 统一的数据提取入口脚本
  - 支持多链（ETH、BSC、Polygon、Arbitrum）
  - 命令行接口：`python extract_contract_data.py <contract_address> <chain_name>`
  - 输出结构化JSON格式的完整分析结果

### 🔧 A1四工具架构

#### 工具1：`tool_1_source_code_fetcher.py`
**功能**：源代码获取和代理关系解析
- 通过字节码模式分析检测代理合约关系
- 支持EIP-1967、EIP-1822、OpenZeppelin等代理标准
- 实现槽检查确保访问实际可执行逻辑
- 维持时间一致性的历史区块查询

#### 工具2：`tool_2_constructor_parameter.py`
**功能**：构造函数参数重构分析
- 分析部署交易calldata重构初始化参数
- 提供配置上下文（代币地址、费用规格、访问控制参数）
- 智能解码各种参数类型
- 生成人类可读的参数值格式

#### 工具3：`tool_3_state_reader.py`
**功能**：合约状态快照捕获
- ABI分析识别所有公共和外部view函数
- 批量并发调用在目标区块捕获状态快照
- 支持历史区块状态查询和对比
- 自动处理函数签名和参数类型

#### 工具4：`tool_4_code_sanitizer.py`
**功能**：代码清理和优化
- 消除非必要元素（注释、未使用代码、无关库依赖）
- 智能保留重要注释（NatSpec、许可证等）
- 专注分析可执行逻辑，避免误导性文档
- 生成优化统计和影响分析

### 📊 核心组件
- **`smart_contract_analyzer.py`** - 分析器核心引擎
  - 整合四个工具的主要接口
  - 提供一键式全面分析功能
  - 支持批量分析和结果导出
  - 生成详细的分析报告

### ⚙️ 配置和工具
- **`config.py`** - 配置管理模块
  - 环境变量加载和验证
  - 多链网络配置支持
  - 类型转换和默认值处理
- **`requirements.txt`** - Python依赖包列表
- **`.env`** - 环境变量配置（API密钥、RPC端点等）
- **`.gitignore`** - Git版本控制忽略规则

## 安装和使用

### 1. 环境配置
```bash
# 创建并激活conda环境
conda create -n zyc python=3.11
conda activate zyc

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量
```bash
# 复制环境变量示例文件
cp env_example.txt .env

# 编辑.env文件，填入您的API密钥
# WEB3_PROVIDER_URL=https://eth-mainnet.alchemyapi.io/v2/YOUR_API_KEY
# ETHERSCAN_API_KEY=YOUR_ETHERSCAN_API_KEY
```

### 3. 基本使用

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

### 4. 使用主要数据提取脚本

#### 命令行使用
```bash
# 基本用法
python extract_contract_data.py <contract_address> <chain_name>

# 示例：分析BSC合约
python extract_contract_data.py 0xdDc0CFF76bcC0ee14c3e73aF630C029fe020F907 bsc

# 示例：分析以太坊合约
python extract_contract_data.py 0xA0b86a33E6441E09e5fDE7f80b0138b43A5A9b27 eth

# 支持的链
# eth - 以太坊主网
# bsc - 币安智能链
# polygon - Polygon网络
# arbitrum - Arbitrum网络
```

#### 输出结果
脚本会生成包含以下信息的JSON文件：
- 🔗 代理合约关系分析
- 🏗️ 构造函数参数重构
- 📸 合约状态快照
- 🧹 代码清理优化
- 📊 完整分析摘要

### 5. 单独使用各个工具

#### 工具1：源代码获取
```python
from tool_1_source_code_fetcher import SourceCodeFetcher

fetcher = SourceCodeFetcher(web3_provider, etherscan_api_key)
contract_info = await fetcher.fetch_contract_info(contract_address)
```

#### 工具2：构造函数参数分析
```python
from tool_2_constructor_parameter import ConstructorParameterTool

tool = ConstructorParameterTool(web3_provider, etherscan_api_key)
deployment_info = await tool.analyze_constructor_params(contract_address)
```

#### 工具3：状态读取
```python
from tool_3_state_reader import StateReaderTool

reader = StateReaderTool(web3_provider, etherscan_api_key)
snapshot = await reader.capture_state_snapshot(contract_address)
```

#### 工具4：代码清理
```python
from tool_4_code_sanitizer import CodeSanitizerTool

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

