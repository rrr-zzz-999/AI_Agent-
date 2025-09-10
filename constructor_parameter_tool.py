"""
Constructor Parameter Tool
构造函数参数工具

该工具分析部署交易的calldata来重构初始化参数，
为代理提供配置上下文，包括代币地址、费用规格和访问控制参数。
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass
from web3 import Web3
from eth_utils import to_checksum_address, decode_hex
from eth_abi import decode_abi
import requests


@dataclass
class ConstructorParam:
    """构造函数参数"""
    name: str
    type: str
    value: Any
    decoded_value: Optional[str] = None  # 人类可读的解码值


@dataclass
class DeploymentInfo:
    """部署信息"""
    contract_address: str
    deployer_address: str
    transaction_hash: str
    block_number: int
    gas_used: int
    gas_price: int
    constructor_params: List[ConstructorParam]
    creation_code: str
    runtime_code: str


class ConstructorParameterTool:
    """构造函数参数分析工具"""
    
    def __init__(self, web3_provider: str, etherscan_api_key: Optional[str] = None):
        """
        初始化构造函数参数工具
        
        Args:
            web3_provider: Web3提供商URL
            etherscan_api_key: Etherscan API密钥
        """
        self.w3 = Web3(Web3.HTTPProvider(web3_provider))
        self.etherscan_api_key = etherscan_api_key
        self.etherscan_base_url = "https://api.etherscan.io/api"
    
    async def analyze_constructor_params(self, contract_address: str) -> DeploymentInfo:
        """
        分析合约的构造函数参数
        
        Args:
            contract_address: 合约地址
            
        Returns:
            部署信息
        """
        # 获取合约创建交易
        creation_tx = await self._get_contract_creation_tx(contract_address)
        if not creation_tx:
            raise ValueError(f"无法找到合约 {contract_address} 的创建交易")
        
        # 获取交易详情
        tx_receipt = self.w3.eth.get_transaction_receipt(creation_tx['hash'])
        tx_detail = self.w3.eth.get_transaction(creation_tx['hash'])
        
        # 获取合约ABI和构造函数信息
        constructor_abi = await self._get_constructor_abi(contract_address)
        
        # 分析calldata提取构造函数参数
        constructor_params = []
        if constructor_abi and tx_detail['input']:
            constructor_params = await self._decode_constructor_params(
                tx_detail['input'], 
                constructor_abi,
                contract_address
            )
        
        return DeploymentInfo(
            contract_address=contract_address,
            deployer_address=tx_detail['from'],
            transaction_hash=creation_tx['hash'],
            block_number=tx_receipt['blockNumber'],
            gas_used=tx_receipt['gasUsed'],
            gas_price=tx_detail['gasPrice'],
            constructor_params=constructor_params,
            creation_code=tx_detail['input'],
            runtime_code=self.w3.eth.get_code(contract_address).hex()
        )
    
    async def _get_contract_creation_tx(self, contract_address: str) -> Optional[Dict]:
        """
        获取合约创建交易
        
        Args:
            contract_address: 合约地址
            
        Returns:
            创建交易信息
        """
        if self.etherscan_api_key:
            try:
                # 使用Etherscan API
                params = {
                    "module": "contract",
                    "action": "getcontractcreation",
                    "contractaddresses": contract_address,
                    "apikey": self.etherscan_api_key
                }
                
                response = requests.get(self.etherscan_base_url, params=params, timeout=10)
                data = response.json()
                
                if data["status"] == "1" and data["result"]:
                    result = data["result"][0]
                    return {
                        'hash': result['txHash'],
                        'creator': result['contractCreator']
                    }
            except Exception as e:
                print(f"使用Etherscan获取创建交易失败: {e}")
        
        # 如果Etherscan失败，尝试其他方法
        return await self._find_creation_tx_by_search(contract_address)
    
    async def _find_creation_tx_by_search(self, contract_address: str) -> Optional[Dict]:
        """
        通过搜索查找创建交易（备用方法）
        
        Args:
            contract_address: 合约地址
            
        Returns:
            创建交易信息
        """
        try:
            # 获取合约的第一个交易（通常是创建交易）
            latest_block = self.w3.eth.block_number
            
            # 二分搜索找到合约创建的区块
            start_block = 0
            end_block = latest_block
            
            while start_block <= end_block:
                mid_block = (start_block + end_block) // 2
                code = self.w3.eth.get_code(contract_address, block_identifier=mid_block)
                
                if len(code) > 0:
                    end_block = mid_block - 1
                else:
                    start_block = mid_block + 1
            
            # 在目标区块附近搜索创建交易
            target_block = start_block
            for block_num in range(max(0, target_block - 10), target_block + 10):
                try:
                    block = self.w3.eth.get_block(block_num, full_transactions=True)
                    for tx in block['transactions']:
                        if tx['to'] is None:  # 合约创建交易
                            receipt = self.w3.eth.get_transaction_receipt(tx['hash'])
                            if receipt['contractAddress'] and receipt['contractAddress'].lower() == contract_address.lower():
                                return {
                                    'hash': tx['hash'].hex(),
                                    'creator': tx['from']
                                }
                except Exception:
                    continue
        
        except Exception as e:
            print(f"搜索创建交易失败: {e}")
        
        return None
    
    async def _get_constructor_abi(self, contract_address: str) -> Optional[Dict]:
        """
        获取构造函数ABI
        
        Args:
            contract_address: 合约地址
            
        Returns:
            构造函数ABI
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
                    abi = json.loads(abi_str)
                    
                    # 查找构造函数
                    for item in abi:
                        if item.get("type") == "constructor":
                            return item
            
        except Exception as e:
            print(f"获取构造函数ABI失败: {e}")
        
        return None
    
    async def _decode_constructor_params(self, calldata: str, constructor_abi: Dict, contract_address: str) -> List[ConstructorParam]:
        """
        解码构造函数参数
        
        Args:
            calldata: 交易的输入数据
            constructor_abi: 构造函数ABI
            contract_address: 合约地址
            
        Returns:
            构造函数参数列表
        """
        params = []
        
        try:
            # 获取构造函数参数类型
            param_types = []
            param_names = []
            
            for input_param in constructor_abi.get("inputs", []):
                param_types.append(input_param["type"])
                param_names.append(input_param["name"])
            
            if not param_types:
                return params
            
            # 分离创建代码和构造函数参数
            # 通常构造函数参数附加在合约字节码之后
            runtime_code = self.w3.eth.get_code(contract_address).hex()
            
            # 尝试找到构造函数参数的起始位置
            constructor_params_data = await self._extract_constructor_params_from_calldata(
                calldata, runtime_code, param_types
            )
            
            if constructor_params_data:
                # 解码参数
                decoded_values = decode_abi(param_types, decode_hex(constructor_params_data))
                
                for i, value in enumerate(decoded_values):
                    param_name = param_names[i] if i < len(param_names) else f"param_{i}"
                    param_type = param_types[i]
                    
                    # 解码特殊类型的值
                    decoded_value = await self._decode_special_value(value, param_type)
                    
                    params.append(ConstructorParam(
                        name=param_name,
                        type=param_type,
                        value=value,
                        decoded_value=decoded_value
                    ))
        
        except Exception as e:
            print(f"解码构造函数参数失败: {e}")
        
        return params
    
    async def _extract_constructor_params_from_calldata(self, calldata: str, runtime_code: str, param_types: List[str]) -> Optional[str]:
        """
        从calldata中提取构造函数参数
        
        Args:
            calldata: 完整的交易输入数据
            runtime_code: 运行时字节码
            param_types: 参数类型列表
            
        Returns:
            构造函数参数的十六进制数据
        """
        try:
            # 移除0x前缀
            calldata = calldata[2:] if calldata.startswith('0x') else calldata
            runtime_code = runtime_code[2:] if runtime_code.startswith('0x') else runtime_code
            
            # 尝试多种方法找到构造函数参数
            
            # 方法1: 如果运行时代码在calldata中，参数在其后
            if runtime_code in calldata:
                runtime_code_end = calldata.find(runtime_code) + len(runtime_code)
                constructor_params = calldata[runtime_code_end:]
                if constructor_params:
                    return "0x" + constructor_params
            
            # 方法2: 计算期望的参数长度
            expected_param_length = sum([self._get_param_length(param_type) for param_type in param_types])
            if expected_param_length > 0:
                # 从calldata末尾取参数
                constructor_params = calldata[-expected_param_length*2:]
                if len(constructor_params) == expected_param_length * 2:
                    return "0x" + constructor_params
            
            # 方法3: 使用Etherscan的构造函数参数（如果可用）
            constructor_args = await self._get_etherscan_constructor_args(calldata)
            if constructor_args:
                return "0x" + constructor_args
        
        except Exception as e:
            print(f"提取构造函数参数失败: {e}")
        
        return None
    
    def _get_param_length(self, param_type: str) -> int:
        """
        获取参数在ABI编码中的长度（32字节槽）
        
        Args:
            param_type: 参数类型
            
        Returns:
            长度（以32字节为单位）
        """
        if param_type.startswith('uint') or param_type.startswith('int'):
            return 1
        elif param_type == 'address':
            return 1
        elif param_type == 'bool':
            return 1
        elif param_type == 'bytes32':
            return 1
        elif param_type == 'string' or param_type == 'bytes':
            return -1  # 动态长度
        elif param_type.endswith('[]'):
            return -1  # 动态数组
        elif '[' in param_type and ']' in param_type:
            # 固定长度数组
            match = re.search(r'\[(\d+)\]', param_type)
            if match:
                array_length = int(match.group(1))
                base_type = param_type[:param_type.find('[')]
                return array_length * self._get_param_length(base_type)
        
        return 1  # 默认值
    
    async def _get_etherscan_constructor_args(self, calldata: str) -> Optional[str]:
        """
        从Etherscan获取构造函数参数
        
        Args:
            calldata: 交易输入数据
            
        Returns:
            构造函数参数数据
        """
        # 这里可以实现从Etherscan API获取已验证的构造函数参数
        # 目前返回None，使用其他方法
        return None
    
    async def _decode_special_value(self, value: Any, param_type: str) -> Optional[str]:
        """
        解码特殊类型的值为人类可读格式
        
        Args:
            value: 原始值
            param_type: 参数类型
            
        Returns:
            解码后的可读值
        """
        try:
            if param_type == 'address' and isinstance(value, (bytes, str)):
                if isinstance(value, bytes):
                    address = '0x' + value.hex()
                else:
                    address = value
                
                # 检查是否为已知合约
                checksum_addr = to_checksum_address(address)
                
                # 尝试获取合约名称（如果有的话）
                contract_name = await self._get_contract_name(checksum_addr)
                if contract_name:
                    return f"{checksum_addr} ({contract_name})"
                
                return checksum_addr
            
            elif param_type.startswith('uint') and isinstance(value, int):
                # 对于大数值，提供更可读的格式
                if value > 10**18:
                    ether_value = value / 10**18
                    return f"{value} ({ether_value:.6f} ETH)"
                elif value > 10**6:
                    return f"{value} ({value:,})"
                return str(value)
            
            elif param_type == 'bytes32' and isinstance(value, bytes):
                # 尝试解码为字符串
                try:
                    decoded_str = value.decode('utf-8').rstrip('\x00')
                    if decoded_str and all(c.isprintable() for c in decoded_str):
                        return f"'{decoded_str}'"
                except:
                    pass
                return '0x' + value.hex()
            
            elif param_type == 'bool':
                return str(bool(value))
            
            elif param_type == 'string':
                return f"'{value}'"
        
        except Exception:
            pass
        
        return str(value)
    
    async def _get_contract_name(self, address: str) -> Optional[str]:
        """
        获取合约名称（如果可用）
        
        Args:
            address: 合约地址
            
        Returns:
            合约名称
        """
        if not self.etherscan_api_key:
            return None
        
        try:
            params = {
                "module": "contract",
                "action": "getsourcecode",
                "address": address,
                "apikey": self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_base_url, params=params, timeout=5)
            data = response.json()
            
            if data["status"] == "1" and data["result"]:
                result = data["result"][0]
                return result.get("ContractName", None)
        
        except Exception:
            pass
        
        return None
    
    def format_deployment_info(self, deployment_info: DeploymentInfo) -> str:
        """
        格式化部署信息为可读字符串
        
        Args:
            deployment_info: 部署信息
            
        Returns:
            格式化的字符串
        """
        lines = []
        lines.append(f"合约地址: {deployment_info.contract_address}")
        lines.append(f"部署者: {deployment_info.deployer_address}")
        lines.append(f"交易哈希: {deployment_info.transaction_hash}")
        lines.append(f"区块号: {deployment_info.block_number}")
        lines.append(f"Gas使用: {deployment_info.gas_used:,}")
        lines.append(f"Gas价格: {deployment_info.gas_price:,} wei")
        lines.append("")
        
        if deployment_info.constructor_params:
            lines.append("构造函数参数:")
            for param in deployment_info.constructor_params:
                value_str = param.decoded_value if param.decoded_value else str(param.value)
                lines.append(f"  {param.name} ({param.type}): {value_str}")
        else:
            lines.append("无构造函数参数")
        
        return "\n".join(lines)


# 使用示例
async def main():
    """使用示例"""
    # 初始化工具
    tool = ConstructorParameterTool(
        web3_provider="https://eth-mainnet.alchemyapi.io/v2/YOUR_API_KEY",
        etherscan_api_key="YOUR_ETHERSCAN_API_KEY"
    )
    
    # 分析合约构造函数参数
    contract_address = "0xA0b86a33E6441E09e5fDE7f80b0138b43A5A9b27"
    deployment_info = await tool.analyze_constructor_params(contract_address)
    
    # 打印格式化的部署信息
    print(tool.format_deployment_info(deployment_info))


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

