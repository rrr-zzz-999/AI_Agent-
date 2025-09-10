"""
State Reader Tool
状态读取工具

该工具执行ABI分析以识别所有公共和外部view函数，
使代理能够通过批量调用在目标区块捕获合约状态快照。
"""

import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict
from web3 import Web3
from web3.contract import Contract
from eth_utils import to_checksum_address
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class ViewFunction:
    """视图函数信息"""
    name: str
    inputs: List[Dict[str, Any]]
    outputs: List[Dict[str, Any]]
    signature: str
    selector: str


@dataclass
class StateSnapshot:
    """状态快照"""
    contract_address: str
    block_number: int
    timestamp: int
    view_functions: List[ViewFunction]
    state_data: Dict[str, Any]
    failed_calls: List[str]


@dataclass
class BatchCallResult:
    """批量调用结果"""
    function_name: str
    inputs: List[Any]
    success: bool
    result: Any = None
    error: Optional[str] = None


class StateReaderTool:
    """状态读取工具"""
    
    def __init__(self, web3_provider: str, etherscan_api_key: Optional[str] = None, max_workers: int = 10):
        """
        初始化状态读取工具
        
        Args:
            web3_provider: Web3提供商URL
            etherscan_api_key: Etherscan API密钥
            max_workers: 最大并发工作线程数
        """
        self.w3 = Web3(Web3.HTTPProvider(web3_provider))
        self.etherscan_api_key = etherscan_api_key
        self.etherscan_base_url = "https://api.etherscan.io/api"
        self.max_workers = max_workers
    
    async def capture_state_snapshot(self, contract_address: str, block_number: Optional[int] = None) -> StateSnapshot:
        """
        捕获合约状态快照
        
        Args:
            contract_address: 合约地址
            block_number: 目标区块号（默认为latest）
            
        Returns:
            状态快照
        """
        contract_address = to_checksum_address(contract_address)
        
        if block_number is None:
            block_number = self.w3.eth.block_number
        
        # 获取区块时间戳
        block = self.w3.eth.get_block(block_number)
        timestamp = block['timestamp']
        
        # 获取合约ABI
        abi = await self._get_contract_abi(contract_address)
        if not abi:
            raise ValueError(f"无法获取合约 {contract_address} 的ABI")
        
        # 分析ABI获取view函数
        view_functions = self._extract_view_functions(abi)
        
        # 批量调用view函数
        state_data, failed_calls = await self._batch_call_view_functions(
            contract_address, view_functions, block_number
        )
        
        return StateSnapshot(
            contract_address=contract_address,
            block_number=block_number,
            timestamp=timestamp,
            view_functions=view_functions,
            state_data=state_data,
            failed_calls=failed_calls
        )
    
    async def _get_contract_abi(self, contract_address: str) -> Optional[List[Dict]]:
        """
        获取合约ABI
        
        Args:
            contract_address: 合约地址
            
        Returns:
            合约ABI
        """
        if not self.etherscan_api_key:
            return None
        
        try:
            params = {
                "module": "contract",
                "action": "getsourcecode", 
                "address": contract_address,
                "apikey": self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_base_url, params=params, timeout=10)
            data = response.json()
            
            if data["status"] == "1" and data["result"]:
                result = data["result"][0]
                abi_str = result.get("ABI", "")
                
                if abi_str and abi_str != "Contract source code not verified":
                    return json.loads(abi_str)
        
        except Exception as e:
            print(f"获取ABI失败: {e}")
        
        return None
    
    def _extract_view_functions(self, abi: List[Dict]) -> List[ViewFunction]:
        """
        从ABI中提取view函数
        
        Args:
            abi: 合约ABI
            
        Returns:
            视图函数列表
        """
        view_functions = []
        
        for item in abi:
            if (item.get("type") == "function" and 
                item.get("stateMutability") in ["view", "pure"] and
                not item.get("name", "").startswith("_")):  # 跳过私有函数
                
                # 计算函数签名和选择器
                signature = self._build_function_signature(item)
                selector = Web3.keccak(text=signature)[:4].hex()
                
                view_function = ViewFunction(
                    name=item["name"],
                    inputs=item.get("inputs", []),
                    outputs=item.get("outputs", []),
                    signature=signature,
                    selector=selector
                )
                
                view_functions.append(view_function)
        
        return view_functions
    
    def _build_function_signature(self, func_abi: Dict) -> str:
        """
        构建函数签名
        
        Args:
            func_abi: 函数ABI
            
        Returns:
            函数签名字符串
        """
        name = func_abi["name"]
        inputs = func_abi.get("inputs", [])
        
        param_types = []
        for input_param in inputs:
            param_types.append(input_param["type"])
        
        return f"{name}({','.join(param_types)})"
    
    async def _batch_call_view_functions(self, contract_address: str, view_functions: List[ViewFunction], block_number: int) -> Tuple[Dict[str, Any], List[str]]:
        """
        批量调用view函数
        
        Args:
            contract_address: 合约地址
            view_functions: 视图函数列表
            block_number: 目标区块号
            
        Returns:
            (状态数据, 失败的调用列表)
        """
        state_data = {}
        failed_calls = []
        
        # 创建合约实例
        try:
            # 构建基本ABI用于调用
            abi = []
            for func in view_functions:
                abi.append({
                    "type": "function",
                    "name": func.name,
                    "inputs": func.inputs,
                    "outputs": func.outputs,
                    "stateMutability": "view"
                })
            
            contract = self.w3.eth.contract(
                address=contract_address,
                abi=abi
            )
        except Exception as e:
            print(f"创建合约实例失败: {e}")
            return state_data, [f.name for f in view_functions]
        
        # 准备批量调用任务
        call_tasks = []
        
        for func in view_functions:
            # 对于无参数的函数，直接调用
            if not func.inputs:
                task = self._call_view_function(contract, func.name, [], block_number)
                call_tasks.append((func.name, [], task))
            else:
                # 对于有参数的函数，尝试使用默认值或跳过
                default_inputs = self._generate_default_inputs(func.inputs)
                if default_inputs is not None:
                    task = self._call_view_function(contract, func.name, default_inputs, block_number)
                    call_tasks.append((func.name, default_inputs, task))
                else:
                    failed_calls.append(f"{func.name} (需要参数)")
        
        # 执行批量调用
        results = await asyncio.gather(*[task for _, _, task in call_tasks], return_exceptions=True)
        
        # 处理结果
        for i, result in enumerate(results):
            func_name, inputs, _ = call_tasks[i]
            
            if isinstance(result, Exception):
                failed_calls.append(f"{func_name}: {str(result)}")
            else:
                # 格式化结果
                formatted_result = self._format_call_result(result, view_functions, func_name)
                
                if inputs:
                    key = f"{func_name}({', '.join(map(str, inputs))})"
                else:
                    key = func_name
                
                state_data[key] = formatted_result
        
        return state_data, failed_calls
    
    async def _call_view_function(self, contract: Contract, function_name: str, inputs: List[Any], block_number: int) -> Any:
        """
        调用单个view函数
        
        Args:
            contract: 合约实例
            function_name: 函数名
            inputs: 输入参数
            block_number: 区块号
            
        Returns:
            函数调用结果
        """
        try:
            func = getattr(contract.functions, function_name)
            
            if inputs:
                result = func(*inputs).call(block_identifier=block_number)
            else:
                result = func().call(block_identifier=block_number)
            
            return result
        
        except Exception as e:
            raise Exception(f"调用 {function_name} 失败: {str(e)}")
    
    def _generate_default_inputs(self, inputs: List[Dict[str, Any]]) -> Optional[List[Any]]:
        """
        为函数输入生成默认值
        
        Args:
            inputs: 输入参数定义
            
        Returns:
            默认值列表（如果无法生成则返回None）
        """
        default_values = []
        
        for input_param in inputs:
            param_type = input_param["type"]
            default_value = self._get_default_value_for_type(param_type)
            
            if default_value is None:
                return None  # 无法为某个参数生成默认值
            
            default_values.append(default_value)
        
        return default_values
    
    def _get_default_value_for_type(self, param_type: str) -> Any:
        """
        为特定类型生成默认值
        
        Args:
            param_type: 参数类型
            
        Returns:
            默认值
        """
        if param_type == "address":
            return "0x0000000000000000000000000000000000000000"
        elif param_type.startswith("uint"):
            return 0
        elif param_type.startswith("int"):
            return 0
        elif param_type == "bool":
            return False
        elif param_type == "bytes32":
            return "0x0000000000000000000000000000000000000000000000000000000000000000"
        elif param_type == "string":
            return ""
        elif param_type == "bytes":
            return b""
        elif param_type.endswith("[]"):
            return []
        elif "[" in param_type and "]" in param_type:
            # 固定长度数组，暂时不支持
            return None
        else:
            return None
    
    def _format_call_result(self, result: Any, view_functions: List[ViewFunction], function_name: str) -> Any:
        """
        格式化调用结果
        
        Args:
            result: 原始结果
            view_functions: 视图函数列表
            function_name: 函数名
            
        Returns:
            格式化后的结果
        """
        # 找到对应的函数定义
        func_def = None
        for func in view_functions:
            if func.name == function_name:
                func_def = func
                break
        
        if not func_def:
            return result
        
        # 根据输出类型格式化结果
        outputs = func_def.outputs
        
        if len(outputs) == 0:
            return None
        elif len(outputs) == 1:
            return self._format_single_value(result, outputs[0])
        else:
            # 多个返回值
            if isinstance(result, (tuple, list)):
                formatted_result = {}
                for i, output in enumerate(outputs):
                    if i < len(result):
                        key = output.get("name", f"output_{i}")
                        formatted_result[key] = self._format_single_value(result[i], output)
                return formatted_result
            else:
                return result
    
    def _format_single_value(self, value: Any, output_def: Dict[str, Any]) -> Any:
        """
        格式化单个值
        
        Args:
            value: 原始值
            output_def: 输出定义
            
        Returns:
            格式化后的值
        """
        output_type = output_def.get("type", "")
        
        if output_type == "address" and isinstance(value, str):
            return to_checksum_address(value)
        elif output_type.startswith("uint") and isinstance(value, int):
            # 对于大数值，提供更多信息
            if value > 10**18:
                return {
                    "raw": str(value),
                    "ether": str(value / 10**18),
                    "formatted": f"{value:,}"
                }
            elif value > 10**6:
                return {
                    "raw": str(value),
                    "formatted": f"{value:,}"
                }
            return value
        elif output_type == "bytes32" and isinstance(value, bytes):
            hex_value = value.hex()
            # 尝试解码为字符串
            try:
                str_value = value.decode('utf-8').rstrip('\x00')
                if str_value and all(c.isprintable() for c in str_value):
                    return {
                        "hex": hex_value,
                        "string": str_value
                    }
            except:
                pass
            return hex_value
        elif isinstance(value, bytes):
            return value.hex()
        else:
            return value
    
    async def compare_state_snapshots(self, snapshot1: StateSnapshot, snapshot2: StateSnapshot) -> Dict[str, Any]:
        """
        比较两个状态快照
        
        Args:
            snapshot1: 第一个快照
            snapshot2: 第二个快照
            
        Returns:
            比较结果
        """
        comparison = {
            "contract_address": snapshot1.contract_address,
            "block_range": f"{snapshot1.block_number} -> {snapshot2.block_number}",
            "time_range": f"{snapshot1.timestamp} -> {snapshot2.timestamp}",
            "changes": {},
            "new_functions": [],
            "removed_functions": []
        }
        
        # 比较共同的函数
        common_functions = set(snapshot1.state_data.keys()) & set(snapshot2.state_data.keys())
        
        for func_name in common_functions:
            value1 = snapshot1.state_data[func_name]
            value2 = snapshot2.state_data[func_name]
            
            if value1 != value2:
                comparison["changes"][func_name] = {
                    "old_value": value1,
                    "new_value": value2
                }
        
        # 新增的函数
        new_functions = set(snapshot2.state_data.keys()) - set(snapshot1.state_data.keys())
        comparison["new_functions"] = list(new_functions)
        
        # 移除的函数
        removed_functions = set(snapshot1.state_data.keys()) - set(snapshot2.state_data.keys())
        comparison["removed_functions"] = list(removed_functions)
        
        return comparison
    
    def export_snapshot_to_json(self, snapshot: StateSnapshot, file_path: str):
        """
        将快照导出为JSON文件
        
        Args:
            snapshot: 状态快照
            file_path: 文件路径
        """
        snapshot_dict = asdict(snapshot)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot_dict, f, indent=2, ensure_ascii=False, default=str)
    
    def import_snapshot_from_json(self, file_path: str) -> StateSnapshot:
        """
        从JSON文件导入快照
        
        Args:
            file_path: 文件路径
            
        Returns:
            状态快照
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 重构ViewFunction对象
        view_functions = []
        for func_data in data["view_functions"]:
            view_functions.append(ViewFunction(**func_data))
        
        return StateSnapshot(
            contract_address=data["contract_address"],
            block_number=data["block_number"],
            timestamp=data["timestamp"],
            view_functions=view_functions,
            state_data=data["state_data"],
            failed_calls=data["failed_calls"]
        )
    
    async def batch_capture_multiple_contracts(self, contract_addresses: List[str], block_number: Optional[int] = None) -> Dict[str, StateSnapshot]:
        """
        批量捕获多个合约的状态快照
        
        Args:
            contract_addresses: 合约地址列表
            block_number: 目标区块号
            
        Returns:
            地址到快照的映射
        """
        tasks = []
        for address in contract_addresses:
            task = self.capture_state_snapshot(address, block_number)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        snapshots = {}
        for i, result in enumerate(results):
            if isinstance(result, StateSnapshot):
                snapshots[contract_addresses[i]] = result
            else:
                print(f"获取合约 {contract_addresses[i]} 状态失败: {result}")
        
        return snapshots


# 使用示例
async def main():
    """使用示例"""
    # 初始化工具
    tool = StateReaderTool(
        web3_provider="https://eth-mainnet.alchemyapi.io/v2/YOUR_API_KEY",
        etherscan_api_key="YOUR_ETHERSCAN_API_KEY"
    )
    
    # 捕获单个合约状态快照
    contract_address = "0xA0b86a33E6441E09e5fDE7f80b0138b43A5A9b27"
    snapshot = await tool.capture_state_snapshot(contract_address)
    
    print(f"合约: {snapshot.contract_address}")
    print(f"区块: {snapshot.block_number}")
    print(f"时间戳: {snapshot.timestamp}")
    print(f"成功调用: {len(snapshot.state_data)} 个函数")
    print(f"失败调用: {len(snapshot.failed_calls)} 个函数")
    
    # 导出快照
    tool.export_snapshot_to_json(snapshot, "contract_snapshot.json")
    
    # 批量捕获多个合约
    contracts = [
        "0xA0b86a33E6441E09e5fDE7f80b0138b43A5A9b27",
        "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"
    ]
    snapshots = await tool.batch_capture_multiple_contracts(contracts)
    
    for addr, snap in snapshots.items():
        print(f"\n{addr}: {len(snap.state_data)} 个函数")


if __name__ == "__main__":
    asyncio.run(main())

