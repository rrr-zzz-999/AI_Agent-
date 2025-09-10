"""
Smart Contract Analyzer
智能合约分析器

整合四个数据收集工具的主要接口，为智能合约行为理解提供全面的分析能力。
"""

import asyncio
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from source_code_fetcher import SourceCodeFetcher, ContractInfo
from constructor_parameter_tool import ConstructorParameterTool, DeploymentInfo
from state_reader_tool import StateReaderTool, StateSnapshot
from code_sanitizer_tool import CodeSanitizerTool, SanitizedCode


@dataclass
class ComprehensiveAnalysis:
    """全面分析结果"""
    contract_address: str
    contract_info: ContractInfo
    deployment_info: Optional[DeploymentInfo]
    state_snapshot: Optional[StateSnapshot]
    sanitized_code: Optional[SanitizedCode]
    analysis_timestamp: int
    analysis_summary: Dict[str, Any]


class SmartContractAnalyzer:
    """智能合约综合分析器"""
    
    def __init__(self, web3_provider: str, etherscan_api_key: Optional[str] = None):
        """
        初始化智能合约分析器
        
        Args:
            web3_provider: Web3提供商URL
            etherscan_api_key: Etherscan API密钥
        """
        self.source_fetcher = SourceCodeFetcher(web3_provider, etherscan_api_key)
        self.constructor_tool = ConstructorParameterTool(web3_provider, etherscan_api_key)
        self.state_reader = StateReaderTool(web3_provider, etherscan_api_key)
        self.code_sanitizer = CodeSanitizerTool()
    
    async def comprehensive_analysis(self, contract_address: str, block_number: Optional[int] = None, 
                                   include_sanitization: bool = True) -> ComprehensiveAnalysis:
        """
        执行全面的合约分析
        
        Args:
            contract_address: 合约地址
            block_number: 目标区块号
            include_sanitization: 是否包含代码清理
            
        Returns:
            全面分析结果
        """
        import time
        analysis_timestamp = int(time.time())
        
        print(f"开始分析合约: {contract_address}")
        
        # 1. 获取合约信息和源代码
        print("1. 获取合约源代码和代理信息...")
        contract_info = await self.source_fetcher.fetch_contract_info(contract_address, block_number)
        
        # 2. 分析构造函数参数
        print("2. 分析构造函数参数...")
        deployment_info = None
        try:
            deployment_info = await self.constructor_tool.analyze_constructor_params(contract_address)
        except Exception as e:
            print(f"构造函数参数分析失败: {e}")
        
        # 3. 捕获状态快照
        print("3. 捕获合约状态快照...")
        state_snapshot = None
        try:
            state_snapshot = await self.state_reader.capture_state_snapshot(contract_address, block_number)
        except Exception as e:
            print(f"状态快照捕获失败: {e}")
        
        # 4. 代码清理（如果有源代码）
        print("4. 执行代码清理...")
        sanitized_code = None
        if include_sanitization and contract_info.source_code:
            try:
                sanitized_code = self.code_sanitizer.sanitize_solidity_code(contract_info.source_code)
            except Exception as e:
                print(f"代码清理失败: {e}")
        
        # 生成分析摘要
        analysis_summary = self._generate_analysis_summary(
            contract_info, deployment_info, state_snapshot, sanitized_code
        )
        
        print("分析完成!")
        
        return ComprehensiveAnalysis(
            contract_address=contract_address,
            contract_info=contract_info,
            deployment_info=deployment_info,
            state_snapshot=state_snapshot,
            sanitized_code=sanitized_code,
            analysis_timestamp=analysis_timestamp,
            analysis_summary=analysis_summary
        )
    
    def _generate_analysis_summary(self, contract_info: ContractInfo, 
                                 deployment_info: Optional[DeploymentInfo],
                                 state_snapshot: Optional[StateSnapshot],
                                 sanitized_code: Optional[SanitizedCode]) -> Dict[str, Any]:
        """
        生成分析摘要
        
        Args:
            contract_info: 合约信息
            deployment_info: 部署信息
            state_snapshot: 状态快照
            sanitized_code: 清理后代码
            
        Returns:
            分析摘要
        """
        summary = {
            "contract_type": "proxy" if contract_info.proxy_info else "implementation",
            "verification_status": contract_info.verification_status,
            "has_source_code": bool(contract_info.source_code),
            "has_abi": bool(contract_info.abi),
            "constructor_analysis_success": deployment_info is not None,
            "state_snapshot_success": state_snapshot is not None,
            "code_sanitization_success": sanitized_code is not None
        }
        
        # 代理信息摘要
        if contract_info.proxy_info:
            summary["proxy_info"] = {
                "type": contract_info.proxy_info.proxy_type,
                "implementation_address": contract_info.proxy_info.implementation_address,
                "has_admin": bool(contract_info.proxy_info.admin_address)
            }
        
        # 构造函数参数摘要
        if deployment_info:
            summary["constructor_params_count"] = len(deployment_info.constructor_params)
            summary["deployment_block"] = deployment_info.block_number
            summary["deployer"] = deployment_info.deployer_address
        
        # 状态快照摘要
        if state_snapshot:
            summary["view_functions_count"] = len(state_snapshot.view_functions)
            summary["successful_calls"] = len(state_snapshot.state_data)
            summary["failed_calls"] = len(state_snapshot.failed_calls)
        
        # 代码清理摘要
        if sanitized_code:
            summary["code_optimization"] = sanitized_code.optimization_summary
        
        return summary
    
    async def batch_analyze_contracts(self, contract_addresses: List[str], 
                                    block_number: Optional[int] = None) -> Dict[str, ComprehensiveAnalysis]:
        """
        批量分析多个合约
        
        Args:
            contract_addresses: 合约地址列表
            block_number: 目标区块号
            
        Returns:
            地址到分析结果的映射
        """
        tasks = []
        for address in contract_addresses:
            task = self.comprehensive_analysis(address, block_number)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        analysis_map = {}
        for i, result in enumerate(results):
            if isinstance(result, ComprehensiveAnalysis):
                analysis_map[contract_addresses[i]] = result
            else:
                print(f"分析合约 {contract_addresses[i]} 失败: {result}")
        
        return analysis_map
    
    def export_analysis_to_json(self, analysis: ComprehensiveAnalysis, file_path: str):
        """
        将分析结果导出为JSON文件
        
        Args:
            analysis: 分析结果
            file_path: 文件路径
        """
        # 转换为可序列化的字典
        data = asdict(analysis)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    
    def generate_analysis_report(self, analysis: ComprehensiveAnalysis) -> str:
        """
        生成分析报告
        
        Args:
            analysis: 分析结果
            
        Returns:
            格式化的分析报告
        """
        lines = []
        lines.append("=== 智能合约综合分析报告 ===")
        lines.append("")
        lines.append(f"合约地址: {analysis.contract_address}")
        lines.append(f"分析时间: {analysis.analysis_timestamp}")
        lines.append("")
        
        # 基本信息
        lines.append("=== 基本信息 ===")
        lines.append(f"合约类型: {analysis.analysis_summary['contract_type']}")
        lines.append(f"验证状态: {'已验证' if analysis.analysis_summary['verification_status'] else '未验证'}")
        lines.append(f"有源代码: {'是' if analysis.analysis_summary['has_source_code'] else '否'}")
        lines.append(f"有ABI: {'是' if analysis.analysis_summary['has_abi'] else '否'}")
        lines.append("")
        
        # 代理信息
        if analysis.contract_info.proxy_info:
            lines.append("=== 代理信息 ===")
            lines.append(f"代理类型: {analysis.contract_info.proxy_info.proxy_type}")
            lines.append(f"实现地址: {analysis.contract_info.proxy_info.implementation_address}")
            if analysis.contract_info.proxy_info.admin_address:
                lines.append(f"管理员地址: {analysis.contract_info.proxy_info.admin_address}")
            lines.append("")
        
        # 部署信息
        if analysis.deployment_info:
            lines.append("=== 部署信息 ===")
            lines.append(f"部署者: {analysis.deployment_info.deployer_address}")
            lines.append(f"部署区块: {analysis.deployment_info.block_number}")
            lines.append(f"Gas使用: {analysis.deployment_info.gas_used:,}")
            lines.append(f"构造参数数量: {len(analysis.deployment_info.constructor_params)}")
            
            if analysis.deployment_info.constructor_params:
                lines.append("构造参数:")
                for param in analysis.deployment_info.constructor_params:
                    value_str = param.decoded_value if param.decoded_value else str(param.value)
                    lines.append(f"  {param.name} ({param.type}): {value_str}")
            lines.append("")
        
        # 状态信息
        if analysis.state_snapshot:
            lines.append("=== 状态快照 ===")
            lines.append(f"快照区块: {analysis.state_snapshot.block_number}")
            lines.append(f"视图函数数量: {len(analysis.state_snapshot.view_functions)}")
            lines.append(f"成功调用: {len(analysis.state_snapshot.state_data)}")
            lines.append(f"失败调用: {len(analysis.state_snapshot.failed_calls)}")
            
            if analysis.state_snapshot.state_data:
                lines.append("状态数据 (前5个):")
                for i, (key, value) in enumerate(analysis.state_snapshot.state_data.items()):
                    if i >= 5:
                        break
                    lines.append(f"  {key}: {value}")
            lines.append("")
        
        # 代码优化信息
        if analysis.sanitized_code:
            lines.append("=== 代码优化 ===")
            opt = analysis.sanitized_code.optimization_summary
            lines.append(f"大小减少: {opt['size_reduction']:,} 字节 ({opt['size_reduction_percent']}%)")
            lines.append(f"移除注释: {opt['removed_comments']} 个")
            lines.append(f"移除函数: {opt['removed_functions']} 个")
            lines.append(f"移除导入: {opt['removed_imports']} 个")
            lines.append(f"移除变量: {opt['removed_variables']} 个")
            lines.append("")
        
        return "\n".join(lines)
    
    async def compare_contract_states(self, contract_address: str, 
                                    block1: int, block2: int) -> Dict[str, Any]:
        """
        比较合约在不同区块的状态
        
        Args:
            contract_address: 合约地址
            block1: 第一个区块号
            block2: 第二个区块号
            
        Returns:
            状态比较结果
        """
        # 获取两个区块的状态快照
        snapshot1 = await self.state_reader.capture_state_snapshot(contract_address, block1)
        snapshot2 = await self.state_reader.capture_state_snapshot(contract_address, block2)
        
        # 比较状态
        comparison = await self.state_reader.compare_state_snapshots(snapshot1, snapshot2)
        
        return comparison


