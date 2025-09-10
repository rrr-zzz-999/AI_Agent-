"""
Source Code Fetcher Tool
源代码获取工具

该工具通过字节码模式分析和实现槽检查来解析代理合约关系，
确保代理能够访问实际的可执行逻辑而不是代理接口。
该工具通过查询特定历史区块的合约状态来维持时间一致性。
"""

import json
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from web3 import Web3
from eth_utils import to_checksum_address, is_address
import requests


@dataclass
class ProxyInfo:
    """代理合约信息"""
    proxy_address: str
    implementation_address: str
    proxy_type: str  # EIP-1967, EIP-1822, OpenZeppelin等
    admin_address: Optional[str] = None
    beacon_address: Optional[str] = None


@dataclass
class ContractInfo:
    """合约信息"""
    address: str
    source_code: Optional[str] = None
    abi: Optional[List[Dict]] = None
    constructor_args: Optional[str] = None
    proxy_info: Optional[ProxyInfo] = None
    verification_status: bool = False
    compiler_version: Optional[str] = None


class SourceCodeFetcher:
    """源代码获取工具"""
    
    # EIP-1967标准存储槽
    EIP1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
    EIP1967_BEACON_SLOT = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
    
    # EIP-1822标准存储槽
    EIP1822_LOGIC_SLOT = "0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7"
    
    # OpenZeppelin代理模式
    OPENZEPPELIN_IMPLEMENTATION_SLOT = "0x7050c9e0f4ca769c69bd3a8ef740bc37934f8e2c036e5a723fd8ee048ed3f8c3"
    
    def __init__(self, web3_provider: str, etherscan_api_key: Optional[str] = None):
        """
        初始化源代码获取工具
        
        Args:
            web3_provider: Web3提供商URL
            etherscan_api_key: Etherscan API密钥（用于获取源代码）
        """
        self.w3 = Web3(Web3.HTTPProvider(web3_provider))
        self.etherscan_api_key = etherscan_api_key
        self.etherscan_base_url = "https://api.etherscan.io/api"
    
    async def fetch_contract_info(self, address: str, block_number: Optional[int] = None) -> ContractInfo:
        """
        获取合约完整信息
        
        Args:
            address: 合约地址
            block_number: 目标区块号（用于历史状态查询）
            
        Returns:
            合约信息对象
        """
        address = to_checksum_address(address)
        
        # 检查是否为代理合约
        proxy_info = await self._detect_proxy_pattern(address, block_number)
        
        # 确定要分析的实际合约地址
        target_address = proxy_info.implementation_address if proxy_info else address
        
        # 获取源代码和ABI
        source_code, abi, constructor_args, verification_status, compiler_version = await self._fetch_etherscan_data(target_address)
        
        return ContractInfo(
            address=address,
            source_code=source_code,
            abi=abi,
            constructor_args=constructor_args,
            proxy_info=proxy_info,
            verification_status=verification_status,
            compiler_version=compiler_version
        )
    
    async def _detect_proxy_pattern(self, address: str, block_number: Optional[int] = None) -> Optional[ProxyInfo]:
        """
        检测代理合约模式
        
        Args:
            address: 合约地址
            block_number: 目标区块号
            
        Returns:
            代理信息（如果是代理合约）
        """
        # 检查EIP-1967标准代理
        eip1967_impl = await self._read_storage_slot(address, self.EIP1967_IMPLEMENTATION_SLOT, block_number)
        if eip1967_impl and eip1967_impl != "0x0000000000000000000000000000000000000000000000000000000000000000":
            implementation_address = "0x" + eip1967_impl[-40:]
            if is_address(implementation_address):
                admin_address = await self._read_storage_slot(address, self.EIP1967_ADMIN_SLOT, block_number)
                beacon_address = await self._read_storage_slot(address, self.EIP1967_BEACON_SLOT, block_number)
                
                return ProxyInfo(
                    proxy_address=address,
                    implementation_address=to_checksum_address(implementation_address),
                    proxy_type="EIP-1967",
                    admin_address=to_checksum_address("0x" + admin_address[-40:]) if admin_address and admin_address != "0x0000000000000000000000000000000000000000000000000000000000000000" else None,
                    beacon_address=to_checksum_address("0x" + beacon_address[-40:]) if beacon_address and beacon_address != "0x0000000000000000000000000000000000000000000000000000000000000000" else None
                )
        
        # 检查EIP-1822标准代理
        eip1822_impl = await self._read_storage_slot(address, self.EIP1822_LOGIC_SLOT, block_number)
        if eip1822_impl and eip1822_impl != "0x0000000000000000000000000000000000000000000000000000000000000000":
            implementation_address = "0x" + eip1822_impl[-40:]
            if is_address(implementation_address):
                return ProxyInfo(
                    proxy_address=address,
                    implementation_address=to_checksum_address(implementation_address),
                    proxy_type="EIP-1822"
                )
        
        # 检查OpenZeppelin代理模式
        oz_impl = await self._read_storage_slot(address, self.OPENZEPPELIN_IMPLEMENTATION_SLOT, block_number)
        if oz_impl and oz_impl != "0x0000000000000000000000000000000000000000000000000000000000000000":
            implementation_address = "0x" + oz_impl[-40:]
            if is_address(implementation_address):
                return ProxyInfo(
                    proxy_address=address,
                    implementation_address=to_checksum_address(implementation_address),
                    proxy_type="OpenZeppelin"
                )
        
        # 通过字节码模式检测
        bytecode = self.w3.eth.get_code(address, block_identifier=block_number or 'latest')
        proxy_info = await self._analyze_bytecode_patterns(address, bytecode.hex())
        
        return proxy_info
    
    async def _read_storage_slot(self, address: str, slot: str, block_number: Optional[int] = None) -> str:
        """读取存储槽数据"""
        try:
            result = self.w3.eth.get_storage_at(
                address, 
                slot, 
                block_identifier=block_number or 'latest'
            )
            return result.hex()
        except Exception:
            return "0x0000000000000000000000000000000000000000000000000000000000000000"
    
    async def _analyze_bytecode_patterns(self, address: str, bytecode: str) -> Optional[ProxyInfo]:
        """
        分析字节码模式以检测代理合约
        
        Args:
            address: 合约地址
            bytecode: 合约字节码
            
        Returns:
            代理信息（如果检测到代理模式）
        """
        # 检查常见的代理字节码模式
        
        # Minimal Proxy (EIP-1167) 模式
        if "363d3d373d3d3d363d73" in bytecode and "5af43d82803e903d91602b57fd5bf3" in bytecode:
            # 提取实现地址
            start_idx = bytecode.find("363d3d373d3d3d363d73") + len("363d3d373d3d3d363d73")
            impl_address = "0x" + bytecode[start_idx:start_idx+40]
            if is_address(impl_address):
                return ProxyInfo(
                    proxy_address=address,
                    implementation_address=to_checksum_address(impl_address),
                    proxy_type="EIP-1167 Minimal Proxy"
                )
        
        # 检查DELEGATECALL模式
        if "f4" in bytecode:  # DELEGATECALL opcode
            # 这可能是一个自定义代理实现
            # 需要更复杂的分析来确定实现地址
            pass
        
        return None
    
    async def _fetch_etherscan_data(self, address: str) -> Tuple[Optional[str], Optional[List[Dict]], Optional[str], bool, Optional[str]]:
        """
        从Etherscan获取合约数据
        
        Args:
            address: 合约地址
            
        Returns:
            (源代码, ABI, 构造参数, 验证状态, 编译器版本)
        """
        if not self.etherscan_api_key:
            return None, None, None, False, None
        
        try:
            # 获取源代码
            params = {
                "module": "contract",
                "action": "getsourcecode",
                "address": address,
                "apikey": self.etherscan_api_key
            }
            
            response = requests.get(self.etherscan_base_url, params=params, timeout=10)
            data = response.json()
            
            if data["status"] == "1" and data["result"]:
                result = data["result"][0]
                
                source_code = result.get("SourceCode", "")
                abi_str = result.get("ABI", "")
                constructor_args = result.get("ConstructorArguments", "")
                compiler_version = result.get("CompilerVersion", "")
                
                # 解析ABI
                abi = None
                if abi_str and abi_str != "Contract source code not verified":
                    try:
                        abi = json.loads(abi_str)
                    except json.JSONDecodeError:
                        abi = None
                
                verification_status = bool(source_code and source_code != "")
                
                return source_code, abi, constructor_args, verification_status, compiler_version
            
        except Exception as e:
            print(f"获取Etherscan数据时出错: {e}")
        
        return None, None, None, False, None
    
    def get_implementation_at_block(self, proxy_address: str, block_number: int) -> Optional[str]:
        """
        获取特定区块高度时的实现合约地址
        
        Args:
            proxy_address: 代理合约地址
            block_number: 目标区块号
            
        Returns:
            实现合约地址
        """
        # 检查各种代理标准的实现槽
        slots_to_check = [
            self.EIP1967_IMPLEMENTATION_SLOT,
            self.EIP1822_LOGIC_SLOT,
            self.OPENZEPPELIN_IMPLEMENTATION_SLOT
        ]
        
        for slot in slots_to_check:
            try:
                storage_value = self.w3.eth.get_storage_at(
                    proxy_address, 
                    slot, 
                    block_identifier=block_number
                )
                
                if storage_value != b'\x00' * 32:
                    implementation_address = "0x" + storage_value.hex()[-40:]
                    if is_address(implementation_address):
                        return to_checksum_address(implementation_address)
            except Exception:
                continue
        
        return None
    
    async def batch_fetch_contracts(self, addresses: List[str], block_number: Optional[int] = None) -> Dict[str, ContractInfo]:
        """
        批量获取多个合约的信息
        
        Args:
            addresses: 合约地址列表
            block_number: 目标区块号
            
        Returns:
            地址到合约信息的映射
        """
        tasks = []
        for address in addresses:
            task = self.fetch_contract_info(address, block_number)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        contract_info_map = {}
        for i, result in enumerate(results):
            if isinstance(result, ContractInfo):
                contract_info_map[addresses[i]] = result
            else:
                # 处理异常情况
                contract_info_map[addresses[i]] = ContractInfo(
                    address=addresses[i],
                    verification_status=False
                )
        
        return contract_info_map


# 使用示例
async def main():
    """使用示例"""
    # 初始化工具
    fetcher = SourceCodeFetcher(
        web3_provider="https://eth-mainnet.alchemyapi.io/v2/YOUR_API_KEY",
        etherscan_api_key="YOUR_ETHERSCAN_API_KEY"
    )
    
    # 获取单个合约信息
    contract_info = await fetcher.fetch_contract_info("0xA0b86a33E6441E09e5fDE7f80b0138b43A5A9b27")
    print(f"合约地址: {contract_info.address}")
    print(f"是否为代理: {contract_info.proxy_info is not None}")
    if contract_info.proxy_info:
        print(f"代理类型: {contract_info.proxy_info.proxy_type}")
        print(f"实现地址: {contract_info.proxy_info.implementation_address}")
    
    # 批量获取合约信息
    addresses = [
        "0xA0b86a33E6441E09e5fDE7f80b0138b43A5A9b27",
        "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984"
    ]
    contract_map = await fetcher.batch_fetch_contracts(addresses)
    for addr, info in contract_map.items():
        print(f"{addr}: 验证状态 = {info.verification_status}")


if __name__ == "__main__":
    asyncio.run(main())

