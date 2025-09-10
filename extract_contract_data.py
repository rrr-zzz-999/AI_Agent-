#!/usr/bin/env python3
"""
智能合约数据提取工具
通过指定合约地址和链名称，提取A1描述中的所有关键信息到JSON

使用方法:
python extract_contract_data.py <contract_address> <chain_name>

支持的链:
- eth: 以太坊主网
- bsc: 币安智能链
- polygon: Polygon网络
- arbitrum: Arbitrum网络
"""

import asyncio
import sys
import json
import time
from typing import Dict, Any, Optional
from dataclasses import asdict

# 导入我们的工具
from config import config, setup_logging
from smart_contract_analyzer import SmartContractAnalyzer

# 设置日志
logger = setup_logging()

# 链配置映射
CHAIN_CONFIGS = {
    'eth': {
        'name': 'Ethereum',
        'rpc_url': 'https://eth-mainnet.nodereal.io/v1/1659dfb40aa24bbb8153a677b98064d7',
        'explorer_api': 'https://api.etherscan.io/api',
        'explorer_name': 'Etherscan'
    },
    'bsc': {
        'name': 'Binance Smart Chain',
        'rpc_url': 'https://bsc-dataseed.bnbchain.org',
        'explorer_api': 'https://api.bscscan.com/api',
        'explorer_name': 'BSCScan'
    },
    'polygon': {
        'name': 'Polygon',
        'rpc_url': 'https://polygon-rpc.com/',
        'explorer_api': 'https://api.polygonscan.com/api',
        'explorer_name': 'PolygonScan'
    },
    'arbitrum': {
        'name': 'Arbitrum',
        'rpc_url': 'https://arb1.arbitrum.io/rpc',
        'explorer_api': 'https://api.arbiscan.io/api',
        'explorer_name': 'Arbiscan'
    }
}