# 使用示例
async def main():
    """使用示例"""
    # 初始化分析器
    analyzer = SmartContractAnalyzer(
        web3_provider="https://eth-mainnet.alchemyapi.io/v2/YOUR_API_KEY",
        etherscan_api_key="YOUR_ETHERSCAN_API_KEY"
    )
    
    # 单个合约分析
    contract_address = "0xA0b86a33E6441E09e5fDE7f80b0138b43A5A9b27"
    
    print("执行全面分析...")
    analysis = await analyzer.comprehensive_analysis(contract_address)
    
    # 生成报告
    report = analyzer.generate_analysis_report(analysis)
    print(report)
    
    # 导出结果
    analyzer.export_analysis_to_json(analysis, f"analysis_{contract_address}.json")
    
    # 批量分析示例
    print("\n执行批量分析...")
    contracts = [
        "0xA0b86a33E6441E09e5fDE7f80b0138b43A5A9b27",
        "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"
    ]
    
    batch_results = await analyzer.batch_analyze_contracts(contracts)
    print(f"批量分析完成，成功分析 {len(batch_results)} 个合约")
    
    # 状态比较示例
    print("\n执行状态比较...")
    comparison = await analyzer.compare_contract_states(
        contract_address, 
        18500000,  # 较早的区块
        18600000   # 较晚的区块
    )
    
    print(f"状态变化数量: {len(comparison['changes'])}")


if __name__ == "__main__":
    asyncio.run(main())