class ContractDataExtractor:
    """合约数据提取器"""
    
    def __init__(self, chain_name: str):
        """
        初始化数据提取器
        
        Args:
            chain_name: 链名称 (eth, bsc, polygon, arbitrum)
        """
        if chain_name.lower() not in CHAIN_CONFIGS:
            raise ValueError(f"不支持的链: {chain_name}. 支持的链: {list(CHAIN_CONFIGS.keys())}")
        
        self.chain_name = chain_name.lower()
        self.chain_config = CHAIN_CONFIGS[self.chain_name]
        
        # 设置环境变量
        import os
        os.environ['WEB3_PROVIDER_URL'] = self.chain_config['rpc_url']
        os.environ['ETHERSCAN_BASE_URL'] = self.chain_config['explorer_api']
        
        # 重新加载配置
        from config import load_config_from_env
        global config
        config = load_config_from_env()
        
        print(f"🔗 初始化 {self.chain_config['name']} 网络")
        print(f"📡 RPC: {self.chain_config['rpc_url']}")
        print(f"🔍 浏览器API: {self.chain_config['explorer_name']}")
    
    async def extract_all_data(self, contract_address: str) -> Dict[str, Any]:
        """
        提取合约的所有关键数据
        
        Args:
            contract_address: 合约地址
            
        Returns:
            包含所有提取数据的字典
        """
        print(f"\n🚀 开始提取合约数据: {contract_address}")
        print(f"🌐 网络: {self.chain_config['name']}")
        print("=" * 80)
        
        start_time = time.time()
        
        try:
            # 初始化分析器
            analyzer = SmartContractAnalyzer()
            
            # 执行全面分析
            analysis = await analyzer.comprehensive_analysis(contract_address)
            
            end_time = time.time()
            
            # 构建提取结果
            extracted_data = self._build_extracted_data(analysis, end_time - start_time)
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"数据提取失败: {e}")
            return self._build_error_result(contract_address, str(e))
    
    def _build_extracted_data(self, analysis, duration: float) -> Dict[str, Any]:
        """构建提取的数据结构"""
        
        # 基础信息
        basic_info = {
            "contract_address": analysis.contract_address,
            "chain": self.chain_config['name'],
            "chain_code": self.chain_name,
            "analysis_timestamp": analysis.analysis_timestamp,
            "analysis_duration_seconds": round(duration, 2)
        }
        
        # 1. 代理合约关系分析 (Source Code Fetcher Tool)
        proxy_analysis = self._extract_proxy_info(analysis.contract_info)
        
        # 2. 构造函数参数分析 (Constructor Parameter Tool)
        constructor_analysis = self._extract_constructor_info(analysis.deployment_info)
        
        # 3. 状态快照分析 (State Reader Tool)
        state_analysis = self._extract_state_info(analysis.state_snapshot)
        
        # 4. 代码清理分析 (Code Sanitizer Tool)
        code_analysis = self._extract_code_info(analysis.sanitized_code, analysis.contract_info)
        
        # 综合分析摘要
        analysis_summary = self._build_analysis_summary(analysis)
        
        return {
            "basic_info": basic_info,
            "proxy_analysis": proxy_analysis,
            "constructor_analysis": constructor_analysis,
            "state_analysis": state_analysis,
            "code_analysis": code_analysis,
            "analysis_summary": analysis_summary,
            "raw_analysis": asdict(analysis)  # 完整的原始数据
        }
    
    def _extract_proxy_info(self, contract_info) -> Dict[str, Any]:
        """提取代理合约信息"""
        proxy_data = {
            "is_proxy": contract_info.proxy_info is not None,
            "proxy_type": None,
            "implementation_address": None,
            "admin_address": None,
            "beacon_address": None,
            "executable_logic_access": False
        }
        
        if contract_info.proxy_info:
            proxy_data.update({
                "proxy_type": contract_info.proxy_info.proxy_type,
                "implementation_address": contract_info.proxy_info.implementation_address,
                "admin_address": contract_info.proxy_info.admin_address,
                "beacon_address": contract_info.proxy_info.beacon_address,
                "executable_logic_access": contract_info.proxy_info.implementation_address != "0x0000000000000000000000000000000000000000"
            })
        
        return proxy_data
    
    def _extract_constructor_info(self, deployment_info) -> Dict[str, Any]:
        """提取构造函数参数信息"""
        constructor_data = {
            "deployment_found": deployment_info is not None,
            "deployer_address": None,
            "deployment_block": None,
            "gas_used": None,
            "initialization_parameters": [],
            "configuration_context": {}
        }
        
        if deployment_info:
            constructor_data.update({
                "deployer_address": deployment_info.deployer_address,
                "deployment_block": deployment_info.block_number,
                "gas_used": deployment_info.gas_used
            })
            
            # 提取初始化参数
            for param in deployment_info.constructor_params:
                param_info = {
                    "name": param.name,
                    "type": param.type,
                    "value": str(param.value),
                    "decoded_value": param.decoded_value
                }
                constructor_data["initialization_parameters"].append(param_info)
                
                # 分类配置上下文
                if param.type == "address":
                    if "token_addresses" not in constructor_data["configuration_context"]:
                        constructor_data["configuration_context"]["token_addresses"] = []
                    constructor_data["configuration_context"]["token_addresses"].append({
                        "parameter": param.name,
                        "address": param.decoded_value or str(param.value)
                    })
                elif "fee" in param.name.lower() or "rate" in param.name.lower():
                    if "fee_specifications" not in constructor_data["configuration_context"]:
                        constructor_data["configuration_context"]["fee_specifications"] = []
                    constructor_data["configuration_context"]["fee_specifications"].append({
                        "parameter": param.name,
                        "value": param.decoded_value or str(param.value)
                    })
                elif "owner" in param.name.lower() or "admin" in param.name.lower():
                    if "access_control" not in constructor_data["configuration_context"]:
                        constructor_data["configuration_context"]["access_control"] = []
                    constructor_data["configuration_context"]["access_control"].append({
                        "parameter": param.name,
                        "address": param.decoded_value or str(param.value)
                    })
        
        return constructor_data
    
    def _extract_state_info(self, state_snapshot) -> Dict[str, Any]:
        """提取状态快照信息"""
        state_data = {
            "snapshot_captured": state_snapshot is not None,
            "block_number": None,
            "timestamp": None,
            "view_functions_identified": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "state_data": {},
            "function_signatures": []
        }
        
        if state_snapshot:
            state_data.update({
                "block_number": state_snapshot.block_number,
                "timestamp": state_snapshot.timestamp,
                "view_functions_identified": len(state_snapshot.view_functions),
                "successful_calls": len(state_snapshot.state_data),
                "failed_calls": len(state_snapshot.failed_calls),
                "state_data": state_snapshot.state_data
            })
            
            # 提取函数签名
            for func in state_snapshot.view_functions:
                state_data["function_signatures"].append({
                    "name": func.name,
                    "signature": func.signature,
                    "selector": func.selector,
                    "inputs": func.inputs,
                    "outputs": func.outputs
                })
        
        return state_data
    
    def _extract_code_info(self, sanitized_code, contract_info) -> Dict[str, Any]:
        """提取代码清理信息"""
        code_data = {
            "source_code_available": contract_info.source_code is not None,
            "code_sanitized": sanitized_code is not None,
            "original_size_bytes": 0,
            "sanitized_size_bytes": 0,
            "size_reduction_bytes": 0,
            "size_reduction_percent": 0,
            "removed_elements": {
                "comments": 0,
                "functions": 0,
                "imports": 0,
                "variables": 0
            },
            "sanitized_code": None,
            "compiler_version": contract_info.compiler_version
        }
        
        if contract_info.source_code:
            code_data["original_size_bytes"] = len(contract_info.source_code)
        
        if sanitized_code:
            code_data.update({
                "sanitized_size_bytes": len(sanitized_code.sanitized_code),
                "size_reduction_bytes": sanitized_code.optimization_summary["size_reduction"],
                "size_reduction_percent": sanitized_code.optimization_summary["size_reduction_percent"],
                "sanitized_code": sanitized_code.sanitized_code,
                "removed_elements": {
                    "comments": sanitized_code.optimization_summary["removed_comments"],
                    "functions": sanitized_code.optimization_summary["removed_functions"],
                    "imports": sanitized_code.optimization_summary["removed_imports"],
                    "variables": sanitized_code.optimization_summary["removed_variables"]
                }
            })
        
        return code_data
    
    def _build_analysis_summary(self, analysis) -> Dict[str, Any]:
        """构建分析摘要"""
        return {
            "tools_execution": {
                "source_code_fetcher": {
                    "executed": True,
                    "success": analysis.contract_info is not None,
                    "proxy_detected": analysis.contract_info.proxy_info is not None
                },
                "constructor_parameter_tool": {
                    "executed": True,
                    "success": analysis.deployment_info is not None,
                    "parameters_found": len(analysis.deployment_info.constructor_params) if analysis.deployment_info else 0
                },
                "state_reader_tool": {
                    "executed": True,
                    "success": analysis.state_snapshot is not None,
                    "functions_called": len(analysis.state_snapshot.state_data) if analysis.state_snapshot else 0
                },
                "code_sanitizer_tool": {
                    "executed": True,
                    "success": analysis.sanitized_code is not None,
                    "code_optimized": analysis.sanitized_code.optimization_summary["size_reduction_percent"] if analysis.sanitized_code else 0
                }
            },
            "overall_success": all([
                analysis.contract_info is not None,
                # 其他工具的成功与否取决于数据可用性
            ]),
            "data_completeness": {
                "contract_verified": analysis.contract_info.verification_status if analysis.contract_info else False,
                "source_code_available": bool(analysis.contract_info.source_code) if analysis.contract_info else False,
                "abi_available": bool(analysis.contract_info.abi) if analysis.contract_info else False,
                "deployment_traceable": analysis.deployment_info is not None
            }
        }
    
    def _build_error_result(self, contract_address: str, error_message: str) -> Dict[str, Any]:
        """构建错误结果"""
        return {
            "basic_info": {
                "contract_address": contract_address,
                "chain": self.chain_config['name'],
                "chain_code": self.chain_name,
                "analysis_timestamp": int(time.time()),
                "error": error_message
            },
            "proxy_analysis": {"error": error_message},
            "constructor_analysis": {"error": error_message},
            "state_analysis": {"error": error_message},
            "code_analysis": {"error": error_message},
            "analysis_summary": {"error": error_message}
        }

def save_results(data: Dict[str, Any], output_file: str = None) -> str:
    """保存结果到JSON文件"""
    if output_file is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        contract_addr = data["basic_info"]["contract_address"]
        chain = data["basic_info"]["chain_code"]
        output_file = f"extracted_data_{chain}_{contract_addr}_{timestamp}.json"
    
    # 确保输出目录存在
    from pathlib import Path
    output_path = Path("analysis_results") / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    return str(output_path)

def print_summary(data: Dict[str, Any]):
    """打印分析摘要"""
    basic = data["basic_info"]
    proxy = data["proxy_analysis"]
    constructor = data["constructor_analysis"]
    state = data["state_analysis"]
    code = data["code_analysis"]
    
    print("\n" + "=" * 80)
    print("📊 数据提取摘要")
    print("=" * 80)
    
    print(f"🔗 合约: {basic['contract_address']}")
    print(f"🌐 链: {basic['chain']}")
    print(f"⏱️  分析时间: {basic.get('analysis_duration_seconds', 0)}秒")
    
    print(f"\n🔧 工具执行结果:")
    print(f"   📋 代理检测: {'✅' if proxy.get('is_proxy') else '❌'} {proxy.get('proxy_type', 'N/A')}")
    print(f"   🏗️  构造参数: {'✅' if constructor.get('deployment_found') else '❌'} {len(constructor.get('initialization_parameters', []))} 个参数")
    print(f"   📸 状态快照: {'✅' if state.get('snapshot_captured') else '❌'} {state.get('successful_calls', 0)} 个调用成功")
    print(f"   🧹 代码清理: {'✅' if code.get('code_sanitized') else '❌'} {code.get('size_reduction_percent', 0)}% 减少")
    
    if proxy.get('is_proxy'):
        print(f"\n🔗 代理信息:")
        print(f"   类型: {proxy.get('proxy_type')}")
        print(f"   实现地址: {proxy.get('implementation_address')}")
        print(f"   可执行逻辑访问: {'✅' if proxy.get('executable_logic_access') else '❌'}")

async def main():
    """主函数"""
    if len(sys.argv) != 3:
        print("使用方法: python extract_contract_data.py <contract_address> <chain_name>")
        print(f"支持的链: {list(CHAIN_CONFIGS.keys())}")
        print("\n示例:")
        print("  python extract_contract_data.py 0xdDc0CFF76bcC0ee14c3e73aF630C029fe020F907 bsc")
        print("  python extract_contract_data.py 0xA0b86a33E6441E09e5fDE7f80b0138b43A5A9b27 eth")
        sys.exit(1)
    
    contract_address = sys.argv[1]
    chain_name = sys.argv[2]
    
    print("🚀 智能合约数据提取工具")
    print("基于A1四工具架构提取关键合约信息")
    print("=" * 80)
    
    try:
        # 初始化提取器
        extractor = ContractDataExtractor(chain_name)
        
        # 提取数据
        extracted_data = await extractor.extract_all_data(contract_address)
        
        # 保存结果
        output_file = save_results(extracted_data)
        
        # 打印摘要
        print_summary(extracted_data)
        
        print(f"\n💾 完整结果已保存到: {output_file}")
        print("🎉 数据提取完成!")
        
    except Exception as e:
        print(f"❌ 提取失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
